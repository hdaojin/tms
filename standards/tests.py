from importlib import import_module

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from assessments.forms import AssessmentForm
from evidence.forms import KnowledgeEvidenceForm
from glossary.forms import ProfessionalGlossaryForm
from training.forms import TrainingCycleForm

from .forms import SkillForm, SkillProjectForm, TechnicalDomainForm, WSOSVersionForm
from .models import (
    Skill,
    SkillProject,
    SkillTerm,
    SkillTreeNode,
    SkillTreeVersion,
    SkillWSOSMap,
    TechnicalDomain,
    TechnicalDomainGroupScope,
    WSOSSection,
    WSOSVersion,
)
from .selectors import can_manage_domain, manageable_skills_for, visible_skills_for
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
        first = SkillTreeVersion.objects.create(technical_domain=self.domain, version="V1", name="第一版")
        second = SkillTreeVersion.objects.create(technical_domain=self.domain, version="V2", name="第二版")
        SkillTreeNode.objects.create(
            tree_version=first,
            skill=self.skill,
        )
        SkillTreeNode.objects.create(
            tree_version=second,
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
        self.linux_group = Group.objects.create(name="Linux 教练")
        self.windows_group = Group.objects.create(name="Windows 查看者")
        change_skill = Permission.objects.get(content_type__app_label="standards", codename="change_skill")
        view_skill = Permission.objects.get(content_type__app_label="standards", codename="view_skill")
        self.linux_group.permissions.add(change_skill)
        self.windows_group.permissions.add(view_skill)
        TechnicalDomainGroupScope.objects.create(group=self.linux_group, technical_domain=self.linux)
        TechnicalDomainGroupScope.objects.create(group=self.windows_group, technical_domain=self.windows)
        self.coach.groups.add(self.linux_group, self.windows_group)
        self.coach = User.objects.get(pk=self.coach.pk)

    def test_domain_coach_only_manages_primary_domain_skills(self):
        self.assertQuerySetEqual(manageable_skills_for(self.coach), [self.linux_skill])

    def test_view_permission_makes_all_project_skills_visible(self):
        self.assertSetEqual(set(visible_skills_for(self.coach)), {self.linux_skill, self.windows_skill})

    def test_permission_and_scope_from_different_groups_do_not_chain(self):
        self.assertTrue(can_manage_domain(self.coach, self.linux, "standards.change_skill"))
        self.assertFalse(can_manage_domain(self.coach, self.windows, "standards.change_skill"))
        self.assertTrue(can_manage_domain(self.coach, self.windows, "standards.view_skill"))

    def test_direct_user_permission_without_same_group_scope_is_rejected(self):
        direct_user = User.objects.create_user(username="direct-user")
        change_skill = Permission.objects.get(content_type__app_label="standards", codename="change_skill")
        direct_user.user_permissions.add(change_skill)
        direct_user = User.objects.get(pk=direct_user.pk)

        self.assertFalse(can_manage_domain(direct_user, self.linux, "standards.change_skill"))

    def test_related_domain_does_not_grant_skill_maintenance(self):
        self.windows_skill.related_domains.add(self.linux)

        self.assertNotIn(self.windows_skill, manageable_skills_for(self.coach))

    def test_superuser_manages_all_skills_and_domains(self):
        admin = User.objects.create_superuser(username="admin")

        self.assertSetEqual(set(manageable_skills_for(admin)), {self.linux_skill, self.windows_skill})
        self.assertTrue(can_manage_domain(admin, self.windows, "standards.change_skill"))

    def test_group_scope_is_unique_per_group_and_domain(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TechnicalDomainGroupScope.objects.create(group=self.linux_group, technical_domain=self.linux)

    def test_skill_move_requires_source_and_target_domain_scope(self):
        windows_group = Group.objects.create(name="Windows 修改者")
        windows_group.permissions.add(
            Permission.objects.get(content_type__app_label="standards", codename="change_skill")
        )
        TechnicalDomainGroupScope.objects.create(group=windows_group, technical_domain=self.windows)
        windows_user = User.objects.create_user(username="windows-maintainer")
        windows_user.groups.add(windows_group)
        windows_user = User.objects.get(pk=windows_user.pk)
        self.linux_skill.primary_domain = self.windows

        with self.assertRaises(PermissionDenied):
            save_skill(
                skill=self.linux_skill,
                aliases=(),
                related_domains=(),
                actor=windows_user,
            )


class RetiredStandardPermissionMigrationTests(TestCase):
    def test_cleanup_removes_global_scope_and_membership_permissions(self):
        project_type = ContentType.objects.get_for_model(SkillProject)
        retired_global, _created = Permission.objects.get_or_create(
            content_type=project_type,
            codename="manage_all_technical_domains",
            defaults={"name": "旧全局技术领域权限"},
        )
        membership_type, _created = ContentType.objects.get_or_create(
            app_label="standards",
            model="technicaldomainmembership",
        )
        membership_permission = Permission.objects.create(
            content_type=membership_type,
            codename="view_technicaldomainmembership",
            name="旧技术领域成员查看权限",
        )

        migration = import_module("standards.migrations.0008_technicaldomaingroupscope_and_more")
        migration.remove_retired_permission_rows(django_apps, None)

        self.assertFalse(Permission.objects.filter(pk=retired_global.pk).exists())
        self.assertFalse(Permission.objects.filter(pk=membership_permission.pk).exists())
        self.assertFalse(ContentType.objects.filter(pk=membership_type.pk).exists())


class SkillTermServiceTests(TestCase):
    def setUp(self):
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.domain = TechnicalDomain.objects.create(skill_project=self.project, code="LINUX", name="Linux")
        self.actor = User.objects.create_superuser(username="skill-service-admin")

    def create_skill(self, name="Linux 用户和组管理", aliases=()):
        return save_skill(
            skill=Skill(skill_project=self.project, primary_domain=self.domain, name=name),
            aliases=aliases,
            related_domains=(),
            actor=self.actor,
        )

    def test_normalization_ignores_width_case_and_spaces_but_keeps_technical_symbols(self):
        self.assertEqual(normalize_skill_term(" Ｌｉｎｕｘ 用户 管理 "), "linux用户管理")
        self.assertNotEqual(normalize_skill_term("C++"), normalize_skill_term("C#"))

    def test_save_skill_registers_primary_name_and_aliases(self):
        skill = self.create_skill(aliases=["Linux 账号管理", "用户与用户组管理"])

        self.assertEqual(str(skill), skill.name)
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
            actor=self.actor,
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
