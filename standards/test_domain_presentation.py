from django import forms
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .forms import TechnicalDomainForm
from .models import SkillProject, SkillTreeVersion, TechnicalDomain


class TechnicalDomainPresentationTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.domain = TechnicalDomain.objects.create(
            skill_project=self.project, code="HIDDEN_DOMAIN_CODE", name="网络服务", is_active=False
        )

    def test_name_and_code_are_unique_including_inactive_domains(self):
        for code, name in [("OTHER", self.domain.name), (self.domain.code, "其他领域")]:
            with self.subTest(code=code, name=name):
                form = TechnicalDomainForm(
                    data={"skill_project": self.project.pk, "code": code, "name": name, "order": 0}
                )
                self.assertFalse(form.is_valid())
                with self.assertRaises(IntegrityError), transaction.atomic():
                    TechnicalDomain.objects.create(skill_project=self.project, code=code, name=name)

    def test_other_project_can_reuse_name_and_code_and_edit_can_keep_them(self):
        other = SkillProject.objects.create(code="OTHER", name="其他项目")
        TechnicalDomain.objects.create(skill_project=other, code=self.domain.code, name=self.domain.name)
        form = TechnicalDomainForm(
            instance=self.domain,
            data={
                "skill_project": self.project.pk,
                "code": self.domain.code,
                "name": self.domain.name,
                "order": 0,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_reference_labels_only_use_domain_name(self):
        tree = SkillTreeVersion.objects.create(
            technical_domain=self.domain, name="标准版", version="2026", is_current=True
        )
        self.assertEqual(str(self.domain), "网络服务")
        self.assertEqual(str(tree), "网络服务 / 标准版 2026（当前）")
        field = forms.ModelChoiceField(queryset=TechnicalDomain.objects.all())
        self.assertEqual(field.label_from_instance(self.domain), "网络服务")

    def test_display_pages_hide_domain_code_but_edit_keeps_it(self):
        self.domain.is_active = True
        self.domain.save()
        tree = SkillTreeVersion.objects.create(
            technical_domain=self.domain, name="标准版", version="2026", is_current=True
        )
        user = get_user_model().objects.create_superuser(username="domain-admin", password="test-password")
        self.client.force_login(user)
        pages = [
            ("project_detail", [self.project.pk]),
            ("current_domain_tree", [self.project.pk, self.domain.pk]),
            ("current_domain_tree_list", [self.project.pk, self.domain.pk]),
            ("tree_detail", [tree.pk]),
            ("tree_list", []),
        ]
        for name, args in pages:
            with self.subTest(page=name):
                response = self.client.get(reverse(f"standards:{name}", args=args))
                self.assertContains(response, self.domain.name)
                self.assertNotContains(response, self.domain.code)
        response = self.client.get(
            reverse("standards:domain_edit", args=[self.project.pk, self.domain.pk])
        )
        self.assertContains(response, self.domain.code)
