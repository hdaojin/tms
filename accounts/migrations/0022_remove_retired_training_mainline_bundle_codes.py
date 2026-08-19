from django.db import migrations


RETIRED_BUNDLE_CODES = {
    "training.view_cycles",
    "training.manage_cycles",
    "training.submit_logs",
    "events.view_event_catalog",
    "events.view_event_participants",
    "events.maintain_event",
    "examcontent.view_examcontent",
    "examcontent.maintain_examcontent",
    "knowledge.view_knowledge",
    "knowledge.maintain_knowledge",
    "archives.view_archive",
    "archives.maintain_archive",
}


def remove_retired_bundle_codes(apps, schema_editor):
    GroupProfile = apps.get_model("accounts", "GroupProfile")
    UserProfile = apps.get_model("accounts", "UserProfile")

    for model in (GroupProfile, UserProfile):
        for profile in model.objects.iterator():
            current = profile.selected_permission_bundles or []
            retained = [code for code in current if code not in RETIRED_BUNDLE_CODES]
            if retained != current:
                profile.selected_permission_bundles = retained
                profile.save(update_fields=["selected_permission_bundles"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0021_drop_retired_ai_schema"),
    ]

    operations = [
        migrations.RunPython(remove_retired_bundle_codes, migrations.RunPython.noop),
    ]
