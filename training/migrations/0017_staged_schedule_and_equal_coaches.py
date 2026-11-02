from datetime import timedelta

from django.db import migrations, models
from django.db.models import F, Q
from django.utils import timezone


def day_filled(value):
    return bool(value.get("duty_all") or value.get("duty_coaches") or value.get("note", "").strip())


def slot_filled(value):
    return bool(
        value.get("kind", "pending") != "pending"
        or value.get("domains")
        or value.get("coaches")
        or value.get("coaches_all")
    )


def migrate_schedule_rules(apps, schema_editor):
    Plan = apps.get_model("training", "TrainingPlan")
    Day = apps.get_model("training", "TrainingScheduleDay")
    Slot = apps.get_model("training", "TrainingScheduleSlot")
    Record = apps.get_model("training", "TrainingChangeRecord")
    Change = apps.get_model("training", "TrainingScheduleChange")
    Execution = apps.get_model("training", "TaskExecution")
    Member = apps.get_model("training", "TrainingCycleMember")
    if Change.objects.filter(status="pending").exists():
        raise RuntimeError("请先处理待审申请，再升级排班规则。")
    if Slot.objects.filter(primary_coach__isnull=False).exclude(coaches=F("primary_coach")).exists():
        raise RuntimeError("存在不在负责名单中的旧主要教练，请先校对；迁移不会自动扩大授权。")
    day_ids, slot_ids = set(), set()
    for day in Day.objects.prefetch_related("duty_coaches"):
        if day.duty_all or day.note.strip() or list(day.duty_coaches.all()):
            day_ids.add(day.pk)
    for slot in Slot.objects.prefetch_related("domains", "coaches", "tasks"):
        if slot.is_configured and (
            slot.kind != "pending"
            or slot.coaches_all
            or list(slot.domains.all())
            or list(slot.coaches.all())
            or list(slot.tasks.all())
        ):
            slot_ids.add(slot.pk)
    # 只使用明确的修改快照判断曾经填写后清空，不用发布递增的 revision 猜测。
    for record in Record.objects.iterator():
        for snapshot in (record.before, record.after):
            if not isinstance(snapshot, dict):
                continue
            for item in snapshot.get("调整", []):
                if not isinstance(item, dict):
                    continue
                values = [item.get("before", {}), item.get("after", {})]
                if item.get("type") == "day" and any(day_filled(value) for value in values):
                    day_ids.add(item["id"])
                elif item.get("type") == "slot" and any(slot_filled(value) for value in values):
                    slot_ids.add(item["id"])
    Day.objects.filter(pk__in=day_ids).update(has_been_filled=True)
    Slot.objects.filter(pk__in=slot_ids).update(has_been_filled=True)
    now = timezone.now()
    for plan in Plan.objects.filter(schedule_published_at__isnull=False).prefetch_related(
        "schedule_days__duty_coaches", "schedule_days__slots__coaches", "schedule_days__slots__domains"
    ):
        coaches = set(
            Member.objects.filter(training_cycle_id=plan.training_cycle_id, role="coach").values_list(
                "user_id", flat=True
            )
        )
        dates = {plan.start_date + timedelta(days=i) for i in range((plan.end_date - plan.start_date).days + 1)}
        days = list(plan.schedule_days.all())
        complete = {day.date for day in days} == dates
        for day in days:
            duty = {person.pk for person in day.duty_coaches.all()}
            complete = complete and bool(coaches if day.duty_all else duty) and duty.issubset(coaches)
            slots = list(day.slots.all())
            complete = complete and {slot.period for slot in slots} == {"early", "morning", "afternoon", "evening"}
            for slot in slots:
                if not slot.is_configured:
                    continue
                if slot.kind in {"rest", "unused"}:
                    continue
                assigned = {person.pk for person in slot.coaches.all()}
                complete = (
                    complete
                    and slot.kind in {"technical", "general"}
                    and bool(coaches if slot.coaches_all else assigned)
                    and assigned.issubset(coaches)
                )
                if slot.kind == "technical":
                    complete = complete and bool(slot.primary_domain_id)
        if complete:
            continue
        facts = (
            Execution.objects.filter(training_task__training_plan_id=plan.pk)
            .filter(
                Q(started_at__isnull=False)
                | ~Q(status__in=["assigned", "cancelled"])
                | Q(progress_records__isnull=False)
                | Q(state_changes__isnull=False)
                | Q(feedback_records__isnull=False)
                | Q(attachments__isnull=False)
                | Q(training_logs__isnull=False)
                | Q(completed_at__isnull=False)
                | Q(actual_minutes__isnull=False)
                | ~Q(coach_feedback="")
                | ~Q(completion_note="")
                | ~Q(problems="")
                | ~Q(solution="")
                | ~Q(reflection="")
            )
            .exists()
        )
        if facts:
            raise RuntimeError(f"排班 {plan.pk} 不完整且已有执行事实，迁移已中止，不能隐藏执行数据。")
        old = plan.schedule_published_at
        Plan.objects.filter(pk=plan.pk).update(schedule_published_at=None, updated_at=now)
        Record.objects.create(
            training_plan_id=plan.pk,
            actor_id=plan.created_by_id,
            action="升级撤回不完整排班",
            reason="统一排班完整性规则升级（系统迁移执行）",
            before={"排班发布时间": old.isoformat()},
            after={"排班已发布": False},
        )


class Migration(migrations.Migration):
    dependencies = [("training", "0016_unconfigured_slot_constraint")]
    operations = [
        migrations.AddField(
            model_name="trainingscheduleday",
            name="has_been_filled",
            field=models.BooleanField(default=False, verbose_name="已首次填写"),
        ),
        migrations.AddField(
            model_name="trainingscheduleslot",
            name="has_been_filled",
            field=models.BooleanField(default=False, verbose_name="已首次填写"),
        ),
        migrations.RunPython(migrate_schedule_rules, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name="trainingtaskcoach", name="uniq_primary_coach_per_trainingtask"),
        migrations.RemoveField(model_name="trainingscheduleslot", name="primary_coach"),
        migrations.RemoveField(model_name="trainingtaskcoach", name="role"),
    ]
