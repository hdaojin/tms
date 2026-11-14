"""Convert the legacy AI app identity before running Django migrations."""
import hashlib
import json

from cryptography.fernet import InvalidToken
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connections, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.views.decorators.debug import sensitive_variables

from accounts.models import GroupProfile, UserProfile
from ai.models import AIModel, AIModelOption, AIModelPreference, AIProviderSettings
from ai.services import cipher

OLD = "ai_models"
NEW = "ai"
BUNDLES = {f"{OLD}.{name}": f"{NEW}.{name}" for name in ("manage_own", "use_shared")}
MODELS = (AIModel, AIModelOption, AIModelPreference, AIProviderSettings)
PROFILES = (UserProfile, GroupProfile)
NEW_FIELDS = {
    "ai_models_aiprovidersettings": {"enabled"},
    "ai_models_aimodeloption": {"supports_images", "supports_json"},
}


def digest_table(cursor, table, quote):
    cursor.execute(f"SELECT * FROM {quote(table)} ORDER BY id")
    digest = hashlib.sha256()
    count = 0
    for row in cursor:
        digest.update(repr(tuple(bytes(value) if isinstance(value, memoryview) else value for value in row)).encode())
        digest.update(b"\n")
        count += 1
    return count, digest.hexdigest()


@sensitive_variables()
def inspect_upgrade(connection, cursor):
    quote = connection.ops.quote_name
    metadata = (*MODELS, AIModel.shared_users.through, AIModel.shared_groups.through)
    tables = {f"{OLD}_{model._meta.db_table.removeprefix('ai_')}": model for model in metadata}
    existing = set(connection.introspection.table_names(cursor))
    old_tables = set(tables) & existing
    new_tables = {model._meta.db_table for model in tables.values()}
    history = set(MigrationRecorder(connection).applied_migrations())
    graph = MigrationLoader(None)
    old_history = {name for app, name in history if app == OLD}
    new_history = {name for app, name in history if app == NEW}
    legacy_leaf = (NEW, "0005_model_share_audience")
    expected = {name for app, name in graph.graph.forwards_plan(legacy_leaf) if app == NEW}
    content = ContentType.objects.using(connection.alias)
    old_types = set(content.filter(app_label=OLD).values_list("id", "model"))
    new_types = set(content.filter(app_label=NEW).values_list("id", "model"))
    required_types = {model._meta.model_name for model in MODELS}
    if not any(table.startswith("ai_models_") for table in existing) and not old_history and not old_types:
        if new_tables <= existing and expected <= new_history and required_types <= {name for _, name in new_types}:
            return None
        raise CommandError("数据库未处于完整的旧版或新版状态。空库请直接执行 migrate。")
    if (
        old_tables != set(tables)
        or any(table.startswith("ai_models_") and table not in tables for table in existing)
        or any(table.startswith("ai_") and not table.startswith("ai_models_") for table in existing)
        or old_history != expected
        or new_history
        or new_types
        or {name for _, name in old_types} != required_types
    ):
        raise CommandError("AI 表、迁移记录或 ContentType 存在缺失或冲突，升级已停止。")
    if ("training", "0026_training_log_ai_workflow") not in history:
        raise CommandError("请先使用旧版代码应用训练日志 AI 工作流迁移。")
    converted_history = {(NEW if app == OLD else app, name) for app, name in history}
    missing = {
        parent for node in converted_history & graph.graph.nodes.keys()
        for parent in graph.graph.forwards_plan(node) if parent not in converted_history
    }
    if missing:
        raise CommandError(f"旧库缺少依赖迁移：{sorted(missing)}")
    for table, model in tables.items():
        columns = {field.name for field in connection.introspection.get_table_description(cursor, table)}
        expected_columns = {field.column for field in model._meta.local_concrete_fields}
        if columns != expected_columns - NEW_FIELDS.get(table, set()):
            raise CommandError(f"旧表字段不完整：{table}")
    verify_foreign_keys(connection, cursor, tables)
    cursor.execute(
        f"SELECT id, encrypted_api_key FROM {quote('ai_models_aimodel')} ORDER BY id"
    )
    encryption = cipher()
    for pk, encrypted in cursor:
        try:
            encryption.decrypt(bytes(encrypted)).decode()
        except (ValueError, InvalidToken):
            raise CommandError(f"模型 {pk} 的凭据无法解密，请核对原加密配置。") from None
    model_type_id = next(pk for pk, name in old_types if name == "aimodel")
    cursor.execute("SELECT id, codename FROM auth_permission WHERE content_type_id = %s", [model_type_id])
    permissions = list(cursor)
    required_permissions = {"view_aimodel", "manage_own_aimodel", "use_shared_aimodel"}
    if not required_permissions <= {codename for _, codename in permissions}:
        raise CommandError("旧版 AI 权限不完整。")
    return tables, old_types, permissions


