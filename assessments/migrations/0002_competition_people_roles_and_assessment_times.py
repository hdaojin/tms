from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


ROLE_SEEDS = (
    ("project_manager", "项目经理", "official", 10),
    ("skill_competition_manager", "技能竞赛经理", "official", 20),
    ("venue_manager", "场地经理", "official", 30),
    ("team_leader", "领队", "official", 40),
    ("chief_expert", "专家组长", "expert", 50),
    ("deputy_chief_expert", "副专家组长", "expert", 60),
    ("expert", "专家", "expert", 70),
    ("judge", "裁判", "expert", 80),
    ("coach", "教练", "coach", 90),
    ("competitor", "选手", "competitor", 100),
    ("staff", "工作人员", "staff", 110),
    ("observer", "观察员", "other", 120),
    ("other", "其他", "other", 999),
)

LEGACY_ROLE_NAMES = {
    "competitor": "选手",
    "expert": "专家",
    "coach": "教练",
    "staff": "工作人员",
    "observer": "观察员",
    "other": "其他",
}

LEGACY_ROLE_CATEGORIES = {
    "competitor": "competitor",
    "expert": "expert",
    "coach": "coach",
    "staff": "staff",
    "observer": "other",
    "other": "other",
}


def seed_roles_and_migrate_participants(apps, schema_editor):
    CompetitionRole = apps.get_model("assessments", "CompetitionRole")
    AssessmentParticipant = apps.get_model("assessments", "AssessmentParticipant")

    roles_by_code = {}
    for code, name, category, order in ROLE_SEEDS:
        role, _created = CompetitionRole.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "category": category,
                "order": order,
                "is_active": True,
            },
        )
        roles_by_code[code] = role

    legacy_values = AssessmentParticipant.objects.order_by().values_list("role", flat=True).distinct()
    for legacy_role in legacy_values:
        code = legacy_role or "other"
        if code not in roles_by_code:
            role, _created = CompetitionRole.objects.get_or_create(
                code=code,
                defaults={
                    "name": LEGACY_ROLE_NAMES.get(code, f"历史角色（{code}）"),
                    "category": LEGACY_ROLE_CATEGORIES.get(code, "other"),
                    "order": 900,
                    "is_active": False,
                },
            )
            roles_by_code[code] = role

    for participant in AssessmentParticipant.objects.select_related("user").iterator():
        role = roles_by_code.get(participant.role) or roles_by_code["other"]
        participant.role_config_id = role.pk
        if not participant.display_name:
            if participant.user_id:
                full_name = f"{participant.user.last_name}{participant.user.first_name}".strip()
                participant.display_name = full_name or participant.user.username
            elif participant.external_code:
                participant.display_name = participant.external_code
            else:
                participant.display_name = f"历史参与人员 {participant.pk}"
        participant.save(update_fields=["role_config", "display_name"])


def restore_legacy_participant_roles(apps, schema_editor):
    AssessmentParticipant = apps.get_model("assessments", "AssessmentParticipant")
    category_fallbacks = {
        "competitor": "competitor",
        "expert": "expert",
        "coach": "coach",
        "staff": "staff",
        "official": "other",
        "other": "other",
    }
    legacy_codes = set(LEGACY_ROLE_NAMES)
    for participant in AssessmentParticipant.objects.select_related("role_config").iterator():
        role = participant.role_config
        participant.role = role.code if role.code in legacy_codes else category_fallbacks.get(role.category, "other")
        participant.save(update_fields=["role"])


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompetitionPerson",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, verbose_name="姓名")),
                ("organization", models.CharField(blank=True, max_length=200, verbose_name="单位")),
                ("country_or_region", models.CharField(blank=True, max_length=120, verbose_name="国家或地区")),
                ("title", models.CharField(blank=True, max_length=120, verbose_name="职务")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="电子邮箱")),
                ("phone", models.CharField(blank=True, max_length=80, verbose_name="联系电话")),
                ("notes", models.TextField(blank=True, verbose_name="备注")),
                ("metadata", models.JSONField(blank=True, default=dict, verbose_name="元数据")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="最后更新时间")),
            ],
            options={
                "verbose_name": "长期赛事人员",
                "verbose_name_plural": "长期赛事人员",
                "ordering": ["name", "organization", "pk"],
            },
        ),
        migrations.CreateModel(
            name="CompetitionRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True, verbose_name="角色代码")),
                ("name", models.CharField(max_length=120, verbose_name="角色名称")),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("competitor", "选手"),
                            ("official", "赛事官员"),
                            ("expert", "专家或裁判"),
                            ("coach", "教练"),
                            ("staff", "工作人员"),
                            ("other", "其他"),
                        ],
                        max_length=20,
                        verbose_name="角色类别",
                    ),
                ),
                ("description", models.TextField(blank=True, verbose_name="说明")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
            ],
            options={
                "verbose_name": "赛事角色",
                "verbose_name_plural": "赛事角色",
                "ordering": ["order", "code", "pk"],
            },
        ),
        migrations.AddField(
            model_name="assessment",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="实际完成时间"),
        ),
        migrations.AddField(
            model_name="assessment",
            name="results_published_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="成绩发布时间"),
        ),
        migrations.AddField(
            model_name="assessment",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="实际启动时间"),
        ),
        migrations.AddField(
            model_name="assessmentmodule",
            name="scheduled_start_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="计划开始时间"),
        ),
        migrations.AddField(
            model_name="assessmentparticipant",
            name="competition_person",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assessment_participations",
                to="assessments.competitionperson",
                verbose_name="长期赛事人员",
            ),
        ),
        migrations.AddField(
            model_name="assessmentparticipant",
            name="country_or_region",
            field=models.CharField(blank=True, max_length=120, verbose_name="国家或地区"),
        ),
        migrations.AddField(
            model_name="assessmentparticipant",
            name="role_config",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="assessments.competitionrole",
            ),
        ),
        migrations.RunPython(seed_roles_and_migrate_participants, restore_legacy_participant_roles),
        migrations.RemoveField(model_name="assessmentparticipant", name="role"),
        migrations.RenameField(model_name="assessmentparticipant", old_name="role_config", new_name="role"),
        migrations.AlterField(
            model_name="assessmentparticipant",
            name="role",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="participants",
                to="assessments.competitionrole",
                verbose_name="赛事角色",
            ),
        ),
        migrations.AddConstraint(
            model_name="assessmentparticipant",
            constraint=models.UniqueConstraint(
                condition=models.Q(("competition_person__isnull", False)),
                fields=("assessment", "competition_person"),
                name="uniq_assessmentparticipant_competition_person",
            ),
        ),
        migrations.AddConstraint(
            model_name="assessmentparticipant",
            constraint=models.CheckConstraint(
                condition=models.Q(("user__isnull", True), ("competition_person__isnull", True), _connector="OR"),
                name="assessmentparticipant_single_linked_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="assessmentparticipant",
            constraint=models.CheckConstraint(
                condition=models.Q(("display_name", ""), _negated=True),
                name="assessmentparticipant_display_name_required",
            ),
        ),
    ]
