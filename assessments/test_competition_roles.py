from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .bootstrap import COMPETITION_ROLES
from .forms import CompetitionRoleForm
from .models import CompetitionRole


class CompetitionRoleEnglishNameTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="role-admin", password="test-password")
        self.client.force_login(self.user)

    def test_optional_english_name_can_be_created_updated_and_cleared(self):
        data = {"code": "new-role", "name": "新增角色", "category": "other", "order": 10, "is_active": "on"}
        response = self.client.get(reverse("assessments:competition_role_create"))
        self.assertContains(response, "角色英文名称")
        response = self.client.post(reverse("assessments:competition_role_create"), data)
        self.assertEqual(response.status_code, 302)
        role = CompetitionRole.objects.get(code="new-role")
        self.assertEqual(role.english_name, "")
        data["english_name"] = "New Role"
        url = reverse("assessments:competition_role_edit", args=[role.pk])
        self.assertEqual(self.client.post(url, data).status_code, 302)
        role.refresh_from_db()
        self.assertEqual(role.english_name, "New Role")
        self.assertContains(self.client.get(reverse("assessments:competition_role_list")), "New Role")
        data["english_name"] = ""
        self.assertEqual(self.client.post(url, data).status_code, 302)
        role.refresh_from_db()
        self.assertEqual(role.english_name, "")

    def test_new_categories_and_legacy_edit_compatibility(self):
        choices = dict(CompetitionRoleForm().fields["category"].choices)
        self.assertEqual(set(choices) - {""}, {"official", "expert", "competitor", "other"})
        for category in ("coach", "staff"):
            role = CompetitionRole.objects.create(code=f"legacy-{category}", name="历史角色", category=category)
            data = {"code": role.code, "name": role.name, "category": category, "order": 0}
            form = CompetitionRoleForm(data=data, instance=role)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertFalse(CompetitionRoleForm(data=data).is_valid())

    def test_default_roles_have_translations_and_confirmed_categories(self):
        roles = {row["code"]: row for row in COMPETITION_ROLES}
        self.assertEqual(len(roles), 16)
        self.assertTrue(all(row["english_name"] for row in roles.values()))
        self.assertEqual(roles["chief_expert"]["name"], "首席专家")
        self.assertEqual(roles["chief_expert"]["category"], "official")
        self.assertEqual(roles["coach"]["category"], "expert")
        self.assertEqual(roles["reserve_competitor"]["category"], "competitor")
        for code in ("interpreter", "staff", "team_leader", "observer"):
            self.assertEqual(roles[code]["category"], "other")
