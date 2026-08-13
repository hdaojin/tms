from django.core.exceptions import ValidationError
from django.test import TestCase

from knowledge.models import KnowledgeEvidence, KnowledgeEvidenceSkillMap
from knowledge.selectors import get_skill_tree_coverage_summary

from .forms import SkillTreeVersionForm
from .models import CapabilityDomain, SkillNode, SkillProject, SkillTreeVersion
from .services import set_current_skill_tree_version


class SkillTreeModelTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NSM", name="网络系统管理")
        self.linux = CapabilityDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.tree = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="v1",
            name="标准技能树 v1",
        )
        self.tree = set_current_skill_tree_version(self.tree)

    def test_project_is_not_duplicated_by_competition_level(self):
        replacement = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="v2",
            name="标准技能树 v2",
        )
        set_current_skill_tree_version(replacement)

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
            SkillNode(
                tree_version=self.tree,
                capability_domain=self.linux,
                node_type=SkillNode.NodeType.TOPIC,
                code="BAD",
                name="错误根节点",
            ).full_clean()

    def test_current_version_switch_is_atomic_and_project_scoped(self):
        other_project = SkillProject.objects.create(code="WIN", name="Windows")
        other_domain = CapabilityDomain.objects.create(skill_project=other_project, code="WIN", name="Windows")
        other_tree = SkillTreeVersion.objects.create(
            skill_project=other_project,
            version="v1",
            name="Windows v1",
        )
        set_current_skill_tree_version(self.tree)
        set_current_skill_tree_version(other_tree)

        replacement = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="v2",
            name="标准技能树 v2",
        )
        set_current_skill_tree_version(replacement)

        self.assertFalse(SkillTreeVersion.objects.get(pk=self.tree.pk).is_current)
        self.assertTrue(SkillTreeVersion.objects.get(pk=replacement.pk).is_current)
        self.assertTrue(SkillTreeVersion.objects.get(pk=other_tree.pk).is_current)
        self.assertEqual(other_domain.skill_project_id, other_project.pk)

    def test_current_version_switch_rolls_back_when_target_save_fails(self):
        from unittest.mock import patch

        set_current_skill_tree_version(self.tree)
        replacement = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="v2",
            name="标准技能树 v2",
        )
        with patch.object(SkillTreeVersion, "save", side_effect=RuntimeError("保存失败")):
            with self.assertRaises(RuntimeError):
                set_current_skill_tree_version(replacement)

        self.assertTrue(SkillTreeVersion.objects.get(pk=self.tree.pk).is_current)
        self.assertFalse(SkillTreeVersion.objects.get(pk=replacement.pk).is_current)

    def test_normal_version_save_does_not_change_other_current_state(self):
        set_current_skill_tree_version(self.tree)
        self.tree.name = "更新名称"
        self.tree.save(update_fields=["name"])
        self.assertTrue(SkillTreeVersion.objects.get(pk=self.tree.pk).is_current)

    def test_form_allows_explicit_current_transition_for_service(self):
        form = SkillTreeVersionForm(
            data={
                "skill_project": self.project.pk,
                "version": "v2",
                "name": "标准技能树 v2",
                "description": "",
                "is_current": "on",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

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
