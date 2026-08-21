from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum
from django.db.models.functions import Coalesce

from .models import Skill, SkillTreeNode, SkillTreeVersion, TechnicalDomain, WSOSVersion


def is_project_admin(user) -> bool:
    return bool(
        user.is_authenticated and (user.is_superuser or user.has_perm("standards.manage_all_technical_domains"))
    )


def manageable_domains_for(user, skill_project=None):
    queryset = TechnicalDomain.objects.all()
    if skill_project is not None:
        queryset = queryset.filter(skill_project=skill_project)
    if is_project_admin(user):
        return queryset
    if not user.is_authenticated:
        return queryset.none()
    return queryset.filter(memberships__user=user).distinct()


def can_manage_domain(user, domain, permission="standards.change_technicaldomain") -> bool:
    return bool(user.has_perm(permission) and manageable_domains_for(user).filter(pk=domain.pk).exists())


def visible_skills_for(user, queryset=None):
    queryset = queryset if queryset is not None else Skill.objects.all()
    if not user.is_authenticated or not user.has_perm("standards.view_skill"):
        return queryset.none()
    if is_project_admin(user):
        return queryset
    domain_ids = manageable_domains_for(user).values("pk")
    return queryset.filter(Q(primary_domain_id__in=domain_ids) | Q(related_domains__in=domain_ids)).distinct()


def manageable_skills_for(user, queryset=None):
    queryset = queryset if queryset is not None else Skill.objects.all()
    if not user.has_perm("standards.change_skill"):
        return queryset.none()
    if is_project_admin(user):
        return queryset
    return queryset.filter(primary_domain__memberships__user=user).distinct()


def can_manage_skill(user, skill) -> bool:
    return manageable_skills_for(user).filter(pk=skill.pk).exists()


def current_skill_tree_for(project):
    return SkillTreeVersion.objects.filter(skill_project=project, is_current=True).first()


def current_wsos_for(project):
    return WSOSVersion.objects.filter(skill_project=project, is_current=True).first()


def skill_tree_structure(*, tree_version, user):
    """一次读取整棵树并在内存中构造模板所需的领域与 children 结构。"""

    nodes = list(
        SkillTreeNode.objects.filter(tree_version=tree_version)
        .select_related("skill", "skill__primary_domain", "technical_domain", "parent")
        .order_by("technical_domain__order", "technical_domain_id", "order", "pk")
    )
    node_domain_ids = {node.technical_domain_id for node in nodes}
    domains = list(
        TechnicalDomain.objects.filter(skill_project=tree_version.skill_project)
        .filter(Q(is_active=True) | Q(pk__in=node_domain_ids))
        .order_by("order", "code", "name", "pk")
    )
    manageable_domain_ids = set(manageable_domains_for(user, tree_version.skill_project).values_list("pk", flat=True))
    children_by_parent = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_id].append(node)

    can_add_node = user.has_perm("standards.add_skilltreenode")
    can_change_node = user.has_perm("standards.change_skilltreenode")
    can_delete_node = user.has_perm("standards.delete_skilltreenode")
    can_change_skill = user.has_perm("standards.change_skill")
    can_view_skill = user.has_perm("standards.view_skill")
    project_admin = is_project_admin(user)

    def decorate_branch(node, ancestors):
        node.tree_children = children_by_parent.get(node.pk, [])
        node.full_path = " / ".join([*ancestors, node.skill.name])
        node.descendant_count = 0
        node.can_view_skill = can_view_skill
        node.can_edit_skill = can_change_skill and (
            project_admin or node.skill.primary_domain_id in manageable_domain_ids
        )
        node.can_add_child = (
            can_add_node and node.technical_domain.is_active and node.technical_domain_id in manageable_domain_ids
        )
        node.can_move = can_change_node and node.technical_domain_id in manageable_domain_ids
        node.can_remove = can_delete_node and node.technical_domain_id in manageable_domain_ids
        for child in node.tree_children:
            decorate_branch(child, [*ancestors, node.skill.name])
            node.descendant_count += child.descendant_count + 1

    roots_by_domain = defaultdict(list)
    for root in children_by_parent.get(None, []):
        roots_by_domain[root.technical_domain_id].append(root)
        decorate_branch(root, [])

    for domain in domains:
        domain.tree_roots = roots_by_domain.get(domain.pk, [])
        domain.can_add_root = can_add_node and domain.is_active and domain.pk in manageable_domain_ids
        domain.can_manage_tree = domain.pk in manageable_domain_ids
    return domains


