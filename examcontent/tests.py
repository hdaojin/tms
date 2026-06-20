from django.test import TestCase
from django.utils import timezone

from events.models import Event, EventModule
from knowledge.models import KnowledgeEvidence
from standards.models import CapabilityDomain, SkillProject

from .models import ExamPaper, ExamRequirement
from .services import create_evidence_for_requirement


class ExamRequirementEvidenceTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NSM", name="网络系统管理")
        self.domain = CapabilityDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.event = Event.objects.create(
            skill_project=self.project,
            event_type=Event.EventType.COMPETITION,
            name="全国选拔赛",
            code="NSM-SELECT",
            start_date=timezone.localdate(),
        )
        self.module = EventModule.objects.create(event=self.event, code="A", name="Linux")
        self.paper = ExamPaper.objects.create(event_module=self.module, title="Module A")

    def test_manual_requirement_generates_approved_evidence(self):
        requirement = ExamRequirement.objects.create(
            paper=self.paper,
            capability_domain=self.domain,
            code="REQ-1",
            title="配置 SSH",
            original_text="SSH service must be reachable.",
        )

        evidence = create_evidence_for_requirement(requirement)

        self.assertEqual(evidence.skill_project, self.project)
        self.assertEqual(evidence.event_module, self.module)
        self.assertEqual(evidence.capability_domain, self.domain)
        self.assertEqual(evidence.source_type, KnowledgeEvidence.SourceType.EXAM_REQUIREMENT)
        self.assertEqual(evidence.review_status, KnowledgeEvidence.ReviewStatus.APPROVED)
