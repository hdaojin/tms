import hashlib

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


COMMON_AWARDS = {
    "金牌": ("gold", "gold", 10),
    "gold": ("gold", "gold", 10),
    "gold medal": ("gold", "gold", 10),
    "银牌": ("silver", "silver", 20),
    "silver": ("silver", "silver", 20),
    "silver medal": ("silver", "silver", 20),
    "铜牌": ("bronze", "bronze", 30),
    "bronze": ("bronze", "bronze", 30),
    "bronze medal": ("bronze", "bronze", 30),
    "优胜奖": ("excellence", "excellence", 40),
    "excellence": ("excellence", "excellence", 40),
    "medallion for excellence": ("excellence", "excellence", 40),
}


def _metadata_dict(value):
    if isinstance(value, dict):
        return dict(value)
    return {"legacy_metadata": value}


def _award_code_and_category(name):
    normalized = name.strip().casefold()
    if normalized in COMMON_AWARDS:
        return COMMON_AWARDS[normalized]
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
    return f"legacy-{digest}", "other", 999


def _get_or_create_award(AssessmentAward, db_alias, assessment_id, name):
    existing = (
        AssessmentAward.objects.using(db_alias).filter(assessment_id=assessment_id, name=name).order_by("pk").first()
    )
    if existing is not None:
        return existing

    base_code, category, order = _award_code_and_category(name)
    code = base_code
    suffix = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    counter = 1
    while AssessmentAward.objects.using(db_alias).filter(assessment_id=assessment_id, code=code).exists():
        code = f"{base_code[:40]}-{suffix[:6]}-{counter}"
        counter += 1
    return AssessmentAward.objects.using(db_alias).create(
        assessment_id=assessment_id,
        code=code,
        name=name,
        category=category,
        order=order,
        metadata={"migrated_from": "AssessmentResultSummary.award"},
    )


