from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, DecimalField, Exists, ExpressionWrapper, F, Max, OuterRef, Q, Sum
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


def current_skill_tree_for(domain):
    return (
        SkillTreeVersion.objects.select_related("technical_domain", "technical_domain__skill_project")
        .filter(technical_domain=domain, is_current=True)
        .first()
    )


def current_wsos_for(project):
    return WSOSVersion.objects.filter(skill_project=project, is_current=True).first()


def project_domains_for_view(*, project, user):
    """返回当前用户可在项目页或技能树页看到的技术领域。"""

    domains = TechnicalDomain.objects.filter(skill_project=project)
    manageable_inactive = manageable_domains_for(user, project).filter(is_active=False)
    current_tree_domain_ids = SkillTreeVersion.objects.filter(
        technical_domain__skill_project=project,
        is_current=True,
    ).values("technical_domain_id")
    visible_condition = Q(is_active=True) | Q(pk__in=manageable_inactive) | Q(pk__in=current_tree_domain_ids)
    domains = domains.filter(visible_condition).order_by("order", "code", "name", "pk")
    manageable_ids = set(manageable_domains_for(user, project).values_list("pk", flat=True))
    current_trees = {
        tree.technical_domain_id: tree
        for tree in SkillTreeVersion.objects.filter(
            technical_domain__skill_project=project,
            is_current=True,
        )
        .select_related("technical_domain")
        .annotate(tree_node_count=Count("nodes"))
    }
    for domain in domains:
        domain.current_tree = current_trees.get(domain.pk)
        domain.tree_node_count = domain.current_tree.tree_node_count if domain.current_tree else 0
        domain.can_edit_domain = can_manage_domain(user, domain)
        domain.can_manage_tree = domain.pk in manageable_ids
    return list(domains)


def unmounted_primary_skills_for_tree(*, tree_version, user):
    """返回当前版本尚无树位置、且主要归属当前领域的启用技能。"""

    mounted_in_tree = SkillTreeNode.objects.filter(tree_version=tree_version, skill_id=OuterRef("pk"))
    return (
        visible_skills_for(user)
        .filter(
            skill_project=tree_version.skill_project,
            primary_domain=tree_version.technical_domain,
            is_active=True,
        )
        .annotate(is_mounted_in_tree=Exists(mounted_in_tree))
        .filter(is_mounted_in_tree=False)
        .select_related("primary_domain")
        .prefetch_related("terms")
        .order_by("order", "name", "pk")
    )


def skill_tree_structure(*, tree_version, user):
    """一次读取单领域技能树，并在内存中构造模板所需的 children 结构。"""

    domain = tree_version.technical_domain
    node_queryset = SkillTreeNode.objects.filter(tree_version=tree_version)
    nodes = list(
        node_queryset
        .select_related("skill", "skill__primary_domain", "tree_version__technical_domain", "parent")
        .order_by("order", "pk")
    )
    manageable_domain_ids = set(manageable_domains_for(user, tree_version.skill_project).values_list("pk", flat=True))
    children_by_parent = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_id].append(node)

    can_add_node = user.has_perm("standards.add_skilltreenode")
    can_add_skill = user.has_perm("standards.add_skill")
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
        node.can_add_tree_position = (
            can_add_node and node.technical_domain.is_active and node.technical_domain_id in manageable_domain_ids
        )
        node.can_create_skill = (
            can_add_skill and node.technical_domain.is_active and node.technical_domain_id in manageable_domain_ids
        )
        node.can_move = can_change_node and node.technical_domain_id in manageable_domain_ids
        node.can_move_up = False
        node.can_move_down = False
        node.can_remove = can_delete_node and node.technical_domain_id in manageable_domain_ids
        decorate_siblings(node.tree_children, [*ancestors, node.skill.name])
        for child in node.tree_children:
            node.descendant_count += child.descendant_count + 1

    def decorate_siblings(siblings, ancestors):
        for node in siblings:
            decorate_branch(node, ancestors)
        for index, node in enumerate(siblings):
            node.can_move_up = node.can_move and index > 0
            node.can_move_down = node.can_move and index < len(siblings) - 1

    domain.tree_roots = children_by_parent.get(None, [])
    decorate_siblings(domain.tree_roots, [])
    domain.can_add_tree_position = can_add_node and domain.is_active and domain.pk in manageable_domain_ids
    domain.can_create_skill = can_add_skill and domain.is_active and domain.pk in manageable_domain_ids
    domain.can_manage_tree = domain.pk in manageable_domain_ids
    return domain


def decorate_skill_tree_paths(*, tree_version, nodes):
    """为列表/搜索结果批量补充完整路径，不在逐行处理中查询数据库。"""

    all_nodes = list(
        SkillTreeNode.objects.filter(tree_version=tree_version)
        .select_related("skill")
        .only("pk", "parent_id", "skill__name")
    )
    node_by_id = {node.pk: node for node in all_nodes}
    path_cache = {}

    def path_for(node):
        if node.pk in path_cache:
            return path_cache[node.pk]
        parts = [node.skill.name]
        parent_id = node.parent_id
        while parent_id is not None:
            parent = node_by_id[parent_id]
            parts.append(parent.skill.name)
            parent_id = parent.parent_id
        path_cache[node.pk] = " / ".join(reversed(parts))
        return path_cache[node.pk]

    for node in nodes:
        node.full_path = path_for(node_by_id[node.pk])
    return nodes


def search_skill_tree_nodes(*, tree_version, user, query, limit=20):
    if not user.has_perm("standards.view_skilltreeversion") or not query.strip():
        return []
    nodes = list(
        SkillTreeNode.objects.filter(tree_version=tree_version)
        .filter(
            Q(skill__name__icontains=query)
            | Q(skill__description__icontains=query)
            | Q(skill__terms__term__icontains=query)
        )
        .select_related("skill")
        .distinct()
        .order_by("skill__name", "pk")[:limit]
    )
    return decorate_skill_tree_paths(tree_version=tree_version, nodes=nodes)


def wsos_skill_candidates(*, section, query="", domain=None):
    queryset = Skill.objects.filter(
        skill_project=section.wsos_version.skill_project,
        is_active=True,
    ).exclude(wsos_mappings__wsos_section=section)
    if query.strip():
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(terms__term__icontains=query)
        )
    if domain is not None:
        queryset = queryset.filter(Q(primary_domain=domain) | Q(related_domains=domain))
    return queryset.select_related("primary_domain").prefetch_related("terms").distinct().order_by("name", "pk")[:20]


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
