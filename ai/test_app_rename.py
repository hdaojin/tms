from datetime import date
from io import StringIO

import pytest
from cryptography.fernet import Fernet
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.exceptions import InconsistentMigrationHistory
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

from accounts.models import GroupProfile, UserProfile
from standards.models import SkillProject
from training.models import TrainingCycle, TrainingLogDraft, TrainingLogGeneration

from .models import AIModel, AIModelPreference

pytestmark = pytest.mark.django_db(transaction=True)
LEGACY_HEAD = ("ai", "0005_model_share_audience")


def test_app_rename_preserves_rows_and_grants(settings, django_user_model):
    if connection.vendor not in {"postgresql", "sqlite"}:
        pytest.skip("仅覆盖 PostgreSQL 和 SQLite")
    settings.AI_MODEL_ENCRYPTION_KEY = Fernet.generate_key()
    user = django_user_model.objects.create_user("rename-rehearsal")
    group = Group.objects.create(name="改名演练")
    user.groups.add(group)
    profile = UserProfile.objects.create(
        user=user, selected_permission_bundles=["unrelated", "ai_models.manage_own", "ai.manage_own"]
    )
    GroupProfile.objects.update_or_create(group=group, defaults={"selected_permission_bundles": ["ai_models.use_shared"]})
    content_type = ContentType.objects.get_for_model(AIModel)
    permission = Permission.objects.get(content_type=content_type, codename="view_aimodel")
    user.user_permissions.add(permission)
    group.permissions.add(permission)
    encrypted = Fernet(settings.AI_MODEL_ENCRYPTION_KEY).encrypt(b"synthetic-rehearsal-key")
    model = AIModel.objects.create(
        owner=user, name="已有模型", provider="deepseek", base_url="https://api.deepseek.com",
        model_id="deepseek-flash", encrypted_api_key=encrypted, verified=True, is_shared=True, share_audience="selected",
    )
    model.shared_users.add(user)
    model.shared_groups.add(group)
    preference = AIModelPreference.objects.create(user=user, model=model)

    project = SkillProject.objects.create(code="RENAME", name="演练项目")
    cycle = TrainingCycle.objects.create(skill_project=project, code="RENAME", name="演练周期", start_date=date(2026, 1, 1))
    draft = TrainingLogDraft.objects.create(author=user, cycle=cycle, training_date=cycle.start_date)
    job = TrainingLogGeneration.objects.create(
        draft=draft, model=model, model_revision=model.revision, thinking="disabled", status="ready",
    )

    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    executor.migrate([LEGACY_HEAD])
    state = executor.loader.project_state()
    # Convert the pre-feature schema to the legacy identity. Table DDL and constraints come from the real migrations.
    metadata = [state.apps.get_model("ai", name)._meta for name in (
        "AIModel", "AIModelOption", "AIModelPreference", "AIProviderSettings",
    )]
    assert connection.introspection.table_names() and "ai_models_aimodel" not in connection.introspection.table_names()
    metadata += [AIModel.shared_users.through._meta, AIModel.shared_groups.through._meta]
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        for meta in metadata:
            table = meta.db_table
            cursor.execute(f"ALTER TABLE {quote(table)} RENAME TO {quote('ai_models_' + table.removeprefix('ai_'))}")
        cursor.execute("UPDATE django_migrations SET app = 'ai_models' WHERE app = 'ai'")
    ContentType.objects.filter(app_label="ai").update(app_label="ai_models")
    try:
        with pytest.raises(InconsistentMigrationHistory, match=r"training\.0026.*ai\.0004"):
            call_command("migrate", "--plan", stdout=StringIO())
        with pytest.raises(CommandError, match="加密"):
            with settings_override_key():
                call_command("migrate_ai_app_label", "--apply", stdout=StringIO())
        call_command("migrate_ai_app_label", "--dry-run", stdout=StringIO())
        assert any(app == "ai_models" for app, _ in MigrationRecorder(connection).applied_migrations())
    finally:
        call_command("migrate_ai_app_label", "--apply", stdout=StringIO())
        MigrationExecutor(connection).migrate(latest)
    call_command("migrate_ai_app_label", "--dry-run", stdout=StringIO())
    plan = StringIO()
    call_command("migrate", "--plan", stdout=plan)
    assert "No planned migration operations." in plan.getvalue()
    migrated = AIModel.objects.get(pk=model.pk)
    assert TrainingLogGeneration.objects.get(pk=job.pk).model_id == model.pk
    assert bytes(migrated.encrypted_api_key) == encrypted
    assert migrated.revision == model.revision
    assert migrated.shared_users.get().pk == user.pk and migrated.shared_groups.get().pk == group.pk
    assert AIModelPreference.objects.get(pk=preference.pk).model_id == model.pk
    assert ContentType.objects.get(app_label="ai", model="aimodel").pk == content_type.pk
    assert user.user_permissions.get(codename="view_aimodel").pk == permission.pk
    assert group.permissions.get(codename="view_aimodel").pk == permission.pk
    profile.refresh_from_db()
    assert profile.selected_permission_bundles == ["unrelated", "ai.manage_own"]
    assert GroupProfile.objects.get(group=group).selected_permission_bundles == ["ai.use_shared"]


def settings_override_key():
    from django.test import override_settings

    return override_settings(AI_MODEL_ENCRYPTION_KEY="")
