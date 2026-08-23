from __future__ import annotations

from difflib import SequenceMatcher
from unicodedata import normalize

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from .models import (
    Skill,
    SkillTerm,
    SkillTreeNode,
    SkillTreeVersion,
    SkillWSOSMap,
    TechnicalDomain,
    WSOSSection,
)
from .selectors import can_manage_domain


HIGH_SIMILARITY_THRESHOLD = 0.72


def normalize_skill_term(value: str) -> str:
    """生成跨 SQLite/PostgreSQL 一致的技能称谓比较键。"""

    folded = normalize("NFKC", value or "").casefold()
    return "".join(character for character in folded if not character.isspace())


def split_skill_terms(value: str) -> list[str]:
    terms = []
    seen = set()
    for item in (value or "").replace(",", "\n").splitlines():
        term = item.strip()
        normalized = normalize_skill_term(term)
        if term and normalized and normalized not in seen:
            terms.append(term)
            seen.add(normalized)
    return terms


def find_skill_term_conflicts(*, skill_project, terms, exclude_skill=None):
    normalized_terms = {normalize_skill_term(term) for term in terms if normalize_skill_term(term)}
    queryset = SkillTerm.objects.filter(
        skill_project=skill_project,
        normalized_term__in=normalized_terms,
    ).select_related("skill", "skill__primary_domain")
    if exclude_skill is not None:
        queryset = queryset.exclude(skill=exclude_skill)
    return list(queryset)


def _term_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if left in right or right in left:
        return 0.9 * min(len(left), len(right)) / max(len(left), len(right)) + 0.1
    return SequenceMatcher(None, left, right).ratio()


def find_skill_candidates(*, skill_project, query: str, limit: int = 8, exclude_skill=None):
    normalized_query = normalize_skill_term(query)
    if len(normalized_query) < 2:
        return []

    queryset = (
        Skill.objects.filter(skill_project=skill_project)
        .select_related("skill_project", "primary_domain")
        .prefetch_related("related_domains", "terms")
    )
    if exclude_skill is not None:
        queryset = queryset.exclude(pk=exclude_skill.pk)

    candidates = []
    for skill in queryset:
        term_scores = [
            _term_similarity(normalized_query, normalize_skill_term(term.term)) for term in skill.terms.all()
        ]
        if not term_scores:
            term_scores = [_term_similarity(normalized_query, normalize_skill_term(skill.name))]
        score = max(term_scores)
        description_match = normalized_query in normalize_skill_term(skill.description)
        if description_match:
            score = max(score, 0.45)
        if score < 0.45:
            continue
        skill.candidate_score = score
        skill.candidate_exact = score == 1.0
        skill.candidate_high_similarity = score >= HIGH_SIMILARITY_THRESHOLD
        candidates.append(skill)

    return sorted(
        candidates,
        key=lambda skill: (-skill.candidate_score, skill.primary_domain.order, skill.name, skill.pk),
    )[:limit]


def _replace_skill_terms(*, skill, aliases):
    aliases = split_skill_terms("\n".join(aliases))
    primary_normalized = normalize_skill_term(skill.name)
    aliases = [alias for alias in aliases if normalize_skill_term(alias) != primary_normalized]
    SkillTerm.objects.filter(skill=skill).delete()
    SkillTerm.objects.bulk_create(
        [
            SkillTerm(
                skill_project=skill.skill_project,
                skill=skill,
                term=skill.name,
                normalized_term=primary_normalized,
                kind=SkillTerm.Kind.NAME,
            ),
            *[
                SkillTerm(
                    skill_project=skill.skill_project,
                    skill=skill,
                    term=alias,
                    normalized_term=normalize_skill_term(alias),
                    kind=SkillTerm.Kind.ALIAS,
                )
                for alias in aliases
            ],
        ]
    )


