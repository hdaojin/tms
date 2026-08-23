from django.db.models import Count, Q
from standards.selectors import is_project_admin, manageable_domains_for
from .models import Assessment, AssessmentDocument, AssessmentModule


def visible_assessments_for(user, queryset=None):
    queryset = queryset if queryset is not None else Assessment.objects.all()
    if not user.is_authenticated or not user.has_perm("assessments.view_assessment"):
        return queryset.none()
    if is_project_admin(user):
        return queryset
    return queryset.filter(
        Q(participants__user=user)
        | Q(modules__coach_assignments__user=user)
        | Q(modules__domain_mappings__technical_domain__memberships__user=user)
    ).distinct()


def manageable_assessment_modules_for(user, queryset=None):
    queryset = queryset if queryset is not None else AssessmentModule.objects.all()
    if not user.has_perm("assessments.change_assessmentmodule"):
        return queryset.none()
    if is_project_admin(user):
        return queryset
    domain_ids = manageable_domains_for(user).values("pk")
    single_domain = queryset.annotate(_domain_count=Count("domain_mappings", distinct=True)).filter(
        _domain_count=1, domain_mappings__technical_domain_id__in=domain_ids
    )
    return (single_domain | queryset.filter(coach_assignments__user=user)).distinct()


def can_manage_assessment_module(user, module):
    return manageable_assessment_modules_for(user).filter(pk=module.pk).exists()


def visible_documents_for(user, queryset=None):
    queryset = queryset if queryset is not None else AssessmentDocument.objects.all()
    return queryset.filter(assessment_id__in=visible_assessments_for(user).values("pk"))
