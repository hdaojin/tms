from django.db import migrations


RETIRED_AI_TABLES = (
    "accounts_useraimodelcredential",
    "accounts_aiprovider",
)


def drop_retired_ai_schema(apps, schema_editor):
    """Remove tables left behind when the retired AI integration was removed."""
    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())

    for table_name in RETIRED_AI_TABLES:
        if table_name not in existing_tables:
            continue
        schema_editor.execute(
            f"DROP TABLE {connection.ops.quote_name(table_name)}"
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("accounts", "0020_reset_legacy_permission_assignments"),
    ]

    operations = [
        migrations.RunPython(drop_retired_ai_schema, migrations.RunPython.noop),
    ]