def verify_foreign_keys(connection, cursor, tables, *, renamed=False):
    aliases = {model._meta.db_table: (model._meta.db_table if renamed else old) for old, model in tables.items()}
    expected = {}
    for table, model in tables.items():
        table = model._meta.db_table if renamed else table
        expected[table] = {
            field.column: (aliases.get(target._meta.db_table, target._meta.db_table), field.target_field.column)
            for field in model._meta.local_concrete_fields
            if field.many_to_one and (target := field.remote_field.model)
        }
    expected["training_trainingloggeneration"] = {"model_id": (aliases["ai_aimodel"], "id")}
    for table, targets in expected.items():
        constraints = connection.introspection.get_constraints(cursor, table)
        observed = {item["columns"][0]: item["foreign_key"] for item in constraints.values() if item["foreign_key"]}
        if any(observed.get(column) != target for column, target in targets.items()):
            raise CommandError(f"外键目标与预期不符：{table}")


def bundle_changes(alias):
    for profile in PROFILES:
        changes = []
        for pk, codes in profile.objects.using(alias).values_list("pk", "selected_permission_bundles").iterator():
            if not isinstance(codes, list) or any(not isinstance(code, str) for code in codes):
                raise CommandError(f"{profile._meta.label} #{pk} 的权限包数据格式异常。")
            if not BUNDLES.keys() & set(codes):
                continue
            converted = []
            for code in codes:
                new_code = BUNDLES.get(code, code)
                if new_code not in BUNDLES.values() or new_code not in converted:
                    converted.append(new_code)
            changes.append((pk, converted))
        yield profile, changes


class Command(BaseCommand):
    help = "预检或原地迁移旧版 AI APP 的数据库身份。须在维护窗口使用。"

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--apply", action="store_true")
        parser.add_argument("--database", default="default")
        parser.add_argument("--if-needed", action="store_true", help="部署集成：跳过空库，报告是否需要转换。")

    def handle(self, *args, **options):
        alias = options["database"]
        connection = connections[alias]
        if connection.vendor not in {"sqlite", "postgresql"}:
            raise CommandError("仅支持 PostgreSQL 和 SQLite。")
        quote = connection.ops.quote_name
        try:
            with transaction.atomic(using=alias), connection.cursor() as cursor:
                if options["if_needed"] and not connection.introspection.table_names(cursor):
                    return
                if options["apply"] and connection.vendor == "postgresql":
                    cursor.execute("SET LOCAL lock_timeout = '5s'")
                manifest = inspect_upgrade(connection, cursor)
                changes = list(bundle_changes(alias))
                if manifest is None:
                    if any(rows for _, rows in changes):
                        raise CommandError("新版数据库仍有旧 AI 权限包，疑似部分升级。")
                    self.stdout.write("数据库已完成 AI APP 更名。")
                    return
                tables, content_types, permissions = manifest
                connection.check_constraints()
                untouched = (
                    "training_trainingloggeneration", "auth_permission",
                    "auth_group_permissions", "auth_user_user_permissions",
                )
                baseline = {table: digest_table(cursor, table, quote) for table in (*tables, *untouched)}
                self.stdout.write(json.dumps({
                    "tables": {old: {"target": model._meta.db_table, "rows": baseline[old][0]}
                               for old, model in tables.items()},
                    "content_types": sorted(content_types),
                    "permissions": sorted(permissions),
                    "bundle_profiles": {profile._meta.label: len(rows) for profile, rows in changes},
                    "training_generations": baseline["training_trainingloggeneration"][0],
                }, ensure_ascii=False))
                if not options["apply"]:
                    self.stdout.write("只读预检通过。")
                    if options["if_needed"]:
                        self.stdout.write("TMS_AI_RENAME_REQUIRED")
                    return
                for old, model in tables.items():
                    cursor.execute(f"ALTER TABLE {quote(old)} RENAME TO {quote(model._meta.db_table)}")
                cursor.execute("UPDATE django_migrations SET app = %s WHERE app = %s", [NEW, OLD])
                ContentType.objects.using(alias).filter(app_label=OLD).update(app_label=NEW)
                for profile, rows in changes:
                    for pk, codes in rows:
                        profile.objects.using(alias).filter(pk=pk).update(selected_permission_bundles=codes)
                for table, expected in baseline.items():
                    target = tables[table]._meta.db_table if table in tables else table
                    if digest_table(cursor, target, quote) != expected:
                        raise CommandError(f"升级前后数据不一致：{target}")
                connection.check_constraints()
                verify_foreign_keys(connection, cursor, tables, renamed=True)
                if inspect_upgrade(connection, cursor) is not None:
                    raise CommandError("升级后仍检测到旧版数据库标识。")
        except ValidationError as exc:
            raise CommandError(exc.messages[0]) from None
        except DatabaseError:
            raise CommandError("数据库检查或更名失败，事务已回滚。请核对停机状态、表和约束。") from None
        ContentType.objects.clear_cache()
        self.stdout.write(self.style.SUCCESS("AI APP 数据库更名完成，可以运行 migrate。"))