@transaction.atomic
def save_skill(*, skill, aliases, related_domains, actor, preserve_old_name=False, old_name=""):
    permission = "standards.change_skill" if skill.pk else "standards.add_skill"
    if skill.pk:
        previous_primary_domain = (
            Skill.objects.filter(pk=skill.pk)
            .select_related("primary_domain")
            .values_list("primary_domain_id", flat=True)
            .first()
        )
        if previous_primary_domain and previous_primary_domain != skill.primary_domain_id:
            _require_domain_scope(
                actor=actor,
                domain=TechnicalDomain.objects.get(pk=previous_primary_domain),
                permission=permission,
            )
    _require_domain_scope(actor=actor, domain=skill.primary_domain, permission=permission)
    aliases = list(aliases)
    if preserve_old_name and old_name and normalize_skill_term(old_name) != normalize_skill_term(skill.name):
        aliases.append(old_name)

    all_terms = [skill.name, *aliases]
    conflicts = find_skill_term_conflicts(
        skill_project=skill.skill_project,
        terms=all_terms,
        exclude_skill=skill if skill.pk else None,
    )
    if conflicts:
        raise ValidationError(f"称谓“{conflicts[0].term}”已属于技能 {conflicts[0].skill}。")

    skill.save()
    set_skill_related_domains(skill, related_domains)
    try:
        _replace_skill_terms(skill=skill, aliases=aliases)
    except IntegrityError as exc:
        raise ValidationError("该技能名称或别名已被其他技能使用，请重新检查。") from exc
    return skill


@transaction.atomic
def add_skill_alias(*, skill, term, actor):
    _require_domain_scope(
        actor=actor,
        domain=skill.primary_domain,
        permission="standards.change_skill",
    )
    term = term.strip()
    normalized_term = normalize_skill_term(term)
    if not normalized_term:
        raise ValidationError("别名不能为空。")
    existing = (
        SkillTerm.objects.filter(
            skill_project=skill.skill_project,
            normalized_term=normalized_term,
        )
        .select_related("skill")
        .first()
    )
    if existing:
        if existing.skill_id == skill.pk:
            return existing, False
        raise ValidationError(f"该称谓已属于技能 {existing.skill}。")
    try:
        created = SkillTerm.objects.create(
            skill_project=skill.skill_project,
            skill=skill,
            term=term,
            normalized_term=normalized_term,
            kind=SkillTerm.Kind.ALIAS,
        )
    except IntegrityError as exc:
        raise ValidationError("该称谓已被其他技能使用，请重新检查。") from exc
    return created, True


@transaction.atomic
def set_skill_related_domains(skill, domains):
    domains = list(domains)
    for domain in domains:
        if domain.skill_project_id != skill.skill_project_id:
            raise ValidationError("关联技术领域必须属于技能对应的技能项目。")
        if domain.pk == skill.primary_domain_id:
            raise ValidationError("主要技术领域不能重复加入关联技术领域。")
    allowed_domain_ids = {skill.primary_domain_id, *(domain.pk for domain in domains)}
    invalid_position = (
        skill.tree_nodes.exclude(tree_version__technical_domain_id__in=allowed_domain_ids)
        .select_related("tree_version", "tree_version__technical_domain")
        .first()
        if skill.pk
        else None
    )
    if invalid_position:
        raise ValidationError(
            f"该修改会使技能树“{invalid_position.tree_version.name}”中的"
            f"“{invalid_position.technical_domain.name}”位置失效；请先移动或移除该树位置。"
        )
    skill.related_domains.set(domains)
    return skill


def _require_domain_scope(*, actor, domain, permission):
    if not can_manage_domain(actor, domain, permission=permission):
        raise PermissionDenied


def _lock_tree(tree_version):
    return SkillTreeVersion.objects.select_for_update().get(pk=tree_version.pk)


def _skill_allows_domain(skill, domain):
    return skill.primary_domain_id == domain.pk or skill.related_domains.filter(pk=domain.pk).exists()


def _validate_parent(*, tree_version, parent):
    if parent is None:
        return
    if parent.tree_version_id != tree_version.pk:
        raise ValidationError("父技能必须属于当前技能树版本。")


def _next_sibling_order(*, tree_version, parent):
    maximum = SkillTreeNode.objects.filter(
        tree_version=tree_version,
        parent=parent,
    ).aggregate(maximum=Max("order"))["maximum"]
    return (maximum or 0) + 10


