import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _metadata_dict(value):
    if isinstance(value, dict):
        return dict(value)
    return {"legacy_metadata": value}


def _snapshot_values(scoring_participant, source_participant=None):
    user = scoring_participant.user
    display_name = scoring_participant.display_name
    organization = scoring_participant.organization
    country_or_region = ""
    if source_participant is not None:
        display_name = display_name or source_participant.display_name
        organization = organization or source_participant.organization
        country_or_region = source_participant.country_or_region
    if not display_name and user is not None:
        display_name = f"{user.last_name}{user.first_name}".strip() or user.username
    return {
        "display_name": display_name or f"历史参评对象 {scoring_participant.pk}",
        "organization": organization,
        "country_or_region": country_or_region,
    }


def _append_legacy_scoring_snapshot(participant, scoring_participant):
    metadata = _metadata_dict(participant.metadata)
    history = metadata.get("legacy_scoring_participants", [])
    if not isinstance(history, list):
        metadata["legacy_scoring_participants_original"] = history
        history = []
    history.append(
        {
            "pk": scoring_participant.pk,
            "scheme_id": scoring_participant.scheme_id,
            "assessment_participant_id": scoring_participant.assessment_participant_id,
            "user_id": scoring_participant.user_id,
            "external_identifier": scoring_participant.external_identifier,
            "display_name": scoring_participant.display_name,
            "organization": scoring_participant.organization,
            "order": scoring_participant.order,
            "metadata": scoring_participant.metadata,
        }
    )
    metadata["legacy_scoring_participants"] = history
    participant.metadata = metadata
    participant.save(update_fields=["metadata"])


