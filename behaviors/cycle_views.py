from uuid import uuid4

import nh3
from django import forms
from django.contrib import messages
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST, require_safe, require_http_methods

from core.utils.breadcrumbs import breadcrumb_link, build_breadcrumbs
from core.utils.markdown import render_markdown_text
from training.models import TrainingCycle
from .cycle_forms import AssignmentForm, EntryDateForm, EntryForm, PolicyForm, PolicyItemForm, RuleForm
from .cycle_services import (
    PERMISSIONS, active_policy, create_elite_draft, cycle_scope, publish_policy, require_cycle, review_record,
    save_entry, student_cycles,
)
from .models import ConductCycleAssignment, ConductPolicy, ConductPolicyItem, ConductPolicyRule, ConductRecord
from .selectors import visible_records, policy_cycles
from .views import find_old_cycle_record, ledger_record



MARKDOWN = nh3.Cleaner(
    tags={'p', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'strong', 'em', 'blockquote',
          'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a', 'br', 'code', 'pre'},
    attributes={'a': {'href'}, 'h2': {'id'}, 'h3': {'id'}, 'h4': {'id'}, 'h5': {'id'}, 'h6': {'id'}},
    url_schemes={'https', 'http'},
)


def page(request, template, title, *, parents=(), **context):
    return render(request, f'behaviors/cycle_{template}.html', {
        'title': title, 'wrap_title': True, 'breadcrumbs': build_breadcrumbs(request, title, parents), **context,
    })


def policy_parents(cycle=None, policy=None):
    parents = [breadcrumb_link('班级条例', 'behaviors:policy_index')]
    if cycle:
        parents.append(breadcrumb_link(str(cycle), 'behaviors:cycle_policies', args=[cycle.pk]))
    if policy:
        parents.append(breadcrumb_link(policy.title, 'behaviors:cycle_policy', args=[cycle.pk, policy.pk]))
    return parents


def record_parents():
    return [breadcrumb_link('奖惩记录', 'behaviors:conductrecord_list')]


def cycle_context(actor, pk):
    if not actor.is_active:
        raise PermissionDenied
    capabilities = {name: cycle_scope(actor, name).filter(pk=pk).exists() for name in PERMISSIONS}
    member = student_cycles(actor).filter(pk=pk).exists()
    if not (member or any(capabilities.values())):
        raise Http404
    return {'cycle': get_object_or_404(TrainingCycle, pk=pk), 'capabilities': capabilities, 'member': member}


def choose_cycle(request, title, cycles, target, parents=()):
    if not request.user.is_active:
        raise PermissionDenied
    if selected := request.GET.get('cycle'):
        if not selected.isascii() or not selected.isdecimal() or len(selected) > 19:
            raise Http404
        cycle = get_object_or_404(cycles, pk=selected)
        return redirect(target, cycle.pk)
    return page(request, 'index', title, parents=parents, cycles=cycles)


@require_safe
def cycle_index(request):
    return choose_cycle(request, '班级条例', policy_cycles(request.user), 'behaviors:cycle_policies')


@require_safe
def assignment_index(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    return choose_cycle(request, '经办分工', TrainingCycle.objects.all(), 'behaviors:cycle_assignment')


@require_safe
def entry_index(request):
    if not cycle_scope(request.user, 'enter').exists():
        raise PermissionDenied
    return choose_cycle(
        request, '录入奖惩', cycle_scope(request.user, 'enter'), 'behaviors:cycle_entry', record_parents(),
    )


@require_safe
def cycle_detail(request, pk):
    cycle_context(request.user, pk)
    return redirect('behaviors:cycle_policies', pk)


@require_safe
def cycle_policies(request, pk):
    cycle = get_object_or_404(policy_cycles(request.user), pk=pk)
    context = cycle_context(request.user, pk)
    capabilities = context['capabilities']
    policies = ConductPolicy.objects.filter(cycle=cycle)
    if not (capabilities['write'] or capabilities['publish']):
        policies = policies.filter(published_at__isnull=False, effective_date__lte=timezone.localdate())
    return page(
        request, 'policies', str(cycle), parents=policy_parents(),
        **context, policies=policies, current=active_policy(cycle, timezone.localdate()),
        can_seed=capabilities['write'] and not policies.exists(),
    )


def policy_context(request, pk, policy_pk):
    context = cycle_context(request.user, pk)
    policy = get_object_or_404(ConductPolicy, cycle_id=pk, pk=policy_pk)
    managing = context['capabilities']['write'] or context['capabilities']['publish']
    if not managing and (not policy.published_at or policy.effective_date > timezone.localdate()):
        raise Http404
    return context, policy


@require_http_methods(['GET', 'POST'])
def policy_detail(request, pk, policy_pk):
    context, policy = policy_context(request, pk, policy_pk)
    if request.method == 'POST':
        try:
            publish_policy(request.user, policy, request.POST.get('revision'))
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, '条例已发布。')
        return redirect('behaviors:cycle_policy', pk, policy_pk)
    rendered = render_markdown_text(policy.body, extensions=['tables', 'header-ids', 'toc'])
    return page(
        request, 'policy', policy.title, **context, policy=policy,
        parents=policy_parents(context['cycle']),
        body=mark_safe(MARKDOWN.clean(rendered.html)),
        toc=mark_safe(MARKDOWN.clean(rendered.toc or '')),
        revision=policy.updated_at.isoformat(),
    )


