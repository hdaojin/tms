from __future__ import annotations

from django.db import migrations


OLD_APP_LABELS = (
    "competition_standards",
    "skilltrees",
    "marking",
    "competitions",
    "assessments",
    "traininglogs",
    "standards",
    "archives",
    "events",
    "knowledge",
)


OLD_TABLES = (
    "marking_markingresult",
    "marking_markingparticipant",
    "marking_markingresultimport",
    "marking_judgementoption",
    "marking_markingaspectskillnodemap",
    "marking_markingaspect",
    "marking_markingsubcriterion",
    "marking_markingscheme",
    "marking_markingschemeimport",
    "skilltrees_skillnode",
    "skilltrees_skilltree",
    "assessments_assessment_participants",
    "assessments_assessmentattachment",
    "assessments_assessmentmodule",
    "assessments_assessment",
    "traininglogs_traininglogdraft",
    "traininglogs_traininglog",
    "competitions_competitionresult",
    "competitions_skillposition",
    "competitions_expert",
    "competitions_competitor",
    "competitions_competitionprojectmember",
    "competitions_competitionmoduleaxismap",
    "competitions_competitionmodulestandardmodulemap",
    "competitions_competitionmodule",
    "competitions_competitiontrainingcycletarget",
    "competitions_competitionperson",
    "competitions_member",
    "competitions_competitionproject",
    "competitions_competition",
    "competition_standards_standardmoduleaxismap",
    "competition_standards_standardmodule",
    "competition_standards_moduleaxis",
    "competition_standards_trainingcycle",
    "competition_standards_standardmoduleset",
    "competition_standards_project",
    "competition_standards_competitiontype",
    "knowledge_knowledgeevidenceskillmap",
    "knowledge_knowledgeevidence",
    "events_eventresultsummary",
    "events_eventparticipant",
    "events_eventmodule",
    "events_event",
    "archives_archiveasset",
    "standards_skillnodeproposal",
    "standards_skillnodealias",
    "standards_skillnode",
    "standards_skilltree",
    "standards_standardmodule",
    "standards_standardmoduleset",
    "standards_standardproject",
    "standards_competitiontype",
)


def _drop_table(cursor, connection, table_name):
    quoted = connection.ops.quote_name(table_name)
    if connection.vendor == "postgresql":
        cursor.execute(f"DROP TABLE IF EXISTS {quoted} CASCADE")
    else:
        cursor.execute(f"DROP TABLE IF EXISTS {quoted}")


def retire_legacy_standard_stack(apps, schema_editor):
    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())
    ContentType = apps.get_model("contenttypes", "ContentType")

    with connection.cursor() as cursor:
        if connection.vendor == "mysql":
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        elif connection.vendor == "sqlite":
            cursor.execute("PRAGMA foreign_keys=OFF")

        for table_name in OLD_TABLES:
            if table_name in existing_tables:
                _drop_table(cursor, connection, table_name)

        cursor.execute(
            "DELETE FROM django_migrations WHERE app IN (%s)"
            % ",".join(["%s"] * len(OLD_APP_LABELS)),
            OLD_APP_LABELS,
        )

        if connection.vendor == "mysql":
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        elif connection.vendor == "sqlite":
            cursor.execute("PRAGMA foreign_keys=ON")

    ContentType.objects.filter(app_label__in=OLD_APP_LABELS).delete()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("core", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(retire_legacy_standard_stack, migrations.RunPython.noop),
    ]
