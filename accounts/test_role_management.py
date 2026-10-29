from unittest.mock import patch
from io import StringIO
import time

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import GroupProfile
from accounts.services.groups import ensure_group_profile
from accounts.services.permission_assignments import sync_group_permission_assignments, sync_user_permission_assignments
from accounts.services.roles import preview_role, role_initial, role_state, save_role
from core.bootstrap_engine import BootstrapPlanError, apply_bootstrap_plan, bootstrap_defaults, build_bootstrap_plan
from core.models import SiteConfig
from standards.models import SkillProject, TechnicalDomain, TechnicalDomainGroupScope
from standards.selectors import scoped_domains_for


User = get_user_model()


class DefaultRoleTests(TestCase):
    def test_feedback_impact_command_is_readonly(self):
        user = User.objects.create_user("impact-user")
        output = StringIO()
        call_command("preview_feedback_access", stdout=output)
        self.assertIn("impact-user", output.getvalue())
        self.assertIn("feedback.view_feedback", output.getvalue())
        self.assertFalse(user.groups.exists())
        self.assertFalse(user.user_permissions.exists())
        self.assertFalse(GroupProfile.objects.exists())
        call_command("reconcile_permission_assignments", dry_run=True, stdout=StringIO())
        self.assertFalse(GroupProfile.objects.exists())

    def test_preflight_is_read_only_and_defaults_are_explicit(self):
        plan = build_bootstrap_plan()
        self.assertFalse(plan.has_errors)
        self.assertEqual(len(plan.roles), 3)
        self.assertFalse(Group.objects.exists())
        apply_bootstrap_plan(plan)
        for code in ("competitor", "coach", "assistant"):
            group = GroupProfile.objects.get(codename=code).group
            self.assertFalse(group.user_set.exists())
            self.assertFalse(group.technical_domain_scopes.exists())
            self.assertFalse(group.permissions.filter(codename__startswith="delete_").exists())
            user = User.objects.create_user(f"role-{code}")
            user.groups.add(group)
            for label in (
                "accounts.change_userprofile",
                "notices.view_notice",
                "behaviors.view_conductrecord",
                "feedback.add_feedback",
                "feedback.add_feedbackreply",
            ):
                self.assertTrue(user.has_perm(label), (code, label))
            for label in (
                "notes.view_noterepo",
                "training.add_trainingcycle",
                "training.change_trainingplan",
                "training.view_all_traininglog",
                "assessments.change_all_assessment",
                "assessments.add_assessment",
                "auth.change_user",
            ):
                self.assertFalse(user.has_perm(label), (code, label))
            positive = {
                "competitor": [
                    "training.change_taskexecution",
                    "training.add_traininglog",
                    "scoring.view_scoringresult",
                    "behaviors.be_conduct_subject",
                ],
                "coach": [
                    "standards.change_skill",
                    "standards.change_skilltreenode",
                    "training.change_trainingtask",
                    "assessments.change_assessmentmodule",
                    "scoring.change_scoringresult",
                    "evidence.change_knowledgeevidence",
                ],
                "assistant": [
                    "behaviors.add_conduct_record",
                    "behaviors.view_all_conduct_records",
                    "notices.add_notice",
                    "meetings.add_meeting",
                ],
            }
            for label in positive[code]:
                self.assertTrue(user.has_perm(label), (code, label))
        coach = User.objects.get(username="role-coach")
        self.client.force_login(coach)
        create_url = reverse("assessments:assessment_create")
        self.assertNotContains(self.client.get(reverse("assessments:assessment_list")), create_url)
        self.assertEqual(self.client.get(create_url).status_code, 403)
        self.assertIsNone(SiteConfig.get_solo().default_registration_group)
        self.assertFalse(build_bootstrap_plan().has_changes)

    def test_existing_assistant_is_updated_in_place_with_members_preserved(self):
        group = Group.objects.create(name="班务")
        profile = ensure_group_profile(group)
        profile.codename = "assistant"
        profile.description = "班主任助理"
        profile.save()
        member = User.objects.create_user("existing-assistant")
        member.groups.add(group)

        plan = build_bootstrap_plan(force=True)
        self.assertFalse(plan.has_errors)
        apply_bootstrap_plan(plan)

        profile.refresh_from_db()
        self.assertEqual(profile.group_id, group.pk)
        self.assertEqual(profile.codename, "assistant")
        self.assertIn("协助管理班级日常事务", profile.description)
        self.assertEqual(list(member.groups.values_list("pk", flat=True)), [group.pk])
        self.assertEqual(Group.objects.filter(name="班务").get().pk, group.pk)
        self.assertFalse(GroupProfile.objects.filter(codename="class_affairs").exists())
        self.assertFalse(build_bootstrap_plan(force=True).has_changes)

    def test_regular_preserves_customizations_force_preserves_members_domains_extras(self):
        bootstrap_defaults()
        profile = GroupProfile.objects.get(codename="coach")
        group = profile.group
        group.name = "自定义教练"
        group.save()
        profile.description = "自定义说明"
        profile.save()
        extra = Permission.objects.get(content_type__app_label="notes", codename="view_noterepo")
        sync_group_permission_assignments(group, ["notes.view_notes"], [extra])
        member = User.objects.create_user("custom-member")
        group.user_set.add(member)
        project = SkillProject.objects.create(code="role_project", name="角色项目")
        domain = TechnicalDomain.objects.create(skill_project=project, code="linux", name="Linux")
        TechnicalDomainGroupScope.objects.create(group=group, technical_domain=domain)
        bootstrap_defaults()
        group.refresh_from_db()
        self.assertEqual(group.name, "自定义教练")
        self.assertEqual(group.profile.selected_permission_bundles, ["notes.view_notes"])
        apply_bootstrap_plan(build_bootstrap_plan(force=True))
        group.refresh_from_db()
        self.assertEqual(group.name, "教练")
        self.assertEqual(list(group.user_set.all()), [member])
        self.assertTrue(group.technical_domain_scopes.filter(technical_domain=domain).exists())
        self.assertTrue(group.profile.explicit_permissions.filter(pk=extra.pk).exists())
        self.assertTrue(group.permissions.filter(pk=extra.pk).exists())

    def test_name_conflict_does_not_adopt_existing_group(self):
        group = Group.objects.create(name="教练")
        ensure_group_profile(group)
        plan = build_bootstrap_plan()
        self.assertTrue(plan.has_errors)
        self.assertIn("名称已被其他稳定标识占用", str(plan.issues))
        self.assertFalse(GroupProfile.objects.filter(codename="coach").exists())

    def test_stale_preview_and_failed_projection_roll_back_all_bootstrap(self):
        plan = build_bootstrap_plan()
        Group.objects.create(name="选手")
        with self.assertRaises(BootstrapPlanError):
            apply_bootstrap_plan(plan)
        self.assertFalse(SiteConfig.objects.exists())
        Group.objects.all().delete()
        plan = build_bootstrap_plan()
        with patch(
            "core.role_bootstrap.sync_group_permission_assignments", side_effect=RuntimeError("projection failed")
        ):
            with self.assertRaises(RuntimeError):
                apply_bootstrap_plan(plan)
        self.assertFalse(Group.objects.exists())
        self.assertFalse(SiteConfig.objects.exists())


class RoleManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("role-admin", "role@example.com", "test")
        self.member = User.objects.create_user("role-member")
        self.group = Group.objects.create(name="Linux教练")
        ensure_group_profile(self.group)
        project = SkillProject.objects.create(code="role_project", name="角色项目")
        self.linux = TechnicalDomain.objects.create(skill_project=project, code="linux", name="Linux")
        self.windows = TechnicalDomain.objects.create(skill_project=project, code="windows", name="Windows")
        self.payload = {
            "name": self.group.name,
            "description": "领域教练",
            "bundles": ["standards.maintain_skills"],
            "domains": [self.linux.pk],
            "members": [self.member.pk],
            "explicit_permissions": [],
        }

    def save(self, group=None, payload=None):
        group = self.group if group is None else group
        payload = payload or self.payload
        preview = preview_role(actor=self.admin, group=group, payload=payload)
        return save_role(actor=self.admin, group=group, payload=payload, token=preview["token"])

    def test_save_coordinates_permissions_domain_and_members_and_separate_groups_do_not_combine(self):
        self.save()
        fresh = User.objects.get(pk=self.member.pk)
        self.assertEqual(list(scoped_domains_for(fresh, "standards.change_skill")), [self.linux])
        other = Group.objects.create(name="仅Windows范围")
        TechnicalDomainGroupScope.objects.create(group=other, technical_domain=self.windows)
        fresh.groups.add(other)
        self.assertNotIn(self.windows, scoped_domains_for(fresh, "standards.change_skill"))
        sync_group_permission_assignments(other, ["standards.maintain_skills"])
        self.assertEqual(set(scoped_domains_for(fresh, "standards.change_skill")), {self.linux, self.windows})

    def test_copy_is_independent_and_members_and_domains_start_empty(self):
        self.save()
        initial = role_initial(self.group, copying=True)
        self.assertEqual(initial["members"], [])
        self.assertEqual(initial["domains"], [])
        preview = preview_role(actor=self.admin, group=None, payload=initial)
        copied = save_role(actor=self.admin, group=None, payload=initial, token=preview["token"])
        self.assertNotEqual(copied.pk, self.group.pk)
        sync_group_permission_assignments(self.group, [])
        self.assertTrue(copied.permissions.filter(codename="change_skill").exists())

    def test_requires_superuser_and_fresh_unchanged_preview(self):
        with self.assertRaises(PermissionDenied):
            preview_role(actor=self.member, group=self.group, payload=self.payload)
        preview = preview_role(actor=self.admin, group=self.group, payload=self.payload)
        self.group.user_set.add(self.member)
        with self.assertRaises(ValidationError):
            save_role(actor=self.admin, group=self.group, payload=self.payload, token=preview["token"])
        with self.assertRaises(ValidationError):
            save_role(actor=self.admin, group=self.group, payload=self.payload, token="forged")

    def test_preview_cannot_be_reused_with_changed_form_or_after_expiry(self):
        preview = preview_role(actor=self.admin, group=self.group, payload=self.payload)
        with self.assertRaises(ValidationError):
            save_role(
                actor=self.admin,
                group=self.group,
                payload={**self.payload, "name": "更改过的表单"},
                token=preview["token"],
            )
        with patch("django.core.signing.time.time", return_value=time.time() + 1900):
            with self.assertRaises(ValidationError):
                save_role(actor=self.admin, group=self.group, payload=self.payload, token=preview["token"])

    def test_all_parts_roll_back_when_member_write_fails(self):
        before = role_state(self.group)
        with patch.object(type(self.group.user_set), "set", side_effect=RuntimeError("member failure")):
            with self.assertRaises(RuntimeError):
                self.save()
        self.group.refresh_from_db()
        self.assertEqual(role_state(self.group), before)

    def test_frontend_preview_save_and_non_superuser_post(self):
        url = reverse("accounts:role_edit", args=[self.group.pk])
        self.client.force_login(self.member)
        for method in (self.client.get, self.client.post):
            self.assertEqual(method(url, self.payload).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(url), "业务权限包")
        preview = self.client.post(url, {**self.payload, "action": "preview"})
        self.assertContains(preview, "保存前变更摘要")
        self.assertFalse(self.group.permissions.exists())
        saved = self.client.post(
            url, {**self.payload, "action": "save", "preview_token": preview.context["preview"]["token"]}
        )
        self.assertEqual(saved.status_code, 302)
        self.assertTrue(self.group.permissions.filter(codename="change_skill").exists())
        sync_user_permission_assignments(self.member, ["notes.view_notes"])
        diagnostic = self.client.get(reverse("accounts:user_permissions", args=[self.member.pk]))
        self.assertContains(diagnostic, "个人直接授权")
        self.assertContains(diagnostic, "notes.view_noterepo")
        self.assertContains(diagnostic, "Linux")
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("accounts:user_permissions", args=[self.admin.pk])).status_code, 403)

    def test_readonly_role_list_uses_view_group_permission(self):
        permission = Permission.objects.get(content_type__app_label="auth", codename="view_group")
        self.member.user_permissions.add(permission)
        self.client.force_login(self.member)
        response = self.client.get(reverse("accounts:role_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "创建角色")