@require_safe
def policy_rules(request, pk, policy_pk):
    context, policy = policy_context(request, pk, policy_pk)
    groups = policy.policy_items.select_related('item__category').prefetch_related('rules')
    return page(
        request, 'rules', '计分附表', parents=policy_parents(context['cycle'], policy),
        **context, policy=policy, groups=groups,
    )


@require_http_methods(['GET', 'POST'])
@transaction.atomic
def policy_edit(request, pk, policy_pk=None):
    require_cycle(request.user, 'write', pk)
    cycle = get_object_or_404(TrainingCycle.objects.select_for_update() if request.method == 'POST' else TrainingCycle, pk=pk)
    policy = ConductPolicy(cycle=cycle)
    if policy_pk:
        policy = get_object_or_404(ConductPolicy, cycle=cycle, pk=policy_pk, published_at__isnull=True)
    source = None
    if not policy_pk and request.GET.get('copy'):
        source = get_object_or_404(ConductPolicy, pk=request.GET['copy'], cycle=cycle, published_at__isnull=False)
    initial = {'effective_date': timezone.localdate()}
    if source:
        initial.update(title=source.title, issuer=source.issuer, body=source.body)
    if policy_pk:
        initial['revision'] = policy.updated_at.isoformat()
    form = PolicyForm(request.POST or None, instance=policy, initial=initial)
    if request.method == 'POST' and form.is_valid():
        if policy_pk and form.cleaned_data['revision'] != policy.updated_at.isoformat():
            form.add_error(None, '草稿已变更，请重新打开。')
        else:
            policy = form.save(commit=False)
            policy.updated_by = request.user
            if not policy.pk:
                policy.created_by = request.user
            policy.save()
            if source:
                now = timezone.now()
                for original in source.policy_items.prefetch_related('rules'):
                    group = ConductPolicyItem.objects.create(
                        policy=policy, item_id=original.item_id, base_score=original.base_score,
                        created_by=request.user, updated_by=request.user,
                    )
                    ConductPolicyRule.objects.bulk_create([
                        ConductPolicyRule(
                            policy_item=group, section=rule.section, condition=rule.condition, severity_id=rule.severity_id,
                            multiplier=rule.multiplier, unit=rule.unit, order=rule.order, created_at=now, updated_at=now,
                            created_by=request.user, updated_by=request.user,
                        ) for rule in original.rules.all()
                    ])
            return redirect('behaviors:cycle_policy', pk, policy.pk)
    return page(
        request, 'form', '编辑条例草稿' if policy_pk else '新建条例草稿',
        form=form, parents=policy_parents(cycle),
    )


def draft_policy(request, pk, policy_pk):
    require_cycle(request.user, 'write', pk)
    cycle = get_object_or_404(
        TrainingCycle.objects.select_for_update() if request.method == 'POST' else TrainingCycle,
        pk=pk,
    )
    policy = get_object_or_404(ConductPolicy, pk=policy_pk, cycle=cycle, published_at__isnull=True)
    return cycle, policy


