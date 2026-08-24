from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0003_final_results_scores_and_awards"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="assessment",
            options={
                "verbose_name": "竞赛与考核",
                "verbose_name_plural": "竞赛与考核",
                "ordering": ["-start_date", "code"],
                "permissions": [
                    ("view_all_assessment", "查看全部竞赛与考核"),
                    ("change_all_assessment", "维护全部竞赛与考核"),
                ],
            },
        ),
    ]
