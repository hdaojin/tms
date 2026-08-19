from __future__ import annotations

from difflib import SequenceMatcher
from unicodedata import normalize

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Skill, SkillTerm


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

    requested_pk = None
    if normalized_query.startswith("sk-"):
        suffix = normalized_query[3:]
        if suffix.isdigit():
            requested_pk = int(suffix)

    candidates = []
    for skill in queryset:
        term_scores = [
            _term_similarity(normalized_query, normalize_skill_term(term.term))
            for term in skill.terms.all()
        ]
        if not term_scores:
            term_scores = [_term_similarity(normalized_query, normalize_skill_term(skill.name))]
        score = max(term_scores)
        description_match = normalized_query in normalize_skill_term(skill.description)
        code_match = requested_pk == skill.pk
        if description_match:
            score = max(score, 0.45)
        if code_match:
            score = 1.0
        if score < 0.45:
            continue
        skill.candidate_score = score
        skill.candidate_exact = score == 1.0 and not code_match
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
def save_skill(*, skill, aliases, related_domains, preserve_old_name=False, old_name=""):
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
def add_skill_alias(*, skill, term):
    term = term.strip()
    normalized_term = normalize_skill_term(term)
    if not normalized_term:
        raise ValidationError("别名不能为空。")
    existing = SkillTerm.objects.filter(
        skill_project=skill.skill_project,
        normalized_term=normalized_term,
    ).select_related("skill").first()
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
    skill.related_domains.set(domains)
    return skill