@require_http_methods(['GET', 'POST'])
@transaction.atomic
def policy_item_edit(request, pk, policy_pk, group_pk=None):
    cycle, policy = draft_policy(request, pk, policy_pk)
    group = get_object_or_404(policy.policy_items, pk=group_pk) if group_pk else ConductPolicyItem(policy=policy)
    form = PolicyItemForm(request.POST if request.method == 'POST' else None, instance=group)
    if request.method == 'POST' and group_pk and request.POST.get('action') == 'delete':
        if group.rules.exists():
            messages.error(request, '请先删除该事项的全部分档。')
        else:
            group.delete()
            policy.updated_by = request.user
            policy.save(update_fields=['updated_by', 'updated_at'])
        return redirect('behaviors:policy_rules', pk, policy_pk)
    if request.method == 'POST' and form.is_valid():
        group = form.save(commit=False)
        group.updated_by = request.user
        if not group.pk:
            group.created_by = request.user
        group.save()
        policy.updated_by = request.user
        policy.save(update_fields=['updated_by', 'updated_at'])
        if not group_pk:
            return redirect('behaviors:cycle_rule_new', pk, policy_pk, group.pk)
        return redirect('behaviors:policy_rules', pk, policy_pk)
    return page(
        request, 'form', '编辑条例事项' if group_pk else '添加条例事项', form=form,
        parents=policy_parents(cycle, policy), deletable=bool(group_pk and not group.rules.exists()),
    )


@require_http_methods(['GET', 'POST'])
@transaction.atomic
def rule_edit(request, pk, policy_pk, group_pk=None, rule_pk=None):
    cycle, policy = draft_policy(request, pk, policy_pk)
    if rule_pk:
        rule = get_object_or_404(policy.rules.select_related('policy_item__item__category'), pk=rule_pk)
        group = rule.policy_item
    else:
        group = get_object_or_404(policy.policy_items.select_related('item__category'), pk=group_pk)
        rule = ConductPolicyRule(policy_item=group)
    form = RuleForm(request.POST if request.method == 'POST' else None, instance=rule, group=group)
    deleting = rule_pk and request.method == 'POST' and request.POST.get('action') == 'delete'
    if deleting or (request.method == 'POST' and form.is_valid()):
        if deleting:
            rule.delete()
        else:
            rule = form.save(commit=False)
            rule.updated_by = request.user
            if not rule.pk:
                rule.created_by = request.user
            rule.save()
        policy.updated_by = request.user
        policy.save(update_fields=['updated_by', 'updated_at'])
        return redirect('behaviors:policy_rules', pk, policy_pk)
    return page(
        request, 'form', '编辑分档' if rule_pk else '新增分档',
        form=form, parents=policy_parents(cycle, policy), deletable=rule_pk,
    )


@require_http_methods(['GET', 'POST'])
@transaction.atomic
def assignment(request, pk, assignment_pk=None):
    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied
    cycle = get_object_or_404(TrainingCycle.objects.select_for_update() if request.method == 'POST' else TrainingCycle, pk=pk)
    scope = ConductCycleAssignment.objects.filter(cycle=cycle).select_related('user')
    obj = get_object_or_404(scope, pk=assignment_pk) if assignment_pk else ConductCycleAssignment(cycle=cycle)
    form = AssignmentForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if not obj.pk and scope.filter(user=obj.user).exists():
            form.add_error('user', '该人员已有分工，请编辑原分工。')
        else:
            obj.updated_by = request.user
            if not obj.pk:
                obj.created_by = request.user
            obj.save()
            return redirect('behaviors:cycle_assignment', pk)
    return page(
        request, 'assignment', '经办分工', cycle=cycle, form=form, assignments=scope,
        parents=[breadcrumb_link('经办分工', 'behaviors:assignment_index')],
    )


def _entry_state(actor, cycle, data, record):
    return [
        actor.pk, cycle.pk, data['occurred_date'].isoformat(), data['rule'].pk,
        sorted(student.pk for student in data['students']), data['quantity'], data['reason'],
        record.pk if record else None, data['revision'],
    ]