@transaction.atomic
def attach_existing_skill_to_tree(*, tree_version, parent, skill, actor):
    _lock_tree(tree_version)
    technical_domain = tree_version.technical_domain
    _require_domain_scope(actor=actor, domain=technical_domain, permission="standards.add_skilltreenode")
    if not technical_domain.is_active:
        raise ValidationError("已停用的技术领域不能新增树位置。")
    _validate_parent(tree_version=tree_version, parent=parent)
    if skill.skill_project_id != tree_version.skill_project_id:
        raise ValidationError("技能与技能树必须属于同一技能项目。")
    if not skill.is_active:
        raise ValidationError("已停用的技能不能新增到技能树。")
    if not _skill_allows_domain(skill, technical_domain):
        raise ValidationError("技能未关联当前技术领域，不能挂载到这里。")
    existing = (
        SkillTreeNode.objects.filter(tree_version=tree_version, skill=skill)
        .select_related("skill", "parent__skill")
        .first()
    )
    if existing:
        raise ValidationError(f"该技能已存在于当前版本：{existing.get_full_path()}。")
    node = SkillTreeNode(
        tree_version=tree_version,
        parent=parent,
        skill=skill,
        order=_next_sibling_order(
            tree_version=tree_version,
            parent=parent,
        ),
    )
    try:
        node.save()
    except IntegrityError as exc:
        raise ValidationError("该技能已存在于当前技能树版本中。") from exc
    return node


@transaction.atomic
def create_skill_in_tree(
    *,
    tree_version,
    parent,
    name,
    actor,
    description="",
    confirm_distinct=False,
):
    _lock_tree(tree_version)
    technical_domain = tree_version.technical_domain
    candidates = find_skill_candidates(skill_project=tree_version.skill_project, query=name)
    exact = next((candidate for candidate in candidates if candidate.candidate_exact), None)
    if exact is not None:
        return attach_existing_skill_to_tree(
            tree_version=tree_version,
            parent=parent,
            skill=exact,
            actor=actor,
        )
    high_similarity = [candidate for candidate in candidates if candidate.candidate_high_similarity]
    if high_similarity and not confirm_distinct:
        raise ValidationError("存在高度相似的候选技能，请先确认这不是同一技能。")
    if high_similarity and not description.strip():
        raise ValidationError("存在高度相似的候选技能时，请填写描述说明技能边界。")
    _require_domain_scope(actor=actor, domain=technical_domain, permission="standards.add_skill")
    _require_domain_scope(actor=actor, domain=technical_domain, permission="standards.add_skilltreenode")
    if not technical_domain.is_active:
        raise ValidationError("已停用的技术领域不能新增技能。")
    skill = save_skill(
        skill=Skill(
            skill_project=tree_version.skill_project,
            primary_domain=technical_domain,
            name=name.strip(),
            description=description.strip(),
        ),
        aliases=(),
        related_domains=(),
        actor=actor,
    )
    return attach_existing_skill_to_tree(
        tree_version=tree_version,
        parent=parent,
        skill=skill,
        actor=actor,
    )


@transaction.atomic
def create_detailed_skill_in_tree(
    *,
    tree_version,
    parent,
    skill,
    aliases,
    related_domains,
    actor,
):
    """保存完整 SkillForm 数据，并原子挂入服务端确定的树位置。"""

    _lock_tree(tree_version)
    technical_domain = tree_version.technical_domain
    _require_domain_scope(actor=actor, domain=technical_domain, permission="standards.add_skill")
    _require_domain_scope(actor=actor, domain=technical_domain, permission="standards.add_skilltreenode")
    if not technical_domain.is_active:
        raise ValidationError("已停用的技术领域不能新增技能。")
    _validate_parent(tree_version=tree_version, parent=parent)

    skill.skill_project = tree_version.skill_project
    skill.primary_domain = technical_domain
    saved_skill = save_skill(
        skill=skill,
        aliases=aliases,
        related_domains=related_domains,
        actor=actor,
    )
    return attach_existing_skill_to_tree(
        tree_version=tree_version,
        parent=parent,
        skill=saved_skill,
        actor=actor,
    )


