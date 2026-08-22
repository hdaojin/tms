from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from .models import Skill, SkillProject, SkillTreeNode, SkillTreeVersion, TechnicalDomain, WSOSVersion


User = get_user_model()


class DomainSkillTreePageTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理", is_default=True)
        self.linux = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.windows = TechnicalDomain.objects.create(skill_project=self.project, code="WINDOWS", name="Windows")
        self.linux_tree = SkillTreeVersion.objects.create(
            technical_domain=self.linux,
            version="2026",
            name="Linux 2026",
            is_current=True,
        )
        self.windows_tree = SkillTreeVersion.objects.create(
            technical_domain=self.windows,
            version="2025",
            name="Windows 2025",
            is_current=True,
        )
        self.user = User.objects.create_user(username="tree-page-admin")
        self.user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="standards",
                codename__in=[
                    "manage_all_technical_domains",
                    "view_skillproject",
                    "view_skilltreeversion",
                    "view_skill",
                    "add_skilltreenode",
                    "add_skill",
                    "add_skilltreeversion",
                    "change_skilltreeversion",
                    "change_skilltreenode",
                ],
            )
        )
        self.client.force_login(self.user)

    def node(self, skill, tree=None):
        return SkillTreeNode.objects.create(tree_version=tree or self.linux_tree, skill=skill)

    def test_project_detail_shows_each_domain_current_version(self):
        WSOSVersion.objects.create(
            skill_project=self.project,
            code="WSOS-2026",
            name="WSOS 2026",
            is_current=True,
        )
        skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="Linux 服务")
        self.node(skill)

        response = self.client.get(reverse("standards:project_detail", args=[self.project.pk]))

        self.assertContains(response, "当前技能树：2026 · 1 个节点")
        self.assertContains(response, "当前技能树：2025 · 0 个节点")
        self.assertContains(response, "当前 WSOS：WSOS 2026")
        self.assertContains(
            response,
            reverse("standards:current_domain_tree", args=[self.project.pk, self.linux.pk]),
        )

    def test_current_tree_entry_and_missing_domain_current_tree(self):
        response = self.client.get(reverse("standards:current_tree_entry"))
        self.assertRedirects(
            response,
            reverse("standards:project_detail", args=[self.project.pk]),
            fetch_redirect_response=False,
        )

        self.linux_tree.is_current = False
        self.linux_tree.save()
        response = self.client.get(
            reverse("standards:current_domain_tree", args=[self.project.pk, self.linux.pk])
        )
        self.assertContains(response, "当前技术领域尚未设置当前技能树版本")
        self.assertContains(
            response,
            reverse("standards:domain_tree_create", args=[self.project.pk, self.linux.pk]),
        )

    def test_current_domain_pages_only_render_their_own_tree(self):
        linux_skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="Linux 服务")
        windows_skill = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.windows,
            name="Windows 服务",
        )
        self.node(linux_skill, self.linux_tree)
        self.node(windows_skill, self.windows_tree)

        response = self.client.get(
            reverse("standards:current_domain_tree", args=[self.project.pk, self.linux.pk])
        )
        self.assertContains(response, linux_skill.name)
        self.assertNotContains(response, windows_skill.name)

        list_response = self.client.get(
            reverse("standards:current_domain_tree_list", args=[self.project.pk, self.linux.pk])
        )
        self.assertContains(list_response, linux_skill.name)
        self.assertNotContains(list_response, windows_skill.name)

    def test_unmounted_skill_can_be_attached_without_domain_url_parameter(self):
        skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="未挂载技能")
        unmounted_url = reverse("standards:tree_unmounted_skills", args=[self.linux_tree.pk])
        attach_url = reverse(
            "standards:tree_attach_existing_skill",
            args=[self.linux_tree.pk, skill.pk],
        )

        listed = self.client.get(unmounted_url, HTTP_HX_REQUEST="true")
        attached = self.client.post(attach_url, {"new_parent": ""}, HTTP_HX_REQUEST="true")

        self.assertContains(listed, skill.name)
        self.assertEqual(attached.status_code, 200)
        self.assertTrue(SkillTreeNode.objects.filter(tree_version=self.linux_tree, skill=skill).exists())
        self.assertNotContains(self.client.get(unmounted_url), skill.name)

    def test_old_project_level_routes_are_hard_removed(self):
        for name in (
            "skill_catalog",
            "skill_tree",
            "skill_tree_create",
            "domain_skill_tree",
            "tree_domain_detail",
        ):
            with self.assertRaises(NoReverseMatch):
                reverse(f"standards:{name}", args=[self.project.pk, self.linux.pk])