def migrate_scoring_results(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    AssessmentParticipant = apps.get_model("assessments", "AssessmentParticipant")
    CompetitionRole = apps.get_model("assessments", "CompetitionRole")
    ScoringParticipant = apps.get_model("scoring", "ScoringParticipant")
    ScoringResult = apps.get_model("scoring", "ScoringResult")

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

    occupied_aspects = {}
    scoring_participants = (
        ScoringParticipant.objects.using(db_alias)
        .select_related(
            "scheme__assessment_module",
            "assessment_participant__role",
            "assessment_participant__competition_person",
            "user",
        )
        .order_by("pk")
    )
    for scoring_participant in scoring_participants.iterator():
        assessment_id = scoring_participant.scheme.assessment_module.assessment_id
        source_participant = scoring_participant.assessment_participant
        source_user_id = scoring_participant.user_id or getattr(source_participant, "user_id", None)
        source_person_id = getattr(source_participant, "competition_person_id", None)
        source_external_code = scoring_participant.external_identifier or getattr(
            source_participant, "external_code", ""
        )
        snapshot = _snapshot_values(scoring_participant, source_participant)

        participant = None
        linked_source_conflict = False
        if source_participant is not None and source_participant.assessment_id == assessment_id:
            participant = source_participant
        elif source_user_id:
            participant = (
                AssessmentParticipant.objects.using(db_alias)
                .select_related("role")
                .filter(assessment_id=assessment_id, user_id=source_user_id)
                .first()
            )
        elif source_person_id:
            participant = (
                AssessmentParticipant.objects.using(db_alias)
                .select_related("role")
                .filter(assessment_id=assessment_id, competition_person_id=source_person_id)
                .first()
            )
        elif source_external_code:
            participant = (
                AssessmentParticipant.objects.using(db_alias)
                .select_related("role")
                .filter(assessment_id=assessment_id, external_code=source_external_code)
                .first()
            )

        if participant is not None and participant.role.category != "competitor":
            linked_source_conflict = True
            participant = None

        result_aspect_ids = set(
            ScoringResult.objects.using(db_alias)
            .filter(participant_id=scoring_participant.pk)
            .values_list("aspect_id", flat=True)
        )
        if participant is not None and result_aspect_ids & occupied_aspects.get(participant.pk, set()):
            linked_source_conflict = True
            participant = None

        if participant is None and not linked_source_conflict:
            create_values = {
                "assessment_id": assessment_id,
                "role_id": competitor_role.pk,
                "display_name": snapshot["display_name"],
                "organization": snapshot["organization"],
                "country_or_region": snapshot["country_or_region"],
                "metadata": {},
            }
            if source_user_id:
                create_values["user_id"] = source_user_id
            elif source_person_id:
                create_values["competition_person_id"] = source_person_id
            elif source_external_code:
                create_values["external_code"] = source_external_code
            participant = AssessmentParticipant.objects.using(db_alias).create(**create_values)

        if participant is None:
            participant = AssessmentParticipant.objects.using(db_alias).create(
                assessment_id=assessment_id,
                role_id=competitor_role.pk,
                display_name=snapshot["display_name"],
                organization=snapshot["organization"],
                country_or_region=snapshot["country_or_region"],
                metadata={
                    "scoring_migration_link_conflict": {
                        "assessment_participant_id": scoring_participant.assessment_participant_id,
                        "user_id": source_user_id,
                        "competition_person_id": source_person_id,
                        "external_identifier": source_external_code,
                    }
                },
            )

        _append_legacy_scoring_snapshot(participant, scoring_participant)
        ScoringResult.objects.using(db_alias).filter(participant_id=scoring_participant.pk).update(
            assessment_participant_id=participant.pk
        )
        occupied_aspects.setdefault(participant.pk, set()).update(result_aspect_ids)

    ScoringResult.objects.using(db_alias).filter(source="cmp").update(source="cmp_import")
    ScoringResult.objects.using(db_alias).filter(source="imported").update(source="excel_import")
    for result in ScoringResult.objects.using(db_alias).exclude(
        source__in=["online", "excel_import", "cmp_import", "manual"]
    ):
        raw_payload = _metadata_dict(result.raw_payload)
        raw_payload.setdefault("legacy_source", result.source)
        result.source = "manual"
        result.raw_payload = raw_payload
        result.save(update_fields=["source", "raw_payload"])
    ScoringResult.objects.using(db_alias).filter(entered_at__isnull=True).update(entered_at=models.F("created_at"))

    if ScoringResult.objects.using(db_alias).filter(assessment_participant__isnull=True).exists():
        raise RuntimeError("存在未能迁移到 AssessmentParticipant 的评分结果。")
    duplicate = (
        ScoringResult.objects.using(db_alias)
        .values("assessment_participant_id", "aspect_id")
        .annotate(total=models.Count("pk"))
        .filter(total__gt=1)
        .order_by("assessment_participant_id", "aspect_id")
        .first()
    )
    if duplicate:
        raise RuntimeError("迁移后仍存在重复的选手评分点结果。")
    if (
        ScoringResult.objects.using(db_alias)
        .exclude(assessment_participant__assessment_id=models.F("aspect__scheme__assessment_module__assessment_id"))
        .exists()
    ):
        raise RuntimeError("迁移后存在跨 Assessment 的评分结果。")
    if ScoringResult.objects.using(db_alias).exclude(assessment_participant__role__category="competitor").exists():
        raise RuntimeError("迁移后存在非选手类参与人员的评分结果。")


def restore_legacy_sources(apps, schema_editor):
    ScoringResult = apps.get_model("scoring", "ScoringResult")
    db_alias = schema_editor.connection.alias
    ScoringResult.objects.using(db_alias).filter(source="cmp_import").update(source="cmp")
    ScoringResult.objects.using(db_alias).filter(source="excel_import").update(source="imported")
    ScoringResult.objects.using(db_alias).filter(source="online").update(source="manual")


def restore_scoring_participants(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    AssessmentParticipant = apps.get_model("assessments", "AssessmentParticipant")
    ScoringParticipant = apps.get_model("scoring", "ScoringParticipant")
    ScoringResult = apps.get_model("scoring", "ScoringResult")

    for participant in AssessmentParticipant.objects.using(db_alias).iterator():
        metadata = _metadata_dict(participant.metadata)
        history = metadata.get("legacy_scoring_participants", [])
        if not isinstance(history, list):
            continue
        for item in history:
            scheme_id = item.get("scheme_id")
            if not scheme_id:
                continue
            ScoringParticipant.objects.using(db_alias).get_or_create(
                scheme_id=scheme_id,
                assessment_participant_id=participant.pk,
                defaults={
                    "display_name": item.get("display_name") or participant.display_name,
                    "organization": item.get("organization") or participant.organization,
                    "external_identifier": "",
                    "metadata": item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
                    "order": item.get("order") or 0,
                },
            )

    results = ScoringResult.objects.using(db_alias).select_related("assessment_participant", "aspect__scheme")
    for result in results.iterator():
        participant = result.assessment_participant
        scoring_participant, _created = ScoringParticipant.objects.using(db_alias).get_or_create(
            scheme_id=result.aspect.scheme_id,
            assessment_participant_id=participant.pk,
            defaults={
                "display_name": participant.display_name,
                "organization": participant.organization,
                "external_identifier": "",
                "metadata": {},
                "order": 0,
            },
        )
        result.participant_id = scoring_participant.pk
        result.save(update_fields=["participant"])

    if ScoringResult.objects.using(db_alias).filter(participant__isnull=True).exists():
        raise RuntimeError("无法为评分结果恢复 ScoringParticipant。")


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0002_competition_people_roles_and_assessment_times"),
        ("scoring", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="scoringresult",
            name="assessment_participant",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="assessments.assessmentparticipant",
            ),
        ),
        migrations.RenameField(model_name="scoringresult", old_name="graded_at", new_name="entered_at"),
        migrations.AddField(
            model_name="scoringresult",
            name="confirmed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="确认时间"),
        ),
        migrations.AddField(
            model_name="scoringresult",
            name="confirmed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="confirmed_scoring_results",
                to=settings.AUTH_USER_MODEL,
                verbose_name="确认人",
            ),
        ),
        migrations.AddField(
            model_name="scoringresult",
            name="entered_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="entered_scoring_results",
                to=settings.AUTH_USER_MODEL,
                verbose_name="录入人",
            ),
        ),
        migrations.AddField(
            model_name="scoringresult",
            name="updated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="updated_scoring_results",
                to=settings.AUTH_USER_MODEL,
                verbose_name="最后修改人",
            ),
        ),
        migrations.RunPython(migrate_scoring_results, restore_legacy_sources),
        migrations.RemoveConstraint(model_name="scoringresult", name="uniq_scoring_result"),
        migrations.AlterField(
            model_name="scoringresult",
            name="participant",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="results",
                to="scoring.scoringparticipant",
                verbose_name="参评对象",
            ),
        ),
        migrations.RunPython(migrations.RunPython.noop, restore_scoring_participants),
        migrations.RemoveField(model_name="scoringresult", name="participant"),
        migrations.DeleteModel(name="ScoringParticipant"),
        migrations.RenameField(
            model_name="scoringresult",
            old_name="assessment_participant",
            new_name="participant",
        ),
        migrations.AlterField(
            model_name="scoringresult",
            name="participant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="scoring_results",
                to="assessments.assessmentparticipant",
                verbose_name="评测参与人员",
            ),
        ),
        migrations.AlterField(
            model_name="scoringresult",
            name="entered_at",
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name="录入时间"),
        ),
        migrations.AlterField(
            model_name="scoringresult",
            name="source",
            field=models.CharField(
                choices=[
                    ("online", "在线评分"),
                    ("excel_import", "Excel 导入"),
                    ("cmp_import", "CMP 导入"),
                    ("manual", "人工录入"),
                ],
                default="manual",
                max_length=20,
                verbose_name="来源",
            ),
        ),
        migrations.AddConstraint(
            model_name="scoringresult",
            constraint=models.UniqueConstraint(
                fields=("participant", "aspect"),
                name="uniq_scoring_result",
            ),
        ),
        migrations.AddConstraint(
            model_name="scoringresult",
            constraint=models.CheckConstraint(
                condition=models.Q(("score_awarded__gte", 0)),
                name="scoring_result_score_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="scoringresult",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("confirmed_by__isnull", True), ("confirmed_at__isnull", True)),
                    models.Q(("confirmed_by__isnull", False), ("confirmed_at__isnull", False)),
                    _connector="OR",
                ),
                name="scoring_result_confirmation_pair",
            ),
        ),
        migrations.CreateModel(
            name="ScoringResultRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_score", models.DecimalField(decimal_places=2, max_digits=8, verbose_name="原得分")),
                ("new_score", models.DecimalField(decimal_places=2, max_digits=8, verbose_name="新得分")),
                ("changed_at", models.DateTimeField(auto_now_add=True, verbose_name="修改时间")),
                ("reason", models.CharField(blank=True, max_length=255, verbose_name="修改原因")),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="scoring_result_revisions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="修改人",
                    ),
                ),
                (
                    "scoring_result",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="revisions",
                        to="scoring.scoringresult",
                        verbose_name="评分结果",
                    ),
                ),
            ],
            options={
                "verbose_name": "评分修改记录",
                "verbose_name_plural": "评分修改记录",
                "ordering": ["-changed_at", "-pk"],
                "default_permissions": ("view",),
            },
        ),
    ]