def _locked_tree_nodes(tree_version):
    return list(
        SkillTreeNode.objects.select_for_update()
        .filter(tree_version=tree_version)
        .select_related("skill", "tree_version__technical_domain", "parent")
        .order_by("order", "pk")
    )


def _subtree_ids(nodes, root_id):
    children_by_parent = {}
    for item in nodes:
        children_by_parent.setdefault(item.parent_id, []).append(item)
    result = []
    stack = [root_id]
    while stack:
        current = stack.pop()
        result.append(current)
        stack.extend(child.pk for child in children_by_parent.get(current, ()))
    return result


@transaction.atomic
def move_skill_tree_node(*, node, new_parent, actor):
    _lock_tree(node.tree_version)
    nodes = _locked_tree_nodes(node.tree_version)
    node_by_id = {item.pk: item for item in nodes}
    locked_node = node_by_id[node.pk]
    technical_domain = locked_node.tree_version.technical_domain
    _require_domain_scope(actor=actor, domain=technical_domain, permission="standards.change_skilltreenode")
    locked_parent = node_by_id.get(new_parent.pk) if new_parent is not None else None
    if new_parent is not None and locked_parent is None:
        raise ValidationError("目标父技能必须属于当前技能树版本。")
    subtree_ids = _subtree_ids(nodes, locked_node.pk)
    if locked_parent is not None and locked_parent.pk in subtree_ids:
        raise ValidationError("不能把技能移动到自身或其下级技能中。")

    locked_node.parent = locked_parent
    locked_node.order = _next_sibling_order(
        tree_version=locked_node.tree_version,
        parent=locked_parent,
    )
    locked_node.save(update_fields=["parent", "order", "updated_at"])
    node.parent = locked_parent
    node.parent_id = locked_parent.pk if locked_parent else None
    node.order = locked_node.order
    return node


@transaction.atomic
def reorder_skill_tree_node(*, node, direction, actor):
    if direction not in {"up", "down"}:
        raise ValidationError("不支持的排序方向。")
    _lock_tree(node.tree_version)
    locked_node = SkillTreeNode.objects.select_related("tree_version__technical_domain").get(pk=node.pk)
    _require_domain_scope(
        actor=actor,
        domain=locked_node.technical_domain,
        permission="standards.change_skilltreenode",
    )
    siblings = list(
        SkillTreeNode.objects.select_for_update()
        .filter(
            tree_version=locked_node.tree_version,
            parent_id=locked_node.parent_id,
        )
        .order_by("order", "pk")
    )
    index = next(position for position, sibling in enumerate(siblings) if sibling.pk == locked_node.pk)
    target_index = index - 1 if direction == "up" else index + 1
    if 0 <= target_index < len(siblings):
        siblings[index], siblings[target_index] = siblings[target_index], siblings[index]
    now = timezone.now()
    for position, sibling in enumerate(siblings, start=1):
        sibling.order = position * 10
        sibling.updated_at = now
    SkillTreeNode.objects.bulk_update(siblings, ["order", "updated_at"])
    node.order = next(sibling.order for sibling in siblings if sibling.pk == node.pk)
    return node


@transaction.atomic
def remove_skill_tree_node(*, node, mode, actor):
    if mode not in {"promote_children", "subtree"}:
        raise ValidationError("不支持的移除方式。")
    _lock_tree(node.tree_version)
    nodes = _locked_tree_nodes(node.tree_version)
    node_by_id = {item.pk: item for item in nodes}
    locked_node = node_by_id[node.pk]
    _require_domain_scope(
        actor=actor,
        domain=locked_node.technical_domain,
        permission="standards.delete_skilltreenode",
    )
    subtree_ids = _subtree_ids(nodes, locked_node.pk)
    if mode == "subtree":
        SkillTreeNode.objects.filter(pk=locked_node.pk).delete()
        return len(subtree_ids)

    siblings = sorted(
        (
            item
            for item in nodes
            if item.parent_id == locked_node.parent_id
        ),
        key=lambda item: (item.order, item.pk),
    )
    children = sorted(
        (item for item in nodes if item.parent_id == locked_node.pk),
        key=lambda item: (item.order, item.pk),
    )
    expanded = []
    for sibling in siblings:
        expanded.extend(children if sibling.pk == locked_node.pk else [sibling])
    now = timezone.now()
    for position, sibling in enumerate(expanded, start=1):
        if sibling.parent_id == locked_node.pk:
            sibling.parent_id = locked_node.parent_id
        sibling.order = position * 10
        sibling.updated_at = now
    if expanded:
        SkillTreeNode.objects.bulk_update(expanded, ["parent", "order", "updated_at"])
    locked_node.delete()
    return 1


