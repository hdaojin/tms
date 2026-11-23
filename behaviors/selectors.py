from django.db.models import Count, Q, Sum

from accounts.services.users import user_name_search_ids
from django.contrib.auth import get_user_model
from training.models import TrainingCycle

from .cycle_services import cycle_scope, student_cycles
from .models import ConductNature, ConductPolicyRule, ConductRecord
from .permissions import can_record_conduct, can_view_all_conduct_records


def policy_cycles(user):
    return TrainingCycle.objects.filter(
        Q(pk__in=student_cycles(user))
        | Q(pk__in=cycle_scope(user, 'write'))
        | Q(pk__in=cycle_scope(user, 'publish'))
        | Q(pk__in=cycle_scope(user, 'enter'))
        | Q(pk__in=cycle_scope(user, 'review')),
    )


def ledger_cycles(user, *, summary=False):
    scope = Q(pk__in=student_cycles(user)) | Q(pk__in=cycle_scope(user, 'review'))
    if not summary:
        scope |= Q(pk__in=cycle_scope(user, 'enter'))
    return TrainingCycle.objects.filter(scope)


def legacy_permission(user, *, summary=False):
    codename = 'view_conductsummary' if summary else 'view_conductrecord'
    return user.has_perm(f'behaviors.{codename}')


def can_view_records(user):
    return user.is_active and (legacy_permission(user) or ledger_cycles(user).exists())


def can_view_summaries(user):
    return user.is_active and (legacy_permission(user, summary=True) or ledger_cycles(user, summary=True).exists())


def can_view_policies(user):
    return user.is_active and (user.is_superuser or policy_cycles(user).exists())


def visible_records(user, *, summary=False, legacy_admin=False):
    records = ConductRecord.objects.all()
    if not user.is_active:
        return records.none()
    scope = (
        Q(cycle__in=cycle_scope(user, 'review'))
        | Q(cycle__in=student_cycles(user), student=user, status=ConductRecord.Status.APPROVED)
    )
    if not summary:
        scope |= Q(cycle__in=cycle_scope(user, 'enter'), recorded_by=user)
    if legacy_permission(user, summary=summary):
        legacy = Q(cycle__isnull=True)
        if not can_view_all_conduct_records(user):
            legacy &= Q(student=user)
        scope |= legacy
    if legacy_admin and user.is_staff:
        if can_view_all_conduct_records(user):
            scope |= Q(cycle__isnull=True)
        elif can_record_conduct(user):
            scope |= Q(cycle__isnull=True, recorded_by=user)
    visible = records.filter(scope)
    return visible.filter(status=ConductRecord.Status.APPROVED) if summary else visible


def search_students(queryset, query):
    candidates = get_user_model().objects.filter(pk__in=queryset.order_by().values('student_id'))
    return queryset.filter(student_id__in=user_name_search_ids(candidates, query))


def summarize_records(queryset):
    section = ConductPolicyRule.Section
    return queryset.order_by().values(
        'student_id', 'student__first_name', 'student__last_name', 'cycle_id', 'cycle__name',
    ).annotate(
        total_score=Sum('frozen_points'),
        competition=Sum('frozen_points', filter=Q(rule__section=section.COMPETITION)),
        management=Sum('frozen_points', filter=Q(rule__section=section.MANAGEMENT)),
        learning=Sum('frozen_points', filter=Q(rule__section=section.LEARNING)),
        reward_count=Count('pk', filter=Q(frozen_nature=ConductNature.REWARD)),
        penalty_count=Count('pk', filter=Q(frozen_nature=ConductNature.PENALTY)),
    ).order_by('cycle__name', 'student__last_name', 'student__first_name', 'student_id', 'cycle_id')
