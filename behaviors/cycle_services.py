import json
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.db import transaction
from django.utils import timezone

from training.models import TrainingCycle
from .permissions import can_manage_catalog
from .models import (
    ConductCategory, ConductCycleAssignment, ConductItem, ConductNature, ConductPolicy,
    ConductPolicyItem, ConductPolicyRule, ConductRecord,
)


PERMISSIONS = {
    'enter': 'behaviors.add_conduct_record',
    'review': 'behaviors.review_conduct_record',
    'write': 'behaviors.change_conductpolicy',
    'publish': 'behaviors.publish_conductpolicy',
}


def cycle_scope(actor, capability):
    cycles = TrainingCycle.objects.all()
    if actor.is_active and actor.is_superuser:
        return cycles
    if not actor.is_active or not actor.has_perm(PERMISSIONS[capability]):
        return cycles.none()
    assignments = ConductCycleAssignment.objects.filter(
        user=actor, **{f'can_{capability}': True},
    )
    return cycles.filter(pk__in=assignments.values('cycle_id'))


def require_cycle(actor, capability, cycle_id):
    if not cycle_scope(actor, capability).filter(pk=cycle_id).exists():
        raise PermissionDenied


def student_cycles(actor):
    return TrainingCycle.objects.filter(members__user=actor, members__role='competitor')


def active_policy(cycle, date):
    return ConductPolicy.objects.filter(
        cycle=cycle, published_at__isnull=False, effective_date__lte=date,
    ).first()


@transaction.atomic
def publish_policy(actor, policy, revision):
    TrainingCycle.objects.select_for_update().get(pk=policy.cycle_id)
    policy = ConductPolicy.objects.select_for_update().get(pk=policy.pk)
    require_cycle(actor, 'publish', policy.cycle_id)
    if policy.published_at or policy.updated_at.isoformat() != revision:
        raise ValidationError('草稿已变更，请重新预览后发布。')
    if ConductPolicy.objects.filter(
        cycle_id=policy.cycle_id, published_at__isnull=False, effective_date__gte=policy.effective_date,
    ).exists():
        raise ValidationError('新版生效日期必须晚于本周期所有已发布版本。')
    if policy.effective_date < timezone.localdate():
        raise ValidationError('生效日期不能早于发布当天。')
    rules = list(policy.rules.select_related('policy_item__item__category'))
    if not rules:
        raise ValidationError('请至少配置一条计分分档。')
    groups = list(policy.policy_items.select_related('item__category'))
    if {group.pk for group in groups} != {rule.policy_item_id for rule in rules}:
        raise ValidationError('请为每个条例事项至少配置一个分档。')
    now = timezone.now()
    for group in groups:
        group.full_clean()
        if not group.item.is_active or not group.item.category.is_active:
            raise ValidationError(f'奖惩事项「{group.item.name}」已停用。')
    for rule in rules:
        rule.full_clean()
        item = rule.policy_item.item
        rule.item_label = item.name
        rule.category_label = item.category.name
        rule.updated_at = now
        rule.updated_by = actor
    policy.rules.bulk_update(rules, ['item_label', 'category_label', 'updated_at', 'updated_by'])
    policy.published_at = now
    policy.published_by = policy.updated_by = actor
    policy.save(update_fields=['published_at', 'published_by', 'updated_by', 'updated_at'])


@transaction.atomic
def review_record(actor, record, action, note, revision):
    if record.cycle_id:
        TrainingCycle.objects.select_for_update().get(pk=record.cycle_id)
        require_cycle(actor, 'review', record.cycle_id)
    elif not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    record = ConductRecord.objects.select_for_update().get(pk=record.pk)
    if record.updated_at.isoformat() != revision:
        raise ValidationError('记录已变更，请重新打开详情。')
    status = ConductRecord.Status
    if action in {'approve', 'reject'} and record.status == status.PENDING:
        if action == 'reject' and not note:
            raise ValidationError('请填写驳回原因。')
        record.status = status.APPROVED if action == 'approve' else status.REJECTED
        record.reviewed_by, record.reviewed_at, record.review_note = actor, timezone.now(), note
    elif action == 'void' and record.cycle_id and record.status == status.APPROVED:
        if not note:
            raise ValidationError('请填写作废原因。')
        record.status = status.VOID
        record.voided_by, record.voided_at, record.void_note = actor, timezone.now(), note
    else:
        raise ValidationError('当前状态不支持该操作。')
    record.updated_by = actor
    record.save()