@transaction.atomic
def clone_skill_tree_version(*, source_version, version, name, description, actor):
    if not actor.is_superuser:
        raise PermissionDenied
    source_version = (
        SkillTreeVersion.objects.select_for_update()
        .select_related("technical_domain", "technical_domain__skill_project")
        .get(pk=source_version.pk)
    )
    if SkillTreeVersion.objects.filter(
        technical_domain=source_version.technical_domain,
        version=version,
    ).exists():
        raise ValidationError({"version": "该技术领域已存在相同版本号。"})
    target = SkillTreeVersion.objects.create(
        technical_domain=source_version.technical_domain,
        based_on=source_version,
        version=version,
        name=name,
        description=description,
        is_current=False,
        created_by=actor,
    )
    source_nodes = list(
        SkillTreeNode.objects.filter(tree_version=source_version)
        .select_related("parent")
        .order_by("order", "pk")
    )
    new_nodes = SkillTreeNode.objects.bulk_create(
        [
            SkillTreeNode(
                tree_version=target,
                skill_id=node.skill_id,
                order=node.order,
            )
            for node in source_nodes
        ]
    )
    old_to_new = {old.pk: new for old, new in zip(source_nodes, new_nodes, strict=True)}
    for old, new in zip(source_nodes, new_nodes, strict=True):
        if old.parent_id:
            new.parent = old_to_new[old.parent_id]
    SkillTreeNode.objects.bulk_update(new_nodes, ["parent"])
    return target


@transaction.atomic
def set_current_skill_tree_version(*, tree_version, actor):
    if not actor.is_superuser:
        raise PermissionDenied
    tree_version = (
        SkillTreeVersion.objects.select_for_update()
        .select_related("technical_domain")
        .get(pk=tree_version.pk)
    )
    SkillTreeVersion.objects.filter(
        technical_domain=tree_version.technical_domain,
        is_current=True,
    ).exclude(pk=tree_version.pk).update(is_current=False)
    if not tree_version.is_current:
        tree_version.is_current = True
        tree_version.save(update_fields=["is_current", "updated_at"])
    return tree_version


@transaction.atomic
def map_skill_to_wsos_section(*, skill, section, actor, note=""):
    if not actor.is_superuser:
        raise PermissionDenied
    if skill.skill_project_id != section.wsos_version.skill_project_id:
        raise ValidationError("技能与 WSOS 章节必须属于同一技能项目。")
    mapping = SkillWSOSMap.objects.filter(skill=skill, wsos_section=section).first()
    if mapping is not None:
        return mapping, False
    mapping = SkillWSOSMap.objects.create(skill=skill, wsos_section=section, note=note.strip())
    return mapping, True


@transaction.atomic
def update_skill_wsos_map_note(*, mapping, note, actor):
    if not actor.is_superuser:
        raise PermissionDenied
    mapping.note = note.strip()
    mapping.save(update_fields=["note"])
    return mapping


@transaction.atomic
def unmap_skill_from_wsos_section(*, mapping, actor):
    if not actor.is_superuser:
        raise PermissionDenied
    mapping.delete()


@transaction.atomic
def delete_wsos_section(*, section: WSOSSection, actor):
    if not actor.is_superuser:
        raise PermissionDenied
    if section.skill_mappings.exists():
        raise ValidationError("该章节已有技能映射，请先解除映射后再删除。")
    section.delete()
