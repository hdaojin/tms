from django.db import migrations


OBSOLETE_TRAINING_PERMISSIONS = {
    "view_coach_traininglog",
    "view_competitor_traininglog",
}


def reset_legacy_permission_assignments(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("auth", "User")
    GroupProfile = apps.get_model("accounts", "GroupProfile")
    UserProfile = apps.get_model("accounts", "UserProfile")

    GroupProfile.objects.update(selected_permission_bundles=[])
    UserProfile.objects.update(selected_permission_bundles=[])
    GroupProfile.explicit_permissions.through.objects.all().delete()
    UserProfile.explicit_permissions.through.objects.all().delete()
    Group.permissions.through.objects.all().delete()
    User.user_permissions.through.objects.all().delete()
    Permission.objects.filter(
        content_type__app_label="training",
        codename__in=OBSOLETE_TRAINING_PERMISSIONS,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0019_groupprofile_explicit_permissions_and_more"),
        ("training", "0002_alter_traininglog_options"),
    ]

    operations = [
        migrations.RunPython(reset_legacy_permission_assignments, migrations.RunPython.noop),
    ]
