from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, Exists, ExpressionWrapper, F, OuterRef, Sum, Value
from django.db.models.functions import Coalesce

from .models import KnowledgeEvidence, KnowledgeEvidenceSkillMap


APPROVED = KnowledgeEvidence.ReviewStatus.APPROVED


def approved_evidences():
    return KnowledgeEvidence.objects.filter(review_status=APPROVED)


def approved_mappings():
    return KnowledgeEvidenceSkillMap.objects.filter(
        review_status=APPROVED,
        evidence__review_status=APPROVED,
        skill_node__is_active=True,
        skill_node__tree_version__is_current=True,
    )


def get_unmapped_evidences(skill_project=None, capability_domain=None):
    mapped = approved_mappings().filter(evidence_id=OuterRef("pk"))
    qs = approved_evidences().annotate(has_approved_mapping=Exists(mapped)).filter(has_approved_mapping=False)
    if skill_project is not None:
        qs = qs.filter(skill_project=skill_project)
    if capability_domain is not None:
        qs = qs.filter(capability_domain=capability_domain)
    return qs.select_related("skill_project", "event_module", "capability_domain")


def get_skill_node_evidences(skill_node):
    return approved_evidences().filter(
        skill_mappings__skill_node=skill_node,
        skill_mappings__review_status=APPROVED,
    ).distinct()


def get_skill_tree_coverage_rows(tree_version):
    mappings = list(
        approved_mappings()
        .filter(skill_node__tree_version=tree_version)
        .select_related("evidence", "skill_node", "skill_node__capability_domain")
    )
    direct = {}
    for mapping in mappings:
        mark = mapping.evidence.estimated_mark or Decimal("0.00")
        weighted_mark = mark * mapping.weight
        stats = direct.setdefault(
            mapping.skill_node_id,
            {"evidence_count": 0, "weighted_mark": Decimal("0.00")},
        )
        stats["evidence_count"] += 1
        stats["weighted_mark"] += weighted_mark

    rows = []
    nodes = list(
        tree_version.nodes.select_related("capability_domain", "parent")
        .order_by("capability_domain__order", "parent_id", "order", "code", "pk")
    )
    node_by_id = {node.pk: node for node in nodes}
    children_by_parent_id = {}
    for node in nodes:
        children_by_parent_id.setdefault(node.parent_id, []).append(node)
    for children in children_by_parent_id.values():
        children.sort(key=lambda node: (node.order, node.code, node.name, node.pk))

    subtree_stats_by_id = {}
    zero_stats = (0, 0, Decimal("0.00"))

    def get_subtree_stats(node_id, visiting=None):
        if node_id in subtree_stats_by_id:
            return subtree_stats_by_id[node_id]
        if visiting is None:
            visiting = set()
        if node_id in visiting:
            return zero_stats

        node = node_by_id.get(node_id)
        if node is None:
            return zero_stats

        visiting.add(node_id)
        if node.is_skill():
            if node.is_active:
                node_stats = direct.get(node.pk, {})
                result = (
                    1,
                    node_stats.get("evidence_count", 0),
                    node_stats.get("weighted_mark", Decimal("0.00")),
                )
            else:
                result = zero_stats
        else:
            skill_count = 0
            evidence_count = 0
            weighted_mark = Decimal("0.00")
            for child in children_by_parent_id.get(node_id, []):
                if not child.is_active:
                    continue
                child_skill_count, child_evidence_count, child_weighted_mark = get_subtree_stats(
                    child.pk,
                    visiting,
                )
                skill_count += child_skill_count
                evidence_count += child_evidence_count
                weighted_mark += child_weighted_mark
            result = (skill_count, evidence_count, weighted_mark)
        visiting.remove(node_id)
        subtree_stats_by_id[node_id] = result
        return result

    for node in nodes:
        node_direct = direct.get(node.pk, {"evidence_count": 0, "weighted_mark": Decimal("0.00")})
        subtree_skill_count, subtree_evidence, subtree_mark = get_subtree_stats(node.pk)
        rows.append(
            {
                "node": node,
                "direct_evidence_count": node_direct["evidence_count"],
                "direct_weighted_mark": node_direct["weighted_mark"],
                "subtree_skill_count": subtree_skill_count,
                "subtree_evidence_count": subtree_evidence,
                "subtree_weighted_mark": subtree_mark,
                "is_covered": subtree_evidence > 0,
                "parent": node_by_id.get(node.parent_id),
            }
        )
    return rows


def get_skill_tree_coverage_summary(tree_version):
    rows = get_skill_tree_coverage_rows(tree_version)
    skill_rows = [row for row in rows if row["node"].is_skill() and row["node"].is_active]
    return {
        "node_count": len(rows),
        "skill_count": len(skill_rows),
        "covered_skill_count": sum(1 for row in skill_rows if row["direct_evidence_count"] > 0),
        "uncovered_skill_count": sum(1 for row in skill_rows if row["direct_evidence_count"] == 0),
        "evidence_count": sum(row["direct_evidence_count"] for row in skill_rows),
        "weighted_mark": sum((row["direct_weighted_mark"] for row in skill_rows), Decimal("0.00")),
    }


def get_evidence_mapping_summary(skill_project):
    evidence_qs = approved_evidences().filter(skill_project=skill_project)
    mapped = approved_mappings().filter(evidence_id=OuterRef("pk"))
    rows = evidence_qs.annotate(has_approved_mapping=Exists(mapped))
    weighted_expr = ExpressionWrapper(
        Coalesce(
            F("evidence__estimated_mark"),
            Value(Decimal("0.00")),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )
        * F("weight"),
        output_field=DecimalField(max_digits=12, decimal_places=4),
    )
    weighted_mark = approved_mappings().filter(evidence__skill_project=skill_project).aggregate(
        total=Coalesce(Sum(weighted_expr), Decimal("0.0000"))
    )["total"]
    return {
        "total_evidence_count": rows.count(),
        "mapped_evidence_count": rows.filter(has_approved_mapping=True).count(),
        "unmapped_evidence_count": rows.filter(has_approved_mapping=False).count(),
        "weighted_mark": weighted_mark,
    }