def migrate_final_results(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    AssessmentParticipant = apps.get_model("assessments", "AssessmentParticipant")
    CompetitionRole = apps.get_model("assessments", "CompetitionRole")
    AssessmentFinalResult = apps.get_model("assessments", "AssessmentFinalResult")
    AssessmentFinalScore = apps.get_model("assessments", "AssessmentFinalScore")
    AssessmentAward = apps.get_model("assessments", "AssessmentAward")
    AssessmentResultAward = apps.get_model("assessments", "AssessmentResultAward")

    competitor_role = (
        CompetitionRole.objects.using(db_alias)
        .filter(category="competitor", is_active=True)
        .order_by("order", "pk")
        .first()
    )
    if competitor_role is None:
        competitor_role = CompetitionRole.objects.using(db_alias).create(
            code="competitor",
            name="选手",
            category="competitor",
            order=100,
            is_active=True,
        )

    expected_score_count = AssessmentFinalResult.objects.using(db_alias).exclude(total_score__isnull=True).count()
    expected_award_count = sum(
        1
        for award_name in AssessmentFinalResult.objects.using(db_alias)
        .order_by()
        .values_list("award", flat=True)
        .iterator()
        if award_name.strip()
    )

    results = AssessmentFinalResult.objects.using(db_alias).select_related("participant__role").order_by("pk")
    for final_result in results.iterator():
        participant = final_result.participant
        if participant.assessment_id != final_result.assessment_id or participant.role.category != "competitor":
            participant_metadata = _metadata_dict(participant.metadata)
            participant_metadata.setdefault(
                "final_result_migration_link_conflict",
                {
                    "original_participant_id": participant.pk,
                    "original_assessment_id": participant.assessment_id,
                    "original_role_id": participant.role_id,
                    "target_assessment_id": final_result.assessment_id,
                    "user_id": participant.user_id,
                    "competition_person_id": participant.competition_person_id,
                    "external_code": participant.external_code,
                },
            )
            participant = AssessmentParticipant.objects.using(db_alias).create(
                assessment_id=final_result.assessment_id,
                role_id=competitor_role.pk,
                display_name=participant.display_name,
                organization=participant.organization,
                country_or_region=participant.country_or_region,
                metadata=participant_metadata,
            )
            final_result.participant_id = participant.pk

        metadata = _metadata_dict(final_result.metadata)
        metadata.setdefault(
            "legacy_result_summary",
            {
                "assessment_id": final_result.assessment_id,
                "total_score": str(final_result.total_score) if final_result.total_score is not None else None,
                "award": final_result.award,
            },
        )
        metadata.setdefault("legacy_confirmation_actor_missing", True)
        final_result.metadata = metadata
        final_result.is_official = True
        final_result.confirmed_at = final_result.updated_at or final_result.created_at
        final_result.save(update_fields=["participant", "metadata", "is_official", "confirmed_at"])

        if final_result.total_score is not None:
            AssessmentFinalScore.objects.using(db_alias).create(
                final_result_id=final_result.pk,
                score_type="raw",
                label="原始总分",
                value=final_result.total_score,
                order=10,
                metadata={"migrated_from": "AssessmentResultSummary.total_score"},
            )
        award_name = final_result.award.strip()
        if award_name:
            award = _get_or_create_award(
                AssessmentAward,
                db_alias,
                final_result.assessment_id,
                award_name,
            )
            AssessmentResultAward.objects.using(db_alias).create(
                final_result_id=final_result.pk,
                award_id=award.pk,
            )

    if AssessmentFinalScore.objects.using(db_alias).filter(score_type="raw").count() != expected_score_count:
        raise RuntimeError("旧总分未完整迁移到 AssessmentFinalScore。")
    if AssessmentResultAward.objects.using(db_alias).count() != expected_award_count:
        raise RuntimeError("旧奖项未完整迁移到 AssessmentResultAward。")
    if AssessmentFinalResult.objects.using(db_alias).exclude(participant__role__category="competitor").exists():
        raise RuntimeError("迁移后存在非选手类参与人员的最终结果。")
    if (
        AssessmentFinalResult.objects.using(db_alias)
        .exclude(participant__assessment_id=models.F("assessment_id"))
        .exists()
    ):
        raise RuntimeError("迁移后存在跨 Assessment 的最终结果。")


def restore_result_summaries(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    AssessmentFinalResult = apps.get_model("assessments", "AssessmentFinalResult")
    for final_result in (
        AssessmentFinalResult.objects.using(db_alias)
        .select_related("participant")
        .prefetch_related("scores", "award_links__award")
        .iterator(chunk_size=200)
    ):
        raw_score = final_result.scores.filter(score_type="raw").order_by("order", "pk").first()
        award_names = [link.award.name for link in final_result.award_links.all()]
        final_result.assessment_id = final_result.participant.assessment_id
        final_result.total_score = raw_score.value if raw_score is not None else None
        final_result.award = "；".join(award_names)[:100]
        final_result.save(update_fields=["assessment", "total_score", "award"])


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0002_competition_people_roles_and_assessment_times"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(old_name="AssessmentResultSummary", new_name="AssessmentFinalResult"),
        migrations.AlterModelOptions(
            name="assessmentfinalresult",
            options={
                "verbose_name": "评测最终结果",
                "verbose_name_plural": "评测最终结果",
                "ordering": ["participant__assessment", "rank", "participant__display_name", "pk"],
            },
        ),
        migrations.AddField(
            model_name="assessmentfinalresult",
            name="confirmed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="确认时间"),
        ),
        migrations.AddField(
            model_name="assessmentfinalresult",
            name="confirmed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="confirmed_assessment_final_results",
                to=settings.AUTH_USER_MODEL,
                verbose_name="确认人",
            ),
        ),
        migrations.AddField(
            model_name="assessmentfinalresult",
            name="is_official",
            field=models.BooleanField(default=False, verbose_name="官方结果"),
        ),
        migrations.AddField(
            model_name="assessmentfinalresult",
            name="notes",
            field=models.TextField(blank=True, verbose_name="备注"),
        ),
        migrations.CreateModel(
            name="AssessmentAward",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, verbose_name="奖项代码")),
                ("name", models.CharField(max_length=120, verbose_name="奖项名称")),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("gold", "金牌"),
                            ("silver", "银牌"),
                            ("bronze", "铜牌"),
                            ("excellence", "优胜奖"),
                            ("other", "其他"),
                        ],
                        default="other",
                        max_length=20,
                        verbose_name="奖项类别",
                    ),
                ),
                ("description", models.TextField(blank=True, verbose_name="说明")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("metadata", models.JSONField(blank=True, default=dict, verbose_name="元数据")),
                (
                    "assessment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="awards",
                        to="assessments.assessment",
                        verbose_name="竞赛与考核",
                    ),
                ),
            ],
            options={
                "verbose_name": "评测奖项",
                "verbose_name_plural": "评测奖项",
                "ordering": ["assessment", "order", "name", "pk"],
                "constraints": [
                    models.UniqueConstraint(fields=("assessment", "code"), name="uniq_assessment_award_code")
                ],
            },
        ),
        migrations.CreateModel(
            name="AssessmentFinalScore",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "score_type",
                    models.CharField(
                        choices=[
                            ("raw", "原始成绩"),
                            ("percentage", "百分制成绩"),
                            ("worldskills", "WorldSkills 标准化成绩"),
                            ("custom", "自定义成绩"),
                        ],
                        max_length=20,
                        verbose_name="成绩类型",
                    ),
                ),
                ("label", models.CharField(max_length=120, verbose_name="成绩名称")),
                ("value", models.DecimalField(decimal_places=4, max_digits=12, verbose_name="成绩值")),
                (
                    "max_value",
                    models.DecimalField(
                        blank=True,
                        decimal_places=4,
                        max_digits=12,
                        null=True,
                        verbose_name="参考最大值",
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("metadata", models.JSONField(blank=True, default=dict, verbose_name="元数据")),
                (
                    "final_result",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scores",
                        to="assessments.assessmentfinalresult",
                        verbose_name="最终结果",
                    ),
                ),
            ],
            options={
                "verbose_name": "评测最终成绩",
                "verbose_name_plural": "评测最终成绩",
                "ordering": ["final_result", "order", "pk"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("final_result", "score_type", "label"),
                        name="uniq_assessment_final_score_type_label",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="AssessmentResultAward",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notes", models.TextField(blank=True, verbose_name="备注")),
                (
                    "award",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="result_links",
                        to="assessments.assessmentaward",
                        verbose_name="奖项",
                    ),
                ),
                (
                    "final_result",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="award_links",
                        to="assessments.assessmentfinalresult",
                        verbose_name="最终结果",
                    ),
                ),
            ],
            options={
                "verbose_name": "最终结果奖项",
                "verbose_name_plural": "最终结果奖项",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("final_result", "award"),
                        name="uniq_assessment_result_award",
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="assessmentfinalresult",
            name="awards",
            field=models.ManyToManyField(
                blank=True,
                related_name="final_results",
                through="assessments.AssessmentResultAward",
                to="assessments.assessmentaward",
            ),
        ),
        migrations.RunPython(migrate_final_results, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="assessmentfinalresult",
            name="assessment",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="result_summaries",
                to="assessments.assessment",
                verbose_name="竞赛与考核",
            ),
        ),
        migrations.AlterField(
            model_name="assessmentfinalresult",
            name="award",
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name="奖项"),
        ),
        migrations.RunPython(migrations.RunPython.noop, restore_result_summaries),
        migrations.RemoveField(model_name="assessmentfinalresult", name="assessment"),
        migrations.RemoveField(model_name="assessmentfinalresult", name="award"),
        migrations.RemoveField(model_name="assessmentfinalresult", name="total_score"),
        migrations.AlterField(
            model_name="assessmentfinalresult",
            name="participant",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="final_result",
                to="assessments.assessmentparticipant",
                verbose_name="选手",
            ),
        ),
    ]
