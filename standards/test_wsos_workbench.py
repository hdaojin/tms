from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .models import Skill, SkillProject, SkillWSOSMap, TechnicalDomain, WSOSSection, WSOSVersion
from .services import delete_wsos_section, map_skill_to_wsos_section


User = get_user_model()


class WSOSWorkbenchTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.linux = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.windows = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="WIN",
            name="Windows",
        )
        self.wsos = WSOSVersion.objects.create(
            skill_project=self.project,
            code="2026",
            name="WSOS 2026",
            is_current=True,
        )
        self.section = WSOSSection.objects.create(
            wsos_version=self.wsos,
            code="1",
            name="工作组织",
            weight=40,
        )
        self.other_section = WSOSSection.objects.create(
            wsos_version=self.wsos,
            code="2",
            name="故障排除",
            weight=50,
        )
        self.skill = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.linux,
            name="DNS 服务",
        )
        self.user = User.objects.create_user(username="wsos-admin")
        self.user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="standards",
                codename__in=[
                    "view_wsosversion",
                    "add_wsossection",
                    "change_wsossection",
                    "delete_wsossection",
                    "view_skillwsosmap",
                    "add_skillwsosmap",
                    "change_skillwsosmap",
                    "delete_skillwsosmap",
                    "view_skill",
                ],
            )
        )
        self.user = User.objects.get(pk=self.user.pk)
        self.client.force_login(self.user)

    def test_detail_shows_sections_mapping_count_and_weight_warning(self):
        SkillWSOSMap.objects.create(skill=self.skill, wsos_section=self.section, note="重点")
        self.skill.is_active = False
        self.skill.save()
        response = self.client.get(reverse("standards:wsos_detail", args=[self.wsos.pk]))
        self.assertContains(response, "工作组织")
        self.assertContains(response, "1 个技能")
        self.assertContains(response, "90%")
        self.assertContains(response, "当前章节权重合计不是 100%")
        self.assertContains(response, "DNS 服务")
        self.assertContains(response, "重点")
        self.assertContains(response, "已停用")

    def test_candidate_search_filters_domain_and_excludes_mapped_and_inactive(self):
        windows_skill = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.windows,
            name="Windows 防火墙",
        )
        inactive = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.linux,
            name="停用服务",
            is_active=False,
        )
        SkillWSOSMap.objects.create(skill=self.skill, wsos_section=self.section)
        response = self.client.get(
            reverse("standards:wsos_section_skill_candidates", args=[self.section.pk]),
            {"domain": self.windows.pk},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, windows_skill.name)
        self.assertNotContains(response, self.skill.name)
        self.assertNotContains(response, inactive.name)

    def test_duplicate_mapping_does_not_overwrite_note(self):
        mapping, created = map_skill_to_wsos_section(
            skill=self.skill,
            section=self.section,
            actor=self.user,
            note="原说明",
        )
        same, created_again = map_skill_to_wsos_section(
            skill=self.skill,
            section=self.section,
            actor=self.user,
            note="不应覆盖",
        )
        same.refresh_from_db()
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(same.pk, mapping.pk)
        self.assertEqual(same.note, "原说明")

    def test_mapping_note_can_be_edited_and_unmapped(self):
        mapping = SkillWSOSMap.objects.create(skill=self.skill, wsos_section=self.section, note="旧说明")
        response = self.client.post(
            reverse("standards:wsos_mapping_edit", args=[mapping.pk]),
            {"note": "新说明"},
        )
        self.assertEqual(response.status_code, 302)
        mapping.refresh_from_db()
        self.assertEqual(mapping.note, "新说明")

        response = self.client.post(reverse("standards:wsos_mapping_delete", args=[mapping.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SkillWSOSMap.objects.filter(pk=mapping.pk).exists())

    def test_section_with_mapping_must_be_unmapped_before_delete(self):
        mapping = SkillWSOSMap.objects.create(skill=self.skill, wsos_section=self.section)
        with self.assertRaisesMessage(ValidationError, "先解除映射"):
            delete_wsos_section(section=self.section, actor=self.user)
        with self.assertRaises(ProtectedError):
            self.section.delete()
        mapping.delete()
        delete_wsos_section(section=self.section, actor=self.user)
        self.assertFalse(WSOSSection.objects.filter(pk=self.section.pk).exists())

    def test_section_create_uses_url_wsos_context(self):
        response = self.client.post(
            reverse("standards:wsos_section_create", args=[self.wsos.pk]),
            {
                "code": "3",
                "name": "新章节",
                "description": "",
                "weight": "10",
                "order": 30,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.wsos.sections.filter(code="3", name="新章节").exists())
