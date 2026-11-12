from django.db import migrations


OWN_LOG_BUNDLES = {"training.competitor", "training.maintain_own_logs"}


def grant_current_training_log_deletion(apps, schema_editor):
    database = schema_editor.connection.alias
    permission = apps.get_model("auth", "Permission").objects.using(database).filter(
        content_type__app_label="training",
        content_type__model="traininglog",
        codename="delete_traininglog",
    ).first()
    if permission is None:
        # 新环境在 post_migrate 创建权限，之后 Bootstrap 使用最新权限包。
        return

    for model_name, owner_field, permissions_field in (
        ("GroupProfile", "group", "permissions"),
        ("UserProfile", "user", "user_permissions"),
    ):
        profiles = apps.get_model("accounts", model_name).objects.using(database).select_related(owner_field)
        for profile in profiles.iterator():
            if OWN_LOG_BUNDLES.intersection(profile.selected_permission_bundles):
                getattr(getattr(profile, owner_field), permissions_field).add(permission)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0024_userprofile_name_disambiguation"), ("training", "0025_retain_deleted_plan_publication_history")]

    # 已有的同名原生权限可能来自显式授权或其他权限包，回退时保留。
    operations = [migrations.RunPython(grant_current_training_log_deletion, migrations.RunPython.noop)]
