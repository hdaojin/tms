from collections import defaultdict
from decimal import Decimal

from django.db import migrations


BATCH = 500
RATE_LIMIT = Decimal('999999.99')
CENT = Decimal('0.01')


def freeze_legacy_records(records, severity_rules):
    rules = {
        (nature, severity): (label, rate)
        for nature, severity, label, rate in severity_rules.values_list(
            'nature', 'severity_id', 'label', 'multiplier',
        )
    }
    fields = ['frozen_nature', 'frozen_points', 'category_label', 'item_label', 'severity_label']
    batch = []
    for record in records.select_related('item__category', 'severity').iterator(chunk_size=BATCH):
        category = record.item.category
        if record.frozen_points is None:
            record.frozen_nature = category.nature
        nature = record.frozen_nature
        label, rate = rules.get(
            (nature, record.severity_id),
            (record.severity.name if record.severity_id else '', Decimal(0) if record.severity_id else Decimal(1)),
        )
        if record.frozen_points is None:
            record.frozen_points = record.item.default_score * rate
        record.category_label = category.name
        record.item_label = record.item.name
        record.severity_label = label
        batch.append(record)
        if len(batch) == BATCH:
            records.bulk_update(batch, fields)
            batch.clear()
    records.bulk_update(batch, fields)


def merge_catalog(categories, items, rules, records):
    grouped = defaultdict(list)
    for category in categories.order_by('pk'):
        grouped[category.nature, category.name].append(category)

    for group in grouped.values():
        group.sort(key=lambda category: (category.cycle_id is not None, category.pk))
        target, *duplicates = group
        names = {item.name: item.pk for item in items.filter(category=target)}
        codes = set(items.filter(category=target).values_list('code', flat=True))
        for duplicate in duplicates:
            for item in items.filter(category=duplicate).order_by('pk'):
                if item.name in names:
                    rules.filter(item=item).update(item_id=names[item.name])
                    records.filter(item=item).update(item_id=names[item.name])
                    item.delete()
                    continue
                code = item.code
                if code in codes:
                    stem = f'{item.code[:30]}-merged-{item.pk}'
                    code = stem
                    suffix = 2
                    while code in codes:
                        code = f'{stem}-{suffix}'
                        suffix += 1
                items.filter(pk=item.pk).update(category=target, code=code)
                names[item.name] = item.pk
                codes.add(code)
            duplicate.delete()
        if target.cycle_id is not None:
            categories.filter(pk=target.pk).update(cycle=None)


def convert_policy_rules(rules, policy_items):
    groups = defaultdict(list)
    for rule in rules.select_related('policy', 'item__category').order_by('pk'):
        groups[rule.policy_id, rule.item_id].append(rule)
    for (policy_id, item_id), group in groups.items():
        first = group[0]
        nature = first.item.category.nature
        base = first.item.default_score
        sign = Decimal(1) if nature == 'REWARD' else Decimal(-1)
        if not (
            base * sign > 0
            and all(
                (rate := rule.points / base) == rate.quantize(CENT) and 0 <= rate <= RATE_LIMIT
                for rule in group
            )
        ):
            base = sign
        policy_item = policy_items.create(
            policy_id=policy_id, item_id=item_id, base_score=base,
            created_by_id=first.created_by_id, updated_by_id=first.updated_by_id,
        )
        for rule in group:
            rate = (rule.points / base).quantize(CENT)
            if not 0 <= rate <= RATE_LIMIT or base * rate != rule.points:
                raise RuntimeError(f'条例计分分档 {rule.pk} 无法按原分值转换。')
            rule.policy_item_id = policy_item.pk
            rule.multiplier = rate
        rules.bulk_update(group, ['policy_item', 'multiplier'], batch_size=BATCH)


