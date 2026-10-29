from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from glossary.models import ProfessionalGlossary
from standards.models import SkillProject


class GlossaryActionVisibilityTests(TestCase):
    def test_read_and_change_permissions_do_not_imply_create(self):
        user = get_user_model().objects.create_user("glossary-action-viewer")
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="glossary",
                codename__in=["change_professionalglossary", "view_glossaryentry", "view_glossaryimport"],
            )
        )
        project = SkillProject.objects.create(code="ACTION", name="操作入口")
        glossary = ProfessionalGlossary.objects.create(skill_project=project, name="词库")
        self.client.force_login(user)
        cases = [
            ("glossary_list", [], "glossary_create", "add_professionalglossary"),
            ("manage_entry_list", [glossary.pk], "entry_create", "add_glossaryentry"),
            ("import_list", [], "import_create", "add_glossaryimport"),
        ]
        for page, args, action, permission in cases:
            with self.subTest(page=page):
                response = self.client.get(reverse(f"glossary:{page}", args=args))
                self.assertNotContains(response, reverse(f"glossary:{action}"))
                self.assertEqual(self.client.get(reverse(f"glossary:{action}")).status_code, 403)
                user.user_permissions.add(
                    Permission.objects.get(content_type__app_label="glossary", codename=permission)
                )
                self.assertContains(
                    self.client.get(reverse(f"glossary:{page}", args=args)), reverse(f"glossary:{action}")
                )
