from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from .models import Skill, SkillProject, SkillTreeNode, SkillTreeVersion, TechnicalDomain, WSOSVersion


User = get_user_model()


class DomainSkillTreePageTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理", is_default=True)
        self.linux = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.windows = TechnicalDomain.objects.create(skill_project=self.project, code="WINDOWS", name="Windows")
        self.tree = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="2026",
            name="2026 技能树",
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
                    "change_skilltreenode",
                ],
            )
        )
        self.client.force_login(self.user)

    def node(self, skill, domain):
        return SkillTreeNode.objects.create(
            tree_version=self.tree,
            technical_domain=domain,
            skill=skill,
        )

    def test_project_detail_shows_current_versions_and_domain_tree_links(self):
        WSOSVersion.objects.create(skill_project=self.project, code="WSOS-2026", name="WSOS 2026", is_current=True)
        linux_skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="Linux 服务")
        self.node(linux_skill, self.linux)

        response = self.client.get(reverse("standards:project_detail", args=[self.project.pk]))

        self.assertContains(response, "当前技能树：2026 技能树（2026）")
        self.assertContains(response, "max-w-full break-words whitespace-normal")
        self.assertContains(response, "当前 WSOS：WSOS 2026")
        self.assertContains(
            response,
            reverse("standards:domain_current_tree", args=[self.project.pk, self.linux.pk]),
        )
        self.assertContains(response, "当前树 1 个节点")

    def test_current_tree_entry_uses_default_project_and_no_current_tree_has_empty_state(self):
        response = self.client.get(reverse("standards:current_tree_entry"))
        self.assertRedirects(
            response,
            reverse("standards:project_detail", args=[self.project.pk]),
            fetch_redirect_response=False,
        )

        self.tree.delete()
        response = self.client.get(
            reverse("standards:domain_current_tree", args=[self.project.pk, self.linux.pk])
        )
        self.assertContains(response, "当前技能项目尚未设置当前技能树版本。")

    def test_current_domain_tree_renders_only_its_domain_and_real_tab_links(self):
        linux_skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="Linux 服务")
        windows_skill = Skill.objects.create(skill_project=self.project, primary_domain=self.windows, name="Windows 服务")
        self.node(linux_skill, self.linux)
        self.node(windows_skill, self.windows)

        response = self.client.get(
            reverse("standards:domain_current_tree", args=[self.project.pk, self.linux.pk])
        )

        self.assertContains(response, linux_skill.name)
        self.assertNotContains(response, windows_skill.name)
        self.assertContains(
            response,
            reverse("standards:domain_current_tree", args=[self.project.pk, self.windows.pk]),
        )

    def test_tree_detail_redirects_to_its_first_domain(self):
        response = self.client.get(reverse("standards:tree_detail", args=[self.tree.pk]))

        self.assertRedirects(
            response,
            reverse("standards:tree_domain_detail", args=[self.tree.pk, self.linux.pk]),
            fetch_redirect_response=False,
        )

    def test_unmounted_skill_is_listed_then_can_be_attached(self):
        skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="未挂载技能")
        unmounted_url = reverse("standards:tree_unmounted_skills", args=[self.tree.pk, self.linux.pk])
        attach_url = reverse("standards:tree_attach_existing_skill", args=[self.tree.pk, self.linux.pk, skill.pk])

        listed = self.client.get(unmounted_url, HTTP_HX_REQUEST="true")
        attached = self.client.post(attach_url, {"new_parent": ""}, HTTP_HX_REQUEST="true")

        self.assertContains(listed, skill.name)
        self.assertEqual(attached.status_code, 200)
        self.assertTrue(SkillTreeNode.objects.filter(tree_version=self.tree, skill=skill).exists())
        self.assertContains(attached, skill.name)
        self.assertNotContains(self.client.get(unmounted_url), skill.name)

    def test_unmounted_skill_already_mounted_in_related_domain_is_not_leaked(self):
        skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="跨领域技能")
        skill.related_domains.add(self.windows)
        self.node(skill, self.windows)

        response = self.client.get(
            reverse("standards:tree_unmounted_skills", args=[self.tree.pk, self.linux.pk])
        )

        self.assertNotContains(response, skill.name)

    def test_cross_domain_move_uses_hx_location_and_normal_redirect(self):
        skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="跨领域技能")
        skill.related_domains.add(self.windows)
        node = self.node(skill, self.linux)
        url = reverse("standards:tree_node_move", args=[self.tree.pk, node.pk])
        destination = reverse("standards:tree_domain_detail", args=[self.tree.pk, self.windows.pk])

        response = self.client.post(
            url,
            {"target_domain": self.windows.pk, "new_parent": ""},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["HX-Location"], destination)
        node.refresh_from_db()
        self.assertEqual(node.technical_domain, self.windows)

        skill_2 = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="另一跨领域技能")
        skill_2.related_domains.add(self.windows)
        node_2 = self.node(skill_2, self.linux)
        response = self.client.post(
            reverse("standards:tree_node_move", args=[self.tree.pk, node_2.pk]),
            {"target_domain": self.windows.pk, "new_parent": ""},
        )
        self.assertRedirects(response, destination, fetch_redirect_response=False)
