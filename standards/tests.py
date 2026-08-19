from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from assessments.forms import AssessmentForm
from evidence.forms import KnowledgeEvidenceForm
from glossary.forms import ProfessionalGlossaryForm
from training.forms import TrainingCycleForm

from .forms import SkillForm, SkillProjectForm, SkillTreeVersionForm, TechnicalDomainForm, WSOSVersionForm
from .models import (
    Skill,
    SkillProject,
    SkillTerm,
    SkillTreeNode,
    SkillTreeVersion,
    SkillWSOSMap,
    TechnicalDomain,
    TechnicalDomainMembership,
    WSOSSection,
    WSOSVersion,
)
from .selectors import manageable_skills_for
from .services import find_skill_candidates, normalize_skill_term, save_skill
from .tables import SkillProjectTable

User = get_user_model()


class SkillProjectDefaultTests(TestCase):
    def test_saving_new_default_project_unsets_previous_default(self):
        previous = SkillProject.objects.create(code="OLD", name="原默认项目", is_default=True)
        current = SkillProject.objects.create(code="NEW", name="新默认项目", is_default=True)

        previous.refresh_from_db()
        self.assertFalse(previous.is_default)
        self.assertTrue(current.is_default)

    def test_inactive_project_cannot_be_default(self):
        project = SkillProject(code="OFF", name="停用项目", is_active=False, is_default=True)

        with self.assertRaisesMessage(ValidationError, "默认技能项目必须处于启用状态"):
            project.save()

    def test_database_constraint_rejects_second_default_from_queryset_update(self):
        SkillProject.objects.create(code="ONE", name="默认项目", is_default=True)
        other = SkillProject.objects.create(code="TWO", name="其他项目")

        with self.assertRaises(IntegrityError), transaction.atomic():
            SkillProject.objects.filter(pk=other.pk).update(is_default=True)

    def test_project_form_can_switch_default_project(self):
        previous = SkillProject.objects.create(code="OLD", name="原默认项目", is_default=True)
        current = SkillProject.objects.create(code="NEW", name="新默认项目")
        form = SkillProjectForm(
            data={
                "code": current.code,
                "name": current.name,
                "short_name": "",
                "description": "",
                "order": 0,
                "is_active": "on",
                "is_default": "on",
            },
            instance=current,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        previous.refresh_from_db()
        current.refresh_from_db()
        self.assertFalse(previous.is_default)
        self.assertTrue(current.is_default)

    def test_project_form_can_leave_system_without_default(self):
        project = SkillProject.objects.create(code="DEF", name="默认项目", is_default=True)
        form = SkillProjectForm(
            data={
                "code": project.code,
                "name": project.name,
                "short_name": "",
                "description": "",
                "order": 0,
                "is_active": "on",
            },
            instance=project,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        project.refresh_from_db()
        self.assertFalse(project.is_default)

    def test_project_table_marks_default_project(self):
        project = SkillProject.objects.create(code="DEF", name="默认项目", is_default=True)

        html = SkillProjectTable([project]).rows[0].get_cell("is_default")

        self.assertIn("默认", html)
        self.assertIn("badge badge-primary", html)


class DefaultSkillProjectFormTests(TestCase):
    form_classes = (
        TechnicalDomainForm,
        SkillForm,
        SkillTreeVersionForm,
        WSOSVersionForm,
        AssessmentForm,
        TrainingCycleForm,
        ProfessionalGlossaryForm,
        KnowledgeEvidenceForm,
    )

    def setUp(self):
        self.default_project = SkillProject.objects.create(code="DEF", name="默认项目", is_default=True)
        self.other_project = SkillProject.objects.create(code="OTHER", name="其他项目")

    def test_all_direct_project_forms_use_explicit_default_for_new_objects(self):
        for form_class in self.form_classes:
            with self.subTest(form=form_class.__name__):
                self.assertEqual(form_class().initial["skill_project"], self.default_project)

    def test_explicit_initial_takes_precedence_over_default_project(self):
        form = AssessmentForm(initial={"skill_project": self.other_project})

        self.assertEqual(form.initial["skill_project"], self.other_project)

    def test_edit_form_preserves_instance_project(self):
        domain = TechnicalDomain.objects.create(
            skill_project=self.other_project,
            code="OTHER",
            name="其他领域",
        )

        form = TechnicalDomainForm(instance=domain)

        self.assertEqual(form.initial["skill_project"], self.other_project.pk)

    def test_bound_form_does_not_fill_missing_project(self):
        form = AssessmentForm(data={})

        self.assertFalse(form.is_valid())
        self.assertIn("skill_project", form.errors)

    def test_skill_form_filters_domains_using_default_project(self):
        expected = TechnicalDomain.objects.create(
            skill_project=self.default_project,
            code="LINUX",
            name="Linux",
        )
        TechnicalDomain.objects.create(
            skill_project=self.other_project,
            code="WINDOWS",
            name="Windows",
        )

        form = SkillForm()

        self.assertEqual(list(form.fields["primary_domain"].queryset), [expected])
        self.assertEqual(list(form.fields["related_domains"].queryset), [expected])


class StableSkillAndWSOSTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.domain = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.skill = Skill.objects.create(skill_project=self.project, primary_domain=self.domain, name="Linux 服务")

    def test_same_skill_can_be_mounted_in_multiple_tree_versions(self):
        first = SkillTreeVersion.objects.create(skill_project=self.project, version="V1", name="第一版")
        second = SkillTreeVersion.objects.create(skill_project=self.project, version="V2", name="第二版")
        first_root = SkillTreeNode.objects.create(
            tree_version=first,
            technical_domain=self.domain,
            node_type=SkillTreeNode.NodeType.CATEGORY,
            code="V1",
            name="Linux 类别",
        )
        second_root = SkillTreeNode.objects.create(
            tree_version=second,
            technical_domain=self.domain,
            node_type=SkillTreeNode.NodeType.CATEGORY,
            code="V2",
            name="Linux 类别",
        )
        SkillTreeNode.objects.create(
            tree_version=first,
            technical_domain=self.domain,
            parent=first_root,
            node_type=SkillTreeNode.NodeType.SKILL,
            code="V1-LNX",
            name="Linux",
            skill=self.skill,
        )
        SkillTreeNode.objects.create(
            tree_version=second,
            technical_domain=self.domain,
            parent=second_root,
            node_type=SkillTreeNode.NodeType.SKILL,
            code="V2-LNX",
            name="Linux",
            skill=self.skill,
        )
        self.assertEqual(self.skill.tree_nodes.count(), 2)
        self.assertEqual({node.skill_id for node in self.skill.tree_nodes.all()}, {self.skill.pk})

    def test_skill_can_map_multiple_wsos_sections_and_empty_section_is_valid(self):
        version = WSOSVersion.objects.create(skill_project=self.project, code="2026", name="WSOS 2026")
        first = WSOSSection.objects.create(wsos_version=version, code="1", name="工作组织", weight=20)
        second = WSOSSection.objects.create(wsos_version=version, code="2", name="沟通", weight=20)
        WSOSSection.objects.create(wsos_version=version, code="3", name="空章节", weight=0)
        SkillWSOSMap.objects.create(skill=self.skill, wsos_section=first)
        SkillWSOSMap.objects.create(skill=self.skill, wsos_section=second)
        self.assertEqual(self.skill.wsos_mappings.count(), 2)

    def test_cross_project_wsos_mapping_is_rejected(self):
        other = SkillProject.objects.create(code="OTHER", name="其他项目")
        version = WSOSVersion.objects.create(skill_project=other, code="2026", name="其他 WSOS")
        section = WSOSSection.objects.create(wsos_version=version, code="1", name="其他", weight=100)
        with self.assertRaises(ValidationError):
            SkillWSOSMap.objects.create(skill=self.skill, wsos_section=section)


class TechnicalDomainPermissionTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.linux = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.windows = TechnicalDomain.objects.create(skill_project=self.project, code="WINDOWS", name="Windows")
        self.linux_skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="Linux")
        self.windows_skill = Skill.objects.create(
            skill_project=self.project, primary_domain=self.windows, name="Windows"
        )
        self.coach = User.objects.create_user(username="linux-coach")
        self.admin = User.objects.create_user(username="project-admin")
        TechnicalDomainMembership.objects.create(
            technical_domain=self.linux, user=self.coach, role=TechnicalDomainMembership.Role.COACH
        )
        change_skill = Permission.objects.get(content_type__app_label="standards", codename="change_skill")
        global_scope = Permission.objects.get(
            content_type__app_label="standards", codename="manage_all_technical_domains"
        )
        self.coach.user_permissions.add(change_skill)
        self.admin.user_permissions.add(change_skill, global_scope)

    def test_domain_coach_only_manages_primary_domain_skills(self):
        self.assertQuerySetEqual(manageable_skills_for(self.coach), [self.linux_skill])

    def test_project_admin_manages_all_skills(self):
        self.assertSetEqual(set(manageable_skills_for(self.admin)), {self.linux_skill, self.windows_skill})


class SkillTermServiceTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.domain = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")

    def create_skill(self, name="Linux 用户和组管理", aliases=()):
        return save_skill(
            skill=Skill(skill_project=self.project, primary_domain=self.domain, name=name),
            aliases=aliases,
            related_domains=(),
        )

    def test_normalization_ignores_width_case_and_spaces_but_keeps_technical_symbols(self):
        self.assertEqual(normalize_skill_term(" Ｌｉｎｕｘ 用户 管理 "), "linux用户管理")
        self.assertNotEqual(normalize_skill_term("C++"), normalize_skill_term("C#"))

    def test_save_skill_registers_primary_name_and_aliases(self):
        skill = self.create_skill(aliases=["Linux 账号管理", "用户与用户组管理"])

        self.assertEqual(skill.display_code, f"SK-{skill.pk:06d}")
        self.assertSetEqual(
            set(skill.terms.values_list("kind", "term")),
            {
                (SkillTerm.Kind.NAME, "Linux 用户和组管理"),
                (SkillTerm.Kind.ALIAS, "Linux 账号管理"),
                (SkillTerm.Kind.ALIAS, "用户与用户组管理"),
            },
        )

    def test_normalized_name_or_alias_cannot_belong_to_another_skill(self):
        self.create_skill(aliases=["Linux 账号管理"])

        with self.assertRaisesMessage(ValidationError, "已属于技能"):
            self.create_skill(name=" LINUX账号管理 ")

        self.assertEqual(Skill.objects.count(), 1)

    def test_renaming_can_keep_old_name_as_alias(self):
        skill = self.create_skill()
        old_name = skill.name
        skill.name = "Linux 本地身份管理"

        save_skill(
            skill=skill,
            aliases=[],
            related_domains=(),
            preserve_old_name=True,
            old_name=old_name,
        )

        self.assertTrue(skill.terms.filter(kind=SkillTerm.Kind.ALIAS, term=old_name).exists())

    def test_candidates_include_inactive_skills_and_rank_exact_alias_first(self):
        skill = self.create_skill(aliases=["Linux 账号管理"])
        skill.is_active = False
        skill.save(update_fields=["is_active"])

        candidates = find_skill_candidates(skill_project=self.project, query="LINUX账号管理")

        self.assertEqual(candidates[0], skill)
        self.assertTrue(candidates[0].candidate_exact)


class SkillCatalogViewTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理", is_default=True)
        self.linux = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.windows = TechnicalDomain.objects.create(skill_project=self.project, code="WINDOWS", name="Windows")
        self.coach = User.objects.create_user(username="linux-coach")
        TechnicalDomainMembership.objects.create(technical_domain=self.linux, user=self.coach)
        permissions = Permission.objects.filter(
            content_type__app_label="standards",
            codename__in=["view_skill", "add_skill", "change_skill"],
        )
        self.coach.user_permissions.add(*permissions)
        self.client.force_login(self.coach)

    @property
    def catalog_url(self):
        return reverse("standards:skill_list", kwargs={"project_pk": self.project.pk})

    def domain_url(self, domain=None):
        domain = domain or self.linux
        return reverse(
            "standards:domain_detail",
            kwargs={"project_pk": self.project.pk, "domain_pk": domain.pk},
        )

    def post_data(self, **overrides):
        data = {
            "skill_project": self.project.pk,
            "primary_domain": self.linux.pk,
            "name": "Linux 服务管理",
            "description": "",
            "aliases_text": "systemd 服务管理",
            "difficulty": 3,
            "order": 0,
            "is_assessable": "on",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_catalog_entry_redirects_to_default_project(self):
        response = self.client.get(reverse("standards:skill_catalog_entry"))

        self.assertRedirects(response, self.catalog_url, fetch_redirect_response=False)

    def test_catalog_entry_requires_project_selection_without_default(self):
        self.project.is_default = False
        self.project.save(update_fields=["is_default"])
        other = SkillProject.objects.create(code="OTHER", name="其他项目")

        response = self.client.get(reverse("standards:skill_catalog_entry"))

        self.assertContains(response, self.project.name)
        self.assertContains(response, other.name)

    def test_catalog_lists_project_domains_and_account_scoped_counts(self):
        Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="Linux 服务")

        response = self.client.get(self.catalog_url)

        self.assertContains(response, "网络系统管理技能目录")
        self.assertContains(response, "Linux")
        self.assertContains(response, "Windows")
        self.assertContains(response, "1 项主要技能")
        self.assertNotContains(response, "data-skill-create-dialog")

    def test_catalog_hides_inactive_domains_from_non_maintainers(self):
        inactive = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="OLD",
            name="旧领域",
            is_active=False,
        )

        response = self.client.get(self.catalog_url)
        self.assertNotContains(response, inactive.name)

        admin = User.objects.create_user(username="project-admin")
        admin.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="standards",
                codename="view_skill",
            ),
            Permission.objects.get(
                content_type__app_label="standards",
                codename="change_technicaldomain",
            ),
            Permission.objects.get(
                content_type__app_label="standards",
                codename="manage_all_technical_domains",
            ),
        )
        self.client.force_login(admin)

        response = self.client.get(self.catalog_url)
        self.assertContains(response, inactive.name)
        self.assertContains(response, "已停用")

    def test_domain_page_combines_management_context_and_skill_table(self):
        skill = Skill.objects.create(skill_project=self.project, primary_domain=self.linux, name="Linux 服务")

        response = self.client.get(self.domain_url())

        self.assertContains(response, "Linux技术领域")
        self.assertContains(response, "技能条目")
        self.assertContains(response, skill.name)
        self.assertNotContains(response, "技能项目")
        self.assertContains(response, "data-skill-create-dialog")
        self.assertContains(response, "js-skill-drawer-open")
        self.assertNotContains(response, "负责成员")
        self.assertContains(response, f'name="skill_project" value="{self.project.pk}"')
        self.assertContains(response, f'name="primary_domain" value="{self.linux.pk}"')

    def test_domain_url_rejects_cross_project_domain(self):
        other_project = SkillProject.objects.create(code="OTHER", name="其他项目")

        response = self.client.get(
            reverse(
                "standards:domain_detail",
                kwargs={"project_pk": other_project.pk, "domain_pk": self.linux.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_domain_page_without_add_permission_does_not_render_create_drawer(self):
        viewer = User.objects.create_user(username="skill-viewer")
        viewer.user_permissions.add(Permission.objects.get(codename="view_skill"))
        self.client.force_login(viewer)

        response = self.client.get(self.domain_url())

        self.assertNotContains(response, "data-skill-create-dialog")
        self.assertNotContains(response, "js-skill-drawer-open")

    def test_focus_create_marks_drawer_for_automatic_opening(self):
        response = self.client.get(f"{self.domain_url()}?focus=create")

        self.assertContains(response, 'data-skill-auto-open="true"')

    def test_domain_context_overrides_tampered_project_and_primary_domain(self):
        other_project = SkillProject.objects.create(code="OTHER", name="其他项目")
        other_domain = TechnicalDomain.objects.create(
            skill_project=other_project,
            code="OTHER",
            name="其他领域",
        )
        response = self.client.post(
            self.domain_url(),
            self.post_data(skill_project=other_project.pk, primary_domain=other_domain.pk),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        skill = Skill.objects.get()
        self.assertEqual(skill.skill_project, self.project)
        self.assertEqual(skill.primary_domain, self.linux)

    def test_successful_htmx_create_registers_terms_and_returns_oob_results(self):
        response = self.client.post(
            self.domain_url(),
            self.post_data(),
            HTTP_HX_REQUEST="true",
        )

        skill = Skill.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-swap-oob="outerHTML"')
        self.assertContains(response, skill.display_code)
        self.assertJSONEqual(response.headers["HX-Trigger-After-Swap"], {"skillCreated": {"skillId": skill.pk}})
        self.assertContains(response, 'data-skill-form-dirty="false"')
        self.assertSetEqual(set(skill.aliases), {"systemd 服务管理"})

    def test_invalid_create_keeps_drawer_form_dirty_without_success_event(self):
        response = self.client.post(
            self.domain_url(),
            self.post_data(name=""),
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, 'data-skill-form-dirty="true"')
        self.assertNotIn("HX-Trigger-After-Swap", response.headers)

    def test_reset_form_preserves_project_and_primary_domain(self):
        response = self.client.get(
            reverse(
                "standards:skill_form_reset",
                kwargs={"project_pk": self.project.pk, "domain_pk": self.linux.pk},
            ),
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, f'name="skill_project" value="{self.project.pk}"')
        self.assertContains(response, f'name="primary_domain" value="{self.linux.pk}"')
        self.assertContains(response, 'data-skill-form-dirty="false"')

    def test_reset_form_requires_add_permission(self):
        viewer = User.objects.create_user(username="reset-viewer")
        viewer.user_permissions.add(Permission.objects.get(content_type__app_label="standards", codename="view_skill"))
        self.client.force_login(viewer)

        response = self.client.get(
            reverse(
                "standards:skill_form_reset",
                kwargs={"project_pk": self.project.pk, "domain_pk": self.linux.pk},
            ),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 403)

    def test_created_skill_hidden_by_filters_offers_clear_filters_link(self):
        response = self.client.post(
            f"{self.domain_url()}?active=0",
            self.post_data(),
            HTTP_HX_REQUEST="true",
        )

        skill = Skill.objects.get()
        self.assertContains(response, "当前筛选条件未显示该技能")
        self.assertContains(response, "清除筛选并查看")
        self.assertContains(response, f"highlight={skill.pk}")

    def test_high_similarity_requires_confirmation_and_description(self):
        save_skill(
            skill=Skill(skill_project=self.project, primary_domain=self.linux, name="Linux 用户管理"),
            aliases=[],
            related_domains=(),
        )

        response = self.client.post(
            self.domain_url(),
            self.post_data(name="Linux 用户和组管理", aliases_text=""),
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, "请先确认候选技能")
        self.assertContains(response, "请填写描述说明技能边界")
        self.assertEqual(Skill.objects.count(), 1)

        response = self.client.post(
            self.domain_url(),
            self.post_data(
                name="Linux 用户和组管理",
                aliases_text="",
                description="包含用户组生命周期，与单用户维护边界不同。",
                confirm_distinct="on",
            ),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Skill.objects.count(), 2)

    def test_domain_page_defaults_to_active_primary_skills_and_can_include_related(self):
        primary = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.linux,
            name="Linux 服务",
        )
        inactive = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.linux,
            name="旧 Linux 服务",
            is_active=False,
        )
        related = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.windows,
            name="PowerShell 自动化",
        )
        related.related_domains.add(self.linux)

        response = self.client.get(self.domain_url())
        self.assertContains(response, primary.name)
        self.assertNotContains(response, inactive.name)
        self.assertNotContains(response, related.name)

        response = self.client.get(self.domain_url(), {"related": "1", "active": ""})
        self.assertContains(response, inactive.name)
        self.assertContains(response, related.name)
        self.assertContains(response, "关联技能")
        self.assertContains(response, "主要归属：Windows")

    def test_domain_management_information_requires_domain_view_permission(self):
        permission = Permission.objects.get(
            content_type__app_label="standards",
            codename="view_technicaldomain",
        )
        self.coach.user_permissions.add(permission)

        response = self.client.get(self.domain_url())

        self.assertContains(response, "负责成员")

    def test_skill_detail_breadcrumb_uses_primary_domain(self):
        skill = Skill.objects.create(
            skill_project=self.project,
            primary_domain=self.linux,
            name="Linux 服务",
        )

        response = self.client.get(reverse("standards:skill_detail", args=[skill.pk]))

        self.assertContains(response, self.catalog_url)
        self.assertContains(response, self.domain_url())

    def test_candidate_search_shows_minimum_cross_domain_information_without_detail_link(self):
        skill = save_skill(
            skill=Skill(skill_project=self.project, primary_domain=self.windows, name="Windows 账号管理"),
            aliases=["域用户管理"],
            related_domains=(),
        )

        response = self.client.get(
            reverse("standards:skill_candidates"),
            {"skill_project": self.project.pk, "name": "Windows账号管理"},
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, skill.name)
        self.assertContains(response, self.windows.name)
        self.assertNotContains(response, "查看详情")

    def test_manageable_candidate_can_register_current_input_as_alias(self):
        skill = save_skill(
            skill=Skill(skill_project=self.project, primary_domain=self.linux, name="Linux 用户管理"),
            aliases=[],
            related_domains=(),
        )

        response = self.client.post(
            reverse("standards:skill_alias_add", args=[skill.pk]),
            {"term": "Linux 账号维护"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("skillAliasAdded", response.headers["HX-Trigger"])
        self.assertTrue(skill.terms.filter(kind=SkillTerm.Kind.ALIAS, term="Linux 账号维护").exists())

    def test_old_domain_and_skill_list_urls_are_not_compatible(self):
        old_domain_response = self.client.get("/standards/domains/")
        old_skill_response = self.client.get("/standards/skills/")

        self.assertEqual(old_domain_response.status_code, 404)
        self.assertEqual(old_skill_response.status_code, 404)
