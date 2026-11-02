"""显式补录旧计划缺失的时间快照；预览后由管理员确认。"""

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from training.models import TrainingPlan, TrainingScheduleDay, TrainingScheduleSlot
from training.scheduling import audit


class Command(BaseCommand):
    help = "预览旧计划缺失的时间快照；--confirm 使用明确配置补录，不伪称为历史原始时间。"

    def add_arguments(self, parser):
        parser.add_argument("plan", type=int)
        parser.add_argument("--actor", type=int, required=True, help="记录此次补录的有效超级管理员用户 ID")
        parser.add_argument("--confirm", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        plan = TrainingPlan.objects.select_for_update().filter(pk=options["plan"]).first()
        actor = get_user_model().objects.filter(pk=options["actor"], is_active=True, is_superuser=True).first()
        if not plan or not actor:
            raise CommandError("计划不存在，或操作者不是有效超级管理员。")
        try:
            from types import SimpleNamespace
            if any(getattr(plan, name) is None for name in TrainingPlan.TIME_FIELDS):
                raise ValidationError("请先在该计划表单完整配置四个时段时间。")
            plan.full_clean()
            configs = {period: SimpleNamespace(start_time=getattr(plan, f"{period}_start"), end_time=getattr(plan, f"{period}_end"), get_period_display=lambda label=label: label) for period, label in TrainingScheduleSlot.Period.choices}
        except ValidationError as exc:
            raise CommandError("；".join(exc.messages)) from exc
        existing = {
            (slot.day.date, slot.period): slot
            for slot in TrainingScheduleSlot.objects.select_for_update()
            .filter(day__training_plan=plan)
            .select_related("day")
        }
        missing = []
        when = plan.start_date
        while when <= plan.end_date:
            for period in TrainingScheduleSlot.Period.values:
                slot = existing.get((when, period))
                if slot is None or slot.ends_at is None:
                    missing.append((when, period, slot))
            when += timedelta(days=1)
        self.stdout.write(f"计划 {plan.pk}：待补录 {len(missing)} 个时段。采用当前管理员配置，历史真实时间仍不可追溯。")
        for period, config in configs.items():
            self.stdout.write(f"{config.get_period_display()}：{config.start_time}–{config.end_time}")
        if not options["confirm"]:
            self.stdout.write("仅预览；确认后使用相同参数并增加 --confirm。")
            return
        values = []
        for when, period, slot in missing:
            if slot is None:
                day, _ = TrainingScheduleDay.objects.get_or_create(training_plan=plan, date=when)
                slot = TrainingScheduleSlot(day=day, period=period)
            config = configs[period]
            slot.starts_at = timezone.make_aware(
                datetime.combine(slot.day.date, config.start_time), timezone.get_default_timezone()
            )
            slot.ends_at = timezone.make_aware(
                datetime.combine(slot.day.date, config.end_time), timezone.get_default_timezone()
            )
            slot.revision += 1
            if slot.pk:
                slot.save(update_fields=["starts_at", "ends_at", "revision", "updated_at"])
            else:
                slot.save()
            values.append({"时段": slot.pk, "开始": slot.starts_at.isoformat(), "结束": slot.ends_at.isoformat()})
        if values:
            audit(
                plan,
                actor,
                "补录历史时间快照",
                after={"补录": values},
                reason="原计划无时间快照，采用管理员明确配置补录；不代表历史真实时间。",
            )
        self.stdout.write(self.style.SUCCESS(f"已补录 {len(values)} 个时段；已有快照未更改。"))