@transaction.atomic
def create_elite_draft(actor, cycle_id):
    cycle = TrainingCycle.objects.select_for_update().get(pk=cycle_id)
    require_cycle(actor, 'write', cycle.pk)
    if ConductPolicy.objects.filter(cycle=cycle).exists():
        raise ValidationError('本周期已有条例版本，请使用新建或复制草稿。')
    source = json.loads(Path(__file__).with_name('elite_class_policy.json').read_text(encoding='utf-8'))
    policy = ConductPolicy.objects.create(
        cycle=cycle, title=source['title'], issuer=source['issuer'], body=source['body'],
        effective_date=timezone.localdate(), created_by=actor, updated_by=actor,
    )
    groups = {}
    for index, row in enumerate(source['rules'], start=1):
        points = Decimal(row['points'])
        nature = ConductNature.REWARD if points > 0 else ConductNature.PENALTY
        key = (nature, row['category'], row['item'])
        group = groups.get(key)
        if group is None:
            category = ConductCategory.objects.filter(nature=nature, name=row['category']).first()
            if category is None:
                if not can_manage_catalog(actor):
                    raise ValidationError('模板包含尚未建立的分类，请联系全局配置维护人。')
                category, _ = ConductCategory.objects.get_or_create(
                    nature=nature, name=row['category'],
                    defaults={'code': f'elite-{uuid4().hex}', 'created_by': actor, 'updated_by': actor},
                )
            item = ConductItem.objects.filter(category=category, name=row['item']).first()
            if item is None:
                if not can_manage_catalog(actor):
                    raise ValidationError('模板包含尚未建立的事项，请联系全局配置维护人。')
                item, _ = ConductItem.objects.get_or_create(
                    category=category, name=row['item'],
                    defaults={
                        'code': f'elite-{uuid4().hex}',
                        'default_score': Decimal(1) if nature == ConductNature.REWARD else Decimal(-1),
                        'created_by': actor, 'updated_by': actor,
                    },
                )
            if not (item.is_active and category.is_active):
                raise ValidationError(f'模板使用的事项「{item.name}」已停用。')
            matching = [
                Decimal(option['points']) for option in source['rules']
                if option['category'] == row['category'] and option['item'] == row['item']
            ]
            base = item.default_score
            if not base or not all(
                (rate := amount / base) == rate.quantize(Decimal('0.01')) and 0 <= rate <= Decimal('999999.99')
                for amount in matching
            ):
                base = Decimal(1) if nature == ConductNature.REWARD else Decimal(-1)
            group = ConductPolicyItem.objects.create(
                policy=policy, item=item, base_score=base, created_by=actor, updated_by=actor,
            )
            groups[key] = group
        rule = ConductPolicyRule(
            policy_item=group, section=row['section'], condition=row['condition'],
            multiplier=points / group.base_score, unit=row['unit'], order=index, created_by=actor, updated_by=actor,
        )
        rule.full_clean()
        rule.save()
    return policy


def save_entry(actor, cycle, data, record, key):
    stored = []
    try:
        with transaction.atomic():
            TrainingCycle.objects.select_for_update().get(pk=cycle.pk)
            require_cycle(actor, 'enter', cycle.pk)
            if record:
                record = ConductRecord.objects.select_for_update().get(pk=record.pk)
                if record.cycle_id != cycle.pk or record.recorded_by_id != actor.pk:
                    raise PermissionDenied
                if record.rule.policy_item.policy_id != data['rule'].policy_item.policy_id:
                    raise ValidationError('待审记录必须沿用原条例版本。')
                if record.status != ConductRecord.Status.PENDING or record.updated_at.isoformat() != data['revision']:
                    raise ValidationError('记录已变更，请重新打开。')
                records = [record]
            else:
                previous = ConductRecord.objects.filter(cycle=cycle, recorded_by=actor, submission_key=key).first()
                if previous:
                    return previous
                policy = active_policy(cycle, data['occurred_date'])
                if not policy or policy.pk != data['rule'].policy_item.policy_id:
                    raise ValidationError('适用条例已变更，请重新预览。')
                ids = [student.pk for student in data['students']]
                if _eligible_student_ids(cycle, ids) != set(ids):
                    raise ValidationError('所选学员已变更，请重新选择。')
                records = [
                    ConductRecord(
                        cycle=cycle, student=student, occurred_date=data['occurred_date'], recorded_by=actor,
                        submission_key=key,
                    ) for student in data['students']
                ]
            for obj in records:
                rule = data['rule']
                obj.rule = rule
                obj.item = rule.policy_item.item
                obj.severity = rule.severity
                obj.category_label = rule.category_label
                obj.item_label = rule.item_label
                obj.severity_label = rule.condition
                obj.frozen_nature = obj.item.category.nature
                obj.quantity = data['quantity']
                obj.frozen_points = rule.points * obj.quantity
                obj.reason = data['reason']
                obj.updated_by = actor
                if upload := data['attachment']:
                    upload.seek(0)
                    obj.attachment.save(upload.name, File(upload), save=False)
                    stored.append((obj.attachment.storage, obj.attachment.name))
                obj.save()
            return records[0]
    except Exception:
        for storage, name in stored:
            storage.delete(name)
        raise


def _eligible_student_ids(cycle, ids):
    return set(cycle.members.filter(role='competitor', user__is_active=True, user_id__in=ids).values_list('user_id', flat=True))
