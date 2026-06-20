from django.core.exceptions import ValidationError
from django.test import TestCase

from standards.models import CapabilityDomain, SkillNode, SkillProject, SkillTreeVersion

from .forms import KnowledgeEvidenceForm, KnowledgeEvidenceSkillMapForm
from .models import KnowledgeEvidence, KnowledgeEvidenceSkillMap
from .selectors import get_evidence_mapping_summary, get_unmapped_evidences


class KnowledgeMappingTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NSM", name="网络系统管理")
        self.linux = CapabilityDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.tree = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="v1",
            name="v1",
            is_current=True,
        )
        self.old_tree = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="v0",
            name="v0",
            is_current=False,
        )
        self.category = SkillNode.objects.create(
            tree_version=self.tree,
            capability_domain=self.linux,
            node_type=SkillNode.NodeType.CATEGORY,
            code="LINUX",
            name="Linux",
        )
        self.skill = SkillNode.objects.create(
            tree_version=self.tree,
            capability_domain=self.linux,
            parent=self.category,
            node_type=SkillNode.NodeType.SKILL,
            code="SSH",
            name="SSH 服务",
        )
        self.inactive_skill = SkillNode.objects.create(
            tree_version=self.tree,
            capability_domain=self.linux,
            parent=self.category,
            node_type=SkillNode.NodeType.SKILL,
            code="FTP",
            name="FTP 服务",
            is_active=False,
        )
        old_category = SkillNode.objects.create(
            tree_version=self.old_tree,
            capability_domain=self.linux,
            node_type=SkillNode.NodeType.CATEGORY,
            code="OLD-LINUX",
            name="旧 Linux",
        )
        self.old_skill = SkillNode.objects.create(
            tree_version=self.old_tree,
            capability_domain=self.linux,
            parent=old_category,
            node_type=SkillNode.NodeType.SKILL,
            code="OLD-SSH",
            name="旧 SSH",
        )
        self.evidence = KnowledgeEvidence.objects.create(
            skill_project=self.project,
            capability_domain=self.linux,
            source_type=KnowledgeEvidence.SourceType.MANUAL,
            extraction_source=KnowledgeEvidence.ExtractionSource.MANUAL,
            title="配置 SSH",
            estimated_mark="10.00",
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )

    def test_manual_evidence_form_defaults_to_approved(self):
        form = KnowledgeEvidenceForm()

        self.assertEqual(form.fields["source_type"].initial, KnowledgeEvidence.SourceType.MANUAL)
        self.assertEqual(form.fields["extraction_source"].initial, KnowledgeEvidence.ExtractionSource.MANUAL)
        self.assertEqual(form.fields["review_status"].initial, KnowledgeEvidence.ReviewStatus.APPROVED)

    def test_mapping_form_limits_to_current_active_skill_nodes(self):
        form = KnowledgeEvidenceSkillMapForm(evidence=self.evidence)

        self.assertIn(self.skill, form.fields["skill_node"].queryset)
        self.assertNotIn(self.category, form.fields["skill_node"].queryset)
        self.assertNotIn(self.inactive_skill, form.fields["skill_node"].queryset)
        self.assertNotIn(self.old_skill, form.fields["skill_node"].queryset)

    def test_mapping_rejects_non_skill_inactive_or_non_current_nodes(self):
        for node in (self.category, self.inactive_skill, self.old_skill):
            with self.subTest(node=node.code), self.assertRaises(ValidationError):
                KnowledgeEvidenceSkillMap.objects.create(
                    evidence=self.evidence,
                    skill_node=node,
                    review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
                )

    def test_unmapped_and_weighted_summary_use_approved_only(self):
        KnowledgeEvidenceSkillMap.objects.create(
            evidence=self.evidence,
            skill_node=self.skill,
            weight="0.50",
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )
        unmapped = KnowledgeEvidence.objects.create(
            skill_project=self.project,
            capability_domain=self.linux,
            source_type=KnowledgeEvidence.SourceType.MANUAL,
            title="未映射考点",
            estimated_mark="5.00",
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )
        draft_mapping_evidence = KnowledgeEvidence.objects.create(
            skill_project=self.project,
            capability_domain=self.linux,
            source_type=KnowledgeEvidence.SourceType.MANUAL,
            title="只有待审映射",
            estimated_mark="8.00",
            review_status=KnowledgeEvidence.ReviewStatus.APPROVED,
        )
        KnowledgeEvidenceSkillMap.objects.create(
            evidence=draft_mapping_evidence,
            skill_node=self.skill,
            weight="1.00",
            review_status=KnowledgeEvidence.ReviewStatus.PENDING,
        )

        self.assertQuerySetEqual(
            get_unmapped_evidences(self.project).order_by("pk"),
            [unmapped, draft_mapping_evidence],
            transform=lambda item: item,
        )
        summary = get_evidence_mapping_summary(self.project)
        self.assertEqual(summary["total_evidence_count"], 3)
        self.assertEqual(summary["mapped_evidence_count"], 1)
        self.assertEqual(summary["unmapped_evidence_count"], 2)
        self.assertEqual(summary["weighted_mark"], 5)

    def test_reject_requires_note(self):
        with self.assertRaises(ValidationError):
            self.evidence.reject(note="")