def copy_cycle_records(records, cycle_records):
    batch = []
    dates = []

    def save_batch():
        records.bulk_create(batch)
        for record, (created_at, updated_at) in zip(batch, dates, strict=True):
            record.recorded_at = created_at
            record.updated_at = updated_at
        records.bulk_update(batch, ['recorded_at', 'updated_at'])
        batch.clear()
        dates.clear()

    for old in cycle_records.select_related('rule__item__category').iterator(chunk_size=BATCH):
        rule = old.rule
        batch.append(records.model(
            source_cycle_record_id=old.pk, cycle_id=old.cycle_id, student_id=old.student_id,
            item_id=rule.item_id, rule_id=old.rule_id, occurred_date=old.occurred_date,
            submission_key=old.submission_key, quantity=old.quantity, frozen_points=old.points,
            frozen_nature=rule.item.category.nature, category_label=rule.category_label,
            item_label=rule.item_label, severity_label=rule.condition,
            reason=old.reason, attachment=old.attachment.name, status=old.status.upper(),
            recorded_by_id=old.created_by_id, updated_by_id=old.updated_by_id,
            reviewed_by_id=old.reviewed_by_id, reviewed_at=old.reviewed_at, review_note=old.review_note,
            voided_by_id=old.voided_by_id, voided_at=old.voided_at, void_note=old.void_note,
        ))
        dates.append((old.created_at, old.updated_at))
        if len(batch) == BATCH:
            save_batch()
    if batch:
        save_batch()


def forwards(apps, schema_editor):
    alias = schema_editor.connection.alias

    def table(name):
        return apps.get_model('behaviors', name).objects.using(alias)

    records = table('ConductRecord')
    cycle_records = table('CycleConductRecord')
    rules = table('ConductPolicyRule')
    old_count = records.count()
    cycle_count = cycle_records.count()
    for rule in rules.select_related('item__category').iterator(chunk_size=BATCH):
        if not rule.item_label or not rule.category_label:
            rules.filter(pk=rule.pk).update(
                item_label=rule.item_label or rule.item.name,
                category_label=rule.category_label or rule.item.category.name,
            )
    freeze_legacy_records(records, table('ConductSeverityRule'))
    merge_catalog(table('ConductCategory'), table('ConductItem'), rules, records)
    convert_policy_rules(rules, table('ConductPolicyItem'))
    copy_cycle_records(records, cycle_records)
    if records.count() != old_count + cycle_count or records.filter(frozen_points__isnull=True).exists():
        raise RuntimeError('奖惩账本迁移校验失败。')


def backwards(apps, schema_editor):
    """Rebuild the earlier schema's facts. Use a backup to undo catalog deduplication."""
    alias = schema_editor.connection.alias
    rules = apps.get_model('behaviors', 'ConductPolicyRule').objects.using(alias)
    records = apps.get_model('behaviors', 'ConductRecord').objects.using(alias)
    cycle_records = apps.get_model('behaviors', 'CycleConductRecord').objects.using(alias)
    for rule in rules.select_related('policy_item').iterator(chunk_size=BATCH):
        if not rule.policy_item_id:
            continue
        group = rule.policy_item
        rules.filter(pk=rule.pk).update(
            item_id=group.item_id, policy_id=group.policy_id, points=group.base_score * rule.multiplier,
        )
    assigned = records.exclude(cycle_id=None)
    for record in assigned.order_by('source_cycle_record_id', 'pk').iterator(chunk_size=BATCH):
        old = cycle_records.create(
            pk=record.source_cycle_record_id or record.pk, cycle_id=record.cycle_id,
            student_id=record.student_id, rule_id=record.rule_id, occurred_date=record.occurred_date,
            submission_key=record.submission_key, quantity=record.quantity, points=record.frozen_points,
            reason=record.reason, attachment=record.attachment.name or '', status=record.status.lower(),
            created_by_id=record.recorded_by_id, updated_by_id=record.updated_by_id,
            reviewed_by_id=record.reviewed_by_id, reviewed_at=record.reviewed_at, review_note=record.review_note,
            voided_by_id=record.voided_by_id, voided_at=record.voided_at, void_note=record.void_note,
        )
        cycle_records.filter(pk=old.pk).update(created_at=record.recorded_at, updated_at=record.updated_at)
    assigned.delete()


class Migration(migrations.Migration):
    dependencies = [('behaviors', '0022_unify_conduct_ledger')]
    operations = [migrations.RunPython(forwards, backwards)]
