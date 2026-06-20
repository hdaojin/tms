from django.core.exceptions import ValidationError
from django.test import TestCase

from knowledge.models import KnowledgeEvidence, KnowledgeEvidenceSkillMap
from knowledge.selectors import get_skill_tree_coverage_summary

from .models import CapabilityDomain, SkillNode, SkillProject, SkillTreeVersion


class SkillTreeModelTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NSM", name="网络系统管理")
        self.linux = CapabilityDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.tree = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="v1",
            name="标准技能树 v1",
            is_current=True,
        )

    def test_project_is_not_duplicated_by_competition_level(self):
        SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="v2",
            name="标准技能树 v2",
            is_current=True,
        )

        self.tree.refresh_from_db()
        self.assertEqual(SkillProject.objects.count(), 1)
        self.assertFalse(self.tree.is_current)
        self.assertTrue(SkillTreeVersion.objects.get(version="v2").is_current)

    def test_node_path_helpers_and_level_rules(self):
        category = SkillNode.objects.create(
            tree_version=self.tree,
            capability_domain=self.linux,
            node_type=SkillNode.NodeType.CATEGORY,
            code="LINUX",
            name="Linux",
        )
        topic = SkillNode.objects.create(
            tree_version=self.tree,
            capability_domain=self.linux,
            parent=category,
            node_type=SkillNode.NodeType.TOPIC,
            code="USER",
            name="用户与权限",
        )
        skill = SkillNode.objects.create(
            tree_version=self.tree,
            capability_domain=self.linux,
            parent=topic,
            node_type=SkillNode.NodeType.SKILL,
            code="USER-ADD",
            name="创建本地用户",
        )

        self.assertTrue(skill.is_skill())
        self.assertEqual(skill.get_ancestors(), [category, topic])
        self.assertEqual(skill.get_descendants(), [])
        self.assertIn("LINUX Linux", skill.get_full_path())
        self.assertEqual(category.get_descendants(), [topic, skill])

        with self.assertRaises(ValidationError):
            SkillNode.objects.create(
                tree_version=self.tree,
                capability_domain=self.linux,
                node_type=SkillNode.NodeType.TOPIC,
                code="BAD",
                name="错误根节点",
            )

    def test_coverage_summary_counts_only_approved_evidence_and_mapping(self):
        category = SkillNode.objects.create(
            tree_version=self.tree,
            capability_domain=self.linux,
            node_type=SkillNode.NodeType.CATEGORY,
            code="LINUX",
            name="Linux",
        )
        skill = SkillNode.objects.create(
            tree_version=self.tree,
            capability_domain=self.linux,
            parent=category,
            node_type=SkillNode.NodeType.SKILL,
            code="SSH",
            name="SSH 服务",
        )
        evidence = KnowledgeEvidence.objects.create(
            skill_project=self.project,
            capability_domain=self.linux,
            source_type=KnowledgeEvidence.SourceType.MANUAL,
            title="配置 SSH 服务",
            estimated_mark="4.00",
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )
        KnowledgeEvidenceSkillMap.objects.create(
            evidence=evidence,
            skill_node=skill,
            weight="0.50",
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )
        draft = KnowledgeEvidence.objects.create(
            skill_project=self.project,
            capability_domain=self.linux,
            source_type=KnowledgeEvidence.SourceType.MANUAL,
            title="待审核考点",
            estimated_mark="8.00",
            review_status=KnowledgeEvidence.ReviewStatus.PENDING,
        )
        KnowledgeEvidenceSkillMap.objects.create(
            evidence=draft,
            skill_node=skill,
            weight="1.00",
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )

        summary = get_skill_tree_coverage_summary(self.tree)

        self.assertEqual(summary["covered_skill_count"], 1)
        self.assertEqual(summary["uncovered_skill_count"], 0)
        self.assertEqual(summary["evidence_count"], 1)
        self.assertEqual(summary["weighted_mark"], 2)