def skill_assessment_history(skill):
    from evidence.models import EvidenceSkillMap, KnowledgeEvidence

    approved = EvidenceSkillMap.objects.filter(
        skill=skill,
        review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        evidence__review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
    )
    weighted_mark = ExpressionWrapper(
        Coalesce(F("evidence__estimated_mark"), Decimal("0")) * F("weight"),
        output_field=DecimalField(max_digits=12, decimal_places=4),
    )
    summary = approved.aggregate(
        evidence_count=Count("evidence", distinct=True),
        assessment_count=Count("evidence__assessment_module__assessment", distinct=True),
        latest_date=Max("evidence__assessment_module__assessment__start_date"),
        weighted_mark=Coalesce(Sum(weighted_mark), Decimal("0")),
    )
    summary["level_distribution"] = list(
        approved.exclude(evidence__assessment_module__assessment__level__isnull=True)
        .values("evidence__assessment_module__assessment__level__name")
        .annotate(count=Count("evidence", distinct=True))
        .order_by("evidence__assessment_module__assessment__level__order")
    )
    summary["domains"] = list(skill.related_domains.all())
    if skill.primary_domain_id:
        summary["domains"].insert(0, skill.primary_domain)
    summary["wsos_sections"] = list(skill.wsos_mappings.select_related("wsos_section", "wsos_section__wsos_version"))
    return summary


def skill_training_investment(skill):
    from training.models import TaskExecution

    executions = TaskExecution.objects.filter(training_task__skill_links__skill=skill)
    summary = executions.aggregate(
        latest_date=Max("training_task__planned_date"),
        task_count=Count("training_task", distinct=True),
        completed_count=Count("pk", filter=Q(status=TaskExecution.Status.COMPLETED)),
        partial_count=Count("pk", filter=Q(status=TaskExecution.Status.PARTIALLY_COMPLETED)),
        blocked_count=Count("pk", filter=Q(status=TaskExecution.Status.BLOCKED)),
        actual_minutes=Coalesce(Sum("actual_minutes"), 0),
    )
    summary["common_problems"] = list(
        executions.exclude(problems="")
        .values("problems")
        .annotate(count=Count("pk"))
        .order_by("-count", "problems")[:5]
    )
    return summary


def skill_assessment_performance(skill):
    from evidence.models import KnowledgeEvidence
    from scoring.models import ScoringResult

    results = ScoringResult.objects.filter(
        aspect__knowledge_evidence__review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        aspect__knowledge_evidence__skill_mappings__skill=skill,
        aspect__knowledge_evidence__skill_mappings__review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
    )
    weight = F("aspect__knowledge_evidence__skill_mappings__weight")
    score_contribution = ExpressionWrapper(
        F("score_awarded") * weight,
        output_field=DecimalField(max_digits=12, decimal_places=4),
    )
    max_contribution = ExpressionWrapper(
        F("aspect__max_mark") * weight,
        output_field=DecimalField(max_digits=12, decimal_places=4),
    )
    summary = results.aggregate(
        awarded_mark=Coalesce(Sum(score_contribution), Decimal("0")),
        mapped_max_mark=Coalesce(Sum(max_contribution), Decimal("0")),
    )
    summary["trend"] = list(
        results.values(
            "participant__display_name",
            "aspect__scheme__assessment_module__assessment__name",
            "aspect__scheme__assessment_module__assessment__start_date",
        )
        .annotate(
            awarded_mark=Sum(score_contribution),
            mapped_max_mark=Sum(max_contribution),
        )
        .order_by("-aspect__scheme__assessment_module__assessment__start_date")[:10]
    )
    return summary
