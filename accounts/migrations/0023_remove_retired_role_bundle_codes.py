from django.db import migrations


RETIRED_BUNDLE_CODES = {
    "standards.maintain_standard",
    "training.coach",
    "training.project_admin",
}


def remove_retired_bundle_codes(apps, schema_editor):
    GroupProfile = apps.get_model("accounts", "GroupProfile")
    UserProfile = apps.get_model("accounts", "UserProfile")
    database = schema_editor.connection.alias if schema_editor else "default"

    for model in (GroupProfile, UserProfile):
        for profile in model.objects.using(database).iterator():
            current = profile.selected_permission_bundles or []
            retained = [code for code in current if code not in RETIRED_BUNDLE_CODES]
            if retained != current:
                profile.selected_permission_bundles = retained
                profile.save(update_fields=["selected_permission_bundles"], using=database)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0022_remove_retired_training_mainline_bundle_codes"),
    ]

    operations = [
        migrations.RunPython(remove_retired_bundle_codes, migrations.RunPython.noop),
    ]
