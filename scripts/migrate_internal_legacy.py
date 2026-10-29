"""内网旧部署的显式迁移入口：只处理恢复副本，不连接生产源库。

从仓库根目录使用 uv run scripts/migrate_internal_legacy.py；环境采用迁移角色。
默认只预览，--apply 才写入目标库。历史原始数据仍由完整数据库备份保留。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, os.environ.get("TMS_RELEASE_DIR", str(Path(__file__).resolve().parent.parent)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tmsproject.settings")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.core.management.color import no_style  # noqa: E402
from django.db import connections, transaction  # noqa: E402
from django.db.migrations.loader import MigrationLoader  # noqa: E402
from django.db.migrations.recorder import MigrationRecorder  # noqa: E402


STABLE_APPS = {
    "accounts", "behaviors", "core", "event_countdown", "feedback", "flatpages",
    "glossary", "meetings", "notes", "notices", "samba", "sites", "worldskills_forum",
}
EXTRA_TABLES = {"auth_user", "auth_group", "auth_user_groups", "django_session",
                "standards_skillproject", "scoring_scoringparserconfig"}
PERMISSION_TABLES = {
    "auth_group_permissions": "group_id",
    "auth_user_user_permissions": "user_id",
    "accounts_groupprofile_explicit_permissions": "groupprofile_id",
    "accounts_userprofile_explicit_permissions": "userprofile_id",
}
UPGRADES = {
    "behaviors": "0015_alter_conductrecord_attachment",
    "event_countdown": "0003_alter_countdownevent_theme",
    "feedback": "0002_alter_feedback_category",
    "worldskills_forum": "0005_alter_forumtopic_options",
}


def rows(connection, table):
    with connection.cursor() as cursor:
        ordering = "session_key" if table == "django_session" else "id"
        cursor.execute(f'SELECT * FROM "{table}" ORDER BY "{ordering}"')
        names = [column.name for column in cursor.description]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def digest(records):
    return hashlib.sha256(json.dumps(records, sort_keys=True, default=str,
                                     ensure_ascii=False).encode()).hexdigest()


def upgrade_restored_catalogs():
    connection = connections["legacy"]
    loader = MigrationLoader(connection)
    recorder = MigrationRecorder(connection)
    for app, baseline in UPGRADES.items():
        state = loader.project_state([(app, baseline)])
        for key in sorted(loader.disk_migrations):
            if key[0] != app or key[1] <= baseline:
                continue
            migration = loader.disk_migrations[key]
            if key not in recorder.applied_migrations():
                with connection.schema_editor() as editor:
                    state = migration.apply(state, editor)
                recorder.record_applied(*key)
            else:
                state = migration.mutate_state(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-database", required=True)
    parser.add_argument("--target-database", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.source_database.startswith("tms_legacy_restore_"):
        parser.error("源库必须是 tms_legacy_restore_ 前缀的恢复副本")
    target = connections["default"]
    if target.settings_dict["NAME"] != args.target_database or args.target_database == args.source_database:
        parser.error("目标数据库与环境不一致，或源目标相同")
    legacy_config = target.settings_dict.copy()
    legacy_config["NAME"] = args.source_database
    connections.databases["legacy"] = legacy_config
    source = connections["legacy"]
    original_tables = set(source.introspection.table_names())
    report = {"source": args.source_database, "target": args.target_database,
              "applied": False, "tables": {}, "unmapped_permissions": [], "archives": {},
              "permission_mapping": {}}
    allowed = set(EXTRA_TABLES)
    for model in apps.get_models(include_auto_created=True):
        if model._meta.app_label in STABLE_APPS:
            allowed.add(model._meta.db_table)
    allowed -= set(PERMISSION_TABLES)
    # Empty retired tables need no invented replacement. Every nonempty omitted table is archived.
    omitted = original_tables - allowed - set(PERMISSION_TABLES) - {
        "django_migrations", "django_content_type", "auth_permission",
    }
    for table in sorted(omitted):
        data = rows(source, table)
        if data:
            report["archives"][table] = {"count": len(data), "sha256": digest(data)}
    permission_keys = {}
    with source.cursor() as cursor:
        cursor.execute("SELECT p.id,c.app_label,c.model,p.codename FROM auth_permission p "
                       "JOIN django_content_type c ON c.id=p.content_type_id")
        permission_keys = {pk: (app, model, code) for pk, app, model, code in cursor.fetchall()}
    with target.cursor() as cursor:
        cursor.execute("SELECT p.id,c.app_label,c.model,p.codename FROM auth_permission p "
                       "JOIN django_content_type c ON c.id=p.content_type_id")
        permission_ids = {(app, model, code): pk for pk, app, model, code in cursor.fetchall()}
    permission_links = {}
    for table, owner in PERMISSION_TABLES.items():
        links = []
        for row in rows(source, table):
            key = permission_keys[row["permission_id"]]
            if key not in permission_ids:
                report["unmapped_permissions"].append({"table": table, "owner": row[owner], "key": key})
            else:
                links.append((row[owner], permission_ids[key]))
                report["permission_mapping"][str(row["permission_id"])] = {
                    "key": key, "target_id": permission_ids[key],
                }
        permission_links[table] = links
    for table in sorted(allowed & original_tables):
        data = rows(source, table)
        report["tables"][table] = {"count": len(data), "source_sha256": digest(data)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.apply:
        print(json.dumps({"preview": True, "tables": len(report["tables"]),
                          "archives": report["archives"], "unmapped_permissions": report["unmapped_permissions"]}, ensure_ascii=False))
        return
    if Path("/srv/tms/current").exists() and not Path("/var/lib/tms/maintenance.flag").exists():
        raise RuntimeError("已存在活动发布，必须先进入维护状态才允许覆盖目标数据")
    if report["unmapped_permissions"]:
        raise RuntimeError("存在不能等价映射的权限；详见受限预览报告，停止导入")
    upgrade_restored_catalogs()
    # This historical migration only adds the project's default flag and its constraints.
    loader = MigrationLoader(source)
    project_migration = ("standards", "0002_skillproject_is_default_and_more")
    recorder = MigrationRecorder(source)
    if project_migration not in recorder.applied_migrations():
        state = loader.project_state([("standards", "0001_initial")])
        with source.schema_editor() as editor:
            loader.disk_migrations[project_migration].apply(state, editor)
        recorder.record_applied(*project_migration)
    # Re-query generated catalog tables after historical data conversions.
    tables = sorted(allowed & set(source.introspection.table_names()) & set(target.introspection.table_names()))
    payload = {table: rows(source, table) for table in tables}
    target_models = [m for m in apps.get_models(include_auto_created=True) if m._meta.db_table in tables]
    with transaction.atomic():
        with target.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
            for table in PERMISSION_TABLES:
                cursor.execute(f'DELETE FROM "{table}"')
            for table in tables:
                cursor.execute(f'DELETE FROM "{table}"')
        for table, data in payload.items():
            if not data:
                report["tables"][table] = {"count": 0, "sha256": digest([]), "identity_mapping": []}
                continue
            with source.cursor() as src, target.cursor() as dst:
                src.execute(f'SELECT * FROM "{table}" LIMIT 0')
                names = [column.name for column in src.description]
                dst.execute(f'SELECT * FROM "{table}" LIMIT 0')
                if set(names) != {column.name for column in dst.description}:
                    raise RuntimeError(f"{table} 字段不匹配，拒绝遗漏字段")
                columns = ",".join(f'"{name}"' for name in names)
                with src.cursor.copy(f'COPY "{table}" ({columns}) TO STDOUT') as copy_out:
                    with dst.cursor.copy(f'COPY "{table}" ({columns}) FROM STDIN') as copy_in:
                        for block in copy_out:
                            copy_in.write(block)
            actual = rows(target, table)
            if digest(data) != digest(actual):
                raise RuntimeError(f"{table} 导入后内容不一致")
            report["tables"][table] = {"count": len(data), "sha256": digest(actual),
                                       "identity_mapping": [row["id"] for row in data if "id" in row]}
        with target.cursor() as cursor:
            for table, owner in PERMISSION_TABLES.items():
                for owner_id, permission_id in permission_links[table]:
                    cursor.execute(f'INSERT INTO "{table}" ("{owner}",permission_id) VALUES (%s,%s)',
                                   [owner_id, permission_id])
            for sql in target.ops.sequence_reset_sql(no_style(), target_models):
                cursor.execute(sql)
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        # Keep native authorization identical; record it as explicit assignment so later sync preserves it.
        from django.contrib.auth.models import Group, User
        from accounts.services.permission_assignments import (
            sync_group_permission_assignments, sync_user_permission_assignments,
        )
        for group in Group.objects.all():
            sync_group_permission_assignments(group, [], list(group.permissions.all()))
        for user in User.objects.all():
            sync_user_permission_assignments(user, [], list(user.user_permissions.all()))
        # SkillProject added default-project fields; empty source domains are deliberately not invented.
        for module_name in ("accounts.migrations.0022_remove_retired_training_mainline_bundle_codes",
                            "accounts.migrations.0023_remove_retired_role_bundle_codes"):
            module = importlib.import_module(module_name)
            with target.schema_editor() as editor:
                module.remove_retired_bundle_codes(apps, editor)
    for table in report["archives"]:
        archive = args.report.parent / f"{table}.json"
        archive.write_text(json.dumps(rows(source, table), default=str, ensure_ascii=False, indent=2), encoding="utf-8")
        archive.chmod(0o600)
    report["applied"] = True
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.chmod(0o600)
    print(json.dumps({"applied": True, "tables": len(tables), "archives": report["archives"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
