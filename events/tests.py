from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from standards.models import CapabilityDomain, SkillProject

from .models import CompetitionLevel, CompetitionSeries, Event, EventModule, EventModuleCapabilityDomainMap


class EventDomainMappingTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NSM", name="网络系统管理")
        self.other_project = SkillProject.objects.create(code="WEB", name="Web 技术")
        self.linux = CapabilityDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.automation = CapabilityDomain.objects.create(
            skill_project=self.project,
            code="AUTO",
            name="Automation",
        )
        self.other_domain = CapabilityDomain.objects.create(skill_project=self.other_project, code="HTML", name="HTML")
        self.series = CompetitionSeries.objects.create(code="WSC", name="世界技能大赛")
        self.level = CompetitionLevel.objects.create(code="NATIONAL", name="国赛")
        self.event = Event.objects.create(
            skill_project=self.project,
            series=self.series,
            level=self.level,
            event_type=Event.EventType.COMPETITION,
            name="2026 全国选拔赛",
            code="NSM-2026-SELECT",
            start_date=timezone.localdate(),
        )
        self.module = EventModule.objects.create(event=self.event, code="A", name="Linux + Automation")

    def test_event_level_does_not_duplicate_skill_project(self):
        Event.objects.create(
            skill_project=self.project,
            series=self.series,
            level=self.level,
            event_type=Event.EventType.MOCK_EXAM,
            name="省赛模拟赛",
            code="NSM-2026-MOCK",
            start_date=timezone.localdate(),
        )

        self.assertEqual(SkillProject.objects.filter(code="NSM").count(), 1)
        self.assertEqual(Event.objects.filter(skill_project=self.project).count(), 2)

    def test_event_module_maps_multiple_capability_domains(self):
        EventModuleCapabilityDomainMap.objects.create(
            event_module=self.module,
            capability_domain=self.linux,
            is_primary=True,
            weight="0.70",
        )
        EventModuleCapabilityDomainMap.objects.create(
            event_module=self.module,
            capability_domain=self.automation,
            weight="0.30",
        )

        self.assertEqual(self.module.domain_mappings.count(), 2)
        self.assertEqual(self.module.domain_mappings.get(is_primary=True).capability_domain, self.linux)

    def test_event_module_domain_must_belong_to_project_and_primary_is_unique(self):
        EventModuleCapabilityDomainMap.objects.create(
            event_module=self.module,
            capability_domain=self.linux,
            is_primary=True,
        )

        with self.assertRaises(ValidationError):
            EventModuleCapabilityDomainMap.objects.create(
                event_module=self.module,
                capability_domain=self.other_domain,
            )
        with self.assertRaises(ValidationError):
            EventModuleCapabilityDomainMap.objects.create(
                event_module=self.module,
                capability_domain=self.automation,
                is_primary=True,
            )