@require_http_methods(['GET', 'POST'])
def record_entry(request, pk, record_pk=None):
    require_cycle(request.user, 'enter', pk)
    cycle = get_object_or_404(TrainingCycle, pk=pk)
    record = None
    initial = {}
    if record_pk:
        record = get_object_or_404(ConductRecord.objects.select_related('rule__policy_item__policy'), cycle=cycle, pk=record_pk, recorded_by=request.user)
        if record.status != ConductRecord.Status.PENDING:
            raise Http404
        initial = dict(
            occurred_date=record.occurred_date, students=[record.student_id],
            rule=record.rule_id, quantity=record.quantity, reason=record.reason, revision=record.updated_at.isoformat(),
        )
    elif request.method == 'GET' and (copy := request.GET.get('copy')):
        if not copy.isascii() or not copy.isdecimal() or len(copy) > 19:
            raise Http404
        source = get_object_or_404(
            visible_records(request.user), cycle=cycle, pk=copy,
            status__in=[ConductRecord.Status.REJECTED, ConductRecord.Status.VOID],
        )
        initial = dict(students=[source.student_id], rule=source.rule_id, quantity=source.quantity, reason=source.reason)
        initial['occurred_date'] = source.occurred_date
    date_form = EntryDateForm(
        request.POST if request.method == 'POST' else request.GET if request.GET.get('occurred_date') else None,
        initial=initial,
    )
    entry_date = record.occurred_date if record else None
    if request.method == 'GET' and not request.GET.get('occurred_date'):
        entry_date = initial.get('occurred_date', timezone.localdate())
    if not entry_date and date_form.is_valid():
        entry_date = date_form.cleaned_data['occurred_date']
    policy = record.rule.policy_item.policy if record else active_policy(cycle, entry_date) if entry_date else None
    form = None
    preview = None
    if entry_date and (policy or record):
        initial['occurred_date'] = entry_date
        form = EntryForm(request.POST or None, request.FILES or None, cycle=cycle, date=entry_date, record=record, initial=initial)
        if request.method == 'POST' and form.is_valid():
            data = form.cleaned_data
            state = _entry_state(request.user, cycle, data, record)
            try:
                if request.POST.get('action') == 'confirm':
                    try:
                        key, confirmed = signing.loads(data['confirmation'], salt='conduct-entry', max_age=1800)
                    except signing.BadSignature as exc:
                        raise ValidationError('预览已失效，请重新预览。') from exc
                    if confirmed != state:
                        raise ValidationError('内容已变更，请重新预览。')
                    saved = save_entry(request.user, cycle, data, record, key)
                    messages.success(request, '奖惩记录已保存，等待审核。')
                    return redirect('behaviors:record_detail', saved.pk)
                token = signing.dumps([str(uuid4()), state], salt='conduct-entry')
                preview = data
                form = EntryForm(
                    cycle=cycle, date=entry_date, record=record, initial={
                        **data, 'students': [student.pk for student in data['students']],
                        'rule': data['rule'].pk, 'confirmation': token,
                    },
                )
                form.fields['occurred_date'].widget = forms.HiddenInput()
            except ValidationError as exc:
                form.add_error(None, '；'.join(exc.messages))
        form.fields['occurred_date'].widget = forms.HiddenInput()
    return page(
        request, 'entry', '编辑待审记录' if record else '录入奖惩记录',
        cycle=cycle, date_form=date_form, form=form, preview=preview, record=record,
        entry_date=entry_date, policy=policy, parents=record_parents(),
    )


@require_http_methods(['GET', 'POST'])
def record_detail(request, pk):
    record = ledger_record(request.user, pk=pk)
    actor = request.user
    status = ConductRecord.Status
    can_review = (
        cycle_scope(actor, 'review').filter(pk=record.cycle_id).exists()
        if record.cycle_id else actor.is_active and actor.is_superuser
    )
    can_enter = bool(record.cycle_id and cycle_scope(actor, 'enter').filter(pk=record.cycle_id).exists())
    if request.method == 'POST':
        try:
            review_record(actor, record, request.POST.get('action'), request.POST.get('note', '').strip(),
                          request.POST.get('revision'))
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, '审核操作已保存。')
        return redirect('behaviors:record_detail', pk)
    return page(
        request, 'record', '奖惩记录详情', parents=record_parents(), record=record, cycle=record.cycle,
        editable=can_enter and record.recorded_by_id == actor.pk and record.status == status.PENDING,
        can_copy=can_enter and record.status in {status.REJECTED, status.VOID},
        review_pending=can_review and record.status == status.PENDING,
        can_void=can_review and record.cycle_id and record.status == status.APPROVED,
        revision=record.updated_at.isoformat(),
    )


def edit_record(request, pk):
    record = ledger_record(request.user, pk=pk)
    if not record.cycle_id:
        raise Http404
    return record_entry(request, record.cycle_id, record.pk)


@require_safe
def old_cycle_record(request, pk, record_pk, *, edit=False):
    record = find_old_cycle_record(request.user, pk, record_pk)
    return redirect('behaviors:record_edit' if edit else 'behaviors:record_detail', record.pk)


@require_POST
def elite_draft(request, pk):
    require_cycle(request.user, 'write', pk)
    try:
        policy = create_elite_draft(request.user, pk)
    except ValidationError as exc:
        messages.error(request, '；'.join(exc.messages))
        return redirect('behaviors:cycle_detail', pk)
    messages.success(request, '已载入条例草稿和计分附表。发布前请校对并列名次、进步奖叠加与积分抵扣口径。')
    return redirect('behaviors:cycle_policy', pk, policy.pk)
