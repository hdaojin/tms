from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Skill, SkillProject, SkillTerm, SkillTreeNode, SkillTreeVersion, TechnicalDomain
from .selectors import skill_tree_structure
from .services import (
    attach_existing_skill_to_tree,
    create_skill_in_tree,
    move_skill_tree_node,
    remove_skill_tree_node,
    reorder_skill_tree_node,
    save_skill,
)


User = get_user_model()


class SkillTreeFixtureMixin:
    def setUp(self):
        super().setUp()
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理")
        self.linux = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="LINUX",
            name="Linux",
            order=10,
        )
        self.windows = TechnicalDomain.objects.create(
            skill_project=self.project,
            code="WINDOWS",
            name="Windows",
            order=20,
        )
        self.tree = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="2026",
            name="2026 技能树",
            is_current=True,
        )

    def skill(self, name, domain=None, **kwargs):
        return Skill.objects.create(
            skill_project=self.project,
            primary_domain=domain or self.linux,
            name=name,
            **kwargs,
        )

    def node(self, name, *, parent=None, domain=None, order=0, skill=None):
        domain = domain or self.linux
        return SkillTreeNode.objects.create(
            tree_version=self.tree,
            technical_domain=domain,
            parent=parent,
            skill=skill or self.skill(name, domain),
            order=order,
        )

    def user_with_permissions(self, username="maintainer", *codenames):
        user = User.objects.create_user(username=username)
        permissions = Permission.objects.filter(
            content_type__app_label="standards",
            codename__in=codenames,
        )
        user.user_permissions.add(*permissions)
        return User.objects.get(pk=user.pk)

    def project_admin(self):
        return self.user_with_permissions(
            "project-admin",
            "manage_all_technical_domains",
            "view_skilltreeversion",
            "view_skilltreenode",
            "view_skill",
            "add_skill",
            "change_skill",
            "add_skilltreenode",
            "change_skilltreenode",
            "delete_skilltreenode",
        )


class SkillTreeNodeModelTests(SkillTreeFixtureMixin, TestCase):
    def test_root_and_skill_children_support_arbitrary_depth(self):
        root = self.node("系统管理", order=10)
        child = self.node("用户与权限管理", parent=root, order=20)
        grandchild = self.node("sudo", parent=child, order=20)
        fourth = self.node("sudoers", parent=grandchild, order=10)
        fifth = self.node("NOPASSWD", parent=fourth, order=10)

        self.assertEqual(
            fifth.get_full_path(),
            "系统管理 / 用户与权限管理 / sudo / sudoers / NOPASSWD",
        )
        self.assertEqual(root.get_descendants(), [child, grandchild, fourth, fifth])
        self.assertTrue(root.skill.is_assessable)

    def test_descendants_use_stable_sibling_order(self):
        root = self.node("根")
        later = self.node("后", parent=root, order=20)
        first = self.node("先", parent=root, order=10)

        self.assertEqual(root.get_descendants(), [first, later])

    def test_same_skill_is_unique_per_version_but_reusable_across_versions(self):
        skill = self.skill("DNS")
        SkillTreeNode.objects.create(
            tree_version=self.tree,
            technical_domain=self.linux,
            skill=skill,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            SkillTreeNode.objects.create(
                tree_version=self.tree,
                technical_domain=self.linux,
                skill=skill,
            )

        other_tree = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="2027",
            name="2027 技能树",
        )
        SkillTreeNode.objects.create(
            tree_version=other_tree,
            technical_domain=self.linux,
            skill=skill,
        )
        self.assertEqual(skill.tree_nodes.count(), 2)

    def test_parent_must_share_version_and_domain(self):
        root = self.node("Linux 根")
        windows_skill = self.skill("Windows 技能", self.windows)
        with self.assertRaisesMessage(ValidationError, "同一技术领域"):
            SkillTreeNode.objects.create(
                tree_version=self.tree,
                technical_domain=self.windows,
                parent=root,
                skill=windows_skill,
            )

        other_tree = SkillTreeVersion.objects.create(
            skill_project=self.project,
            version="2027",
            name="2027 技能树",
        )
        with self.assertRaisesMessage(ValidationError, "同一技能树版本"):
            SkillTreeNode.objects.create(
                tree_version=other_tree,
                technical_domain=self.linux,
                parent=root,
                skill=self.skill("其他版本技能"),
            )

    def test_skill_project_and_domain_membership_are_validated(self):
        other_project = SkillProject.objects.create(code="OTHER", name="其他项目")
        other_domain = TechnicalDomain.objects.create(
            skill_project=other_project,
            code="OTHER",
            name="其他领域",
        )
        with self.assertRaisesMessage(ValidationError, "对应的技能项目"):
            SkillTreeNode.objects.create(
                tree_version=self.tree,
                technical_domain=self.linux,
                skill=Skill.objects.create(
                    skill_project=other_project,
                    primary_domain=other_domain,
                    name="其他技能",
                ),
            )

        with self.assertRaisesMessage(ValidationError, "主要或关联技术领域"):
            SkillTreeNode.objects.create(
                tree_version=self.tree,
                technical_domain=self.windows,
                skill=self.skill("仅 Linux"),
            )

    def test_self_parent_and_ancestor_cycle_are_rejected(self):
        root = self.node("根")
        child = self.node("子", parent=root)
        root.parent = root
        with self.assertRaisesMessage(ValidationError, "自身"):
            root.save()
        root.parent = child
        with self.assertRaisesMessage(ValidationError, "下级"):
            root.save()


class SkillTreeServiceTests(SkillTreeFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.actor = self.project_admin()

    def test_create_skill_in_tree_is_atomic_and_registers_primary_term(self):
        node = create_skill_in_tree(
            tree_version=self.tree,
            technical_domain=self.linux,
            parent=None,
            name="系统管理",
            actor=self.actor,
        )

        self.assertEqual(node.order, 10)
        self.assertEqual(node.skill.name, "系统管理")
        self.assertTrue(
            SkillTerm.objects.filter(
                skill=node.skill,
                kind=SkillTerm.Kind.NAME,
                term="系统管理",
            ).exists()
        )

        with patch.object(SkillTreeNode, "save", side_effect=ValidationError("节点失败")):
            with self.assertRaisesMessage(ValidationError, "节点失败"):
                create_skill_in_tree(
                    tree_version=self.tree,
                    technical_domain=self.linux,
                    parent=None,
                    name="不应残留",
                    actor=self.actor,
                )
        self.assertFalse(Skill.objects.filter(name="不应残留").exists())

    def test_exact_candidate_can_be_attached_without_add_skill_permission(self):
        existing = save_skill(
            skill=Skill(
                skill_project=self.project,
                primary_domain=self.linux,
                name="sudo 权限管理",
            ),
            aliases=("sudo 管理",),
            related_domains=(),
        )
        actor = self.user_with_permissions(
            "node-maintainer",
            "manage_all_technical_domains",
            "add_skilltreenode",
        )

        node = create_skill_in_tree(
            tree_version=self.tree,
            technical_domain=self.linux,
            parent=None,
            name="sudo 管理",
            actor=actor,
        )

        self.assertEqual(node.skill, existing)
        self.assertEqual(Skill.objects.count(), 1)

    def test_high_similarity_requires_confirmation_and_description(self):
        save_skill(
            skill=Skill(
                skill_project=self.project,
                primary_domain=self.linux,
                name="Linux 用户管理",
            ),
            aliases=(),
            related_domains=(),
        )
        with self.assertRaisesMessage(ValidationError, "高度相似"):
            create_skill_in_tree(
                tree_version=self.tree,
                technical_domain=self.linux,
                parent=None,
                name="Linux 用户和组管理",
                actor=self.actor,
            )
        with self.assertRaisesMessage(ValidationError, "描述"):
            create_skill_in_tree(
                tree_version=self.tree,
                technical_domain=self.linux,
                parent=None,
                name="Linux 用户和组管理",
                actor=self.actor,
                confirm_distinct=True,
            )

    def test_inactive_skill_duplicate_and_inactive_domain_are_rejected(self):
        inactive = self.skill("旧技能", is_active=False)
        with self.assertRaisesMessage(ValidationError, "已停用的技能"):
            attach_existing_skill_to_tree(
                tree_version=self.tree,
                technical_domain=self.linux,
                parent=None,
                skill=inactive,
                actor=self.actor,
            )
        active = self.skill("活动技能")
        attach_existing_skill_to_tree(
            tree_version=self.tree,
            technical_domain=self.linux,
            parent=None,
            skill=active,
            actor=self.actor,
        )
        with self.assertRaisesMessage(ValidationError, "已存在于当前版本"):
            attach_existing_skill_to_tree(
                tree_version=self.tree,
                technical_domain=self.linux,
                parent=None,
                skill=active,
                actor=self.actor,
            )
        self.windows.is_active = False
        self.windows.save(update_fields=["is_active"])
        with self.assertRaisesMessage(ValidationError, "已停用的技术领域"):
            create_skill_in_tree(
                tree_version=self.tree,
                technical_domain=self.windows,
                parent=None,
                name="Windows 根",
                actor=self.actor,
            )

    def test_reorder_and_promote_children_preserve_user_visible_order(self):
        before = self.node("前", order=10)
        parent = self.node("父", order=20)
        first_child = self.node("子一", parent=parent, order=10)
        second_child = self.node("子二", parent=parent, order=20)
        after = self.node("后", order=30)

        reorder_skill_tree_node(node=after, direction="up", actor=self.actor)
        self.assertEqual(
            list(
                SkillTreeNode.objects.filter(parent=None).order_by("order", "pk").values_list("skill__name", flat=True)
            ),
            ["前", "后", "父"],
        )

        remove_skill_tree_node(node=parent, mode="promote_children", actor=self.actor)
        self.assertEqual(
            list(SkillTreeNode.objects.filter(parent=None).order_by("order", "pk").values_list("skill__name", "order")),
            [("前", 10), ("后", 20), ("子一", 30), ("子二", 40)],
        )
        self.assertTrue(Skill.objects.filter(pk=parent.skill_id).exists())
        self.assertEqual(first_child.skill.tree_nodes.count(), 1)
        self.assertEqual(second_child.skill.tree_nodes.count(), 1)
        self.assertTrue(Skill.objects.filter(pk=before.skill_id).exists())

    def test_move_subtree_cross_domain_validates_every_skill_and_rolls_back(self):
        root = self.node("跨域根")
        child = self.node("仅 Linux", parent=root)
        root.skill.related_domains.add(self.windows)

        with self.assertRaisesMessage(ValidationError, "仅 Linux"):
            move_skill_tree_node(
                node=root,
                new_parent=None,
                target_domain=self.windows,
                actor=self.actor,
            )
        root.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual(root.technical_domain, self.linux)
        self.assertEqual(child.technical_domain, self.linux)

        child.skill.related_domains.add(self.windows)
        move_skill_tree_node(
            node=root,
            new_parent=None,
            target_domain=self.windows,
            actor=self.actor,
        )
        root.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual(root.technical_domain, self.windows)
        self.assertEqual(child.technical_domain, self.windows)

    def test_remove_subtree_keeps_every_skill(self):
        root = self.node("根")
        child = self.node("子", parent=root)
        skill_ids = [root.skill_id, child.skill_id]

        removed = remove_skill_tree_node(node=root, mode="subtree", actor=self.actor)

        self.assertEqual(removed, 2)
        self.assertFalse(SkillTreeNode.objects.filter(pk__in=[root.pk, child.pk]).exists())
        self.assertEqual(Skill.objects.filter(pk__in=skill_ids).count(), 2)

    def test_skill_domain_change_cannot_invalidate_existing_tree_position(self):
        skill = self.skill("跨域技能")
        skill.related_domains.add(self.windows)
        node = SkillTreeNode.objects.create(
            tree_version=self.tree,
            technical_domain=self.windows,
            skill=skill,
        )

        with self.assertRaisesMessage(ValidationError, "请先移动或移除"):
            save_skill(skill=skill, aliases=(), related_domains=())

        self.assertTrue(SkillTreeNode.objects.filter(pk=node.pk).exists())
        self.assertTrue(skill.related_domains.filter(pk=self.windows.pk).exists())


class SkillTreePermissionAndViewTests(SkillTreeFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.project_admin()
        self.client.force_login(self.admin)

    def test_model_permission_without_domain_scope_is_rejected(self):
        actor = self.user_with_permissions("unscoped", "add_skilltreenode")
        skill = self.skill("技能")
        with self.assertRaises(PermissionDenied):
            attach_existing_skill_to_tree(
                tree_version=self.tree,
                technical_domain=self.linux,
                parent=None,
                skill=skill,
                actor=actor,
            )

    def test_tree_detail_renders_domains_and_arbitrary_depth_without_old_terms(self):
        root = self.node("系统管理")
        child = self.node("用户管理", parent=root)
        self.node("sudo", parent=child)

        response = self.client.get(reverse("standards:tree_detail", args=[self.tree.pk]))

        self.assertContains(response, "Linux")
        self.assertContains(response, "系统管理")
        self.assertContains(response, "用户管理")
        self.assertContains(response, "sudo")
        self.assertNotContains(response, "技能分类")
        self.assertNotContains(response, "能力主题")
        self.assertNotContains(response, "节点代码")
        self.assertNotContains(response, "SK-")

    def test_htmx_quick_add_returns_panel_and_created_event(self):
        response = self.client.post(
            reverse(
                "standards:tree_quick_add_root",
                kwargs={"tree_pk": self.tree.pk, "domain_pk": self.linux.pk},
            ),
            {"name": "系统管理"},
            HTTP_HX_REQUEST="true",
        )

        node = SkillTreeNode.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="skill-tree-panel"')
        self.assertJSONEqual(
            response.headers["HX-Trigger-After-Swap"],
            {"skillTreeNodeCreated": {"nodeId": node.pk}},
        )

    def test_candidate_fragment_includes_distinct_skill_confirmation_fields(self):
        self.skill("sudo 权限管理")

        response = self.client.get(
            reverse(
                "standards:tree_candidates_root",
                kwargs={"tree_pk": self.tree.pk, "domain_pk": self.linux.pk},
            ),
            {"name": "sudo 权限管理"},
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, "可能已有相同或相近技能")
        self.assertContains(response, 'name="description"')
        self.assertContains(response, 'name="confirm_distinct"')

    def test_node_only_maintainer_can_attach_exact_existing_skill_by_post(self):
        existing = save_skill(
            skill=Skill(
                skill_project=self.project,
                primary_domain=self.linux,
                name="sudo 权限管理",
            ),
            aliases=("sudo 管理",),
            related_domains=(),
        )
        node_only = self.user_with_permissions(
            "node-only",
            "manage_all_technical_domains",
            "view_skilltreeversion",
            "add_skilltreenode",
        )
        self.client.force_login(node_only)

        response = self.client.post(
            reverse(
                "standards:tree_quick_add_root",
                kwargs={"tree_pk": self.tree.pk, "domain_pk": self.linux.pk},
            ),
            {"name": "sudo 管理"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SkillTreeNode.objects.get().skill, existing)
        self.assertEqual(Skill.objects.count(), 1)

    def test_direct_tree_write_posts_are_rejected_without_permissions(self):
        node = self.node("受保护技能")
        viewer = self.user_with_permissions("write-viewer", "view_skilltreeversion")
        self.client.force_login(viewer)

        quick_add = self.client.post(
            reverse(
                "standards:tree_quick_add_root",
                kwargs={"tree_pk": self.tree.pk, "domain_pk": self.linux.pk},
            ),
            {"name": "越权新增"},
            HTTP_HX_REQUEST="true",
        )
        move = self.client.post(
            reverse("standards:tree_node_move", args=[self.tree.pk, node.pk]),
            {"target_domain": self.linux.pk, "new_parent": ""},
            HTTP_HX_REQUEST="true",
        )
        remove = self.client.post(
            reverse("standards:tree_node_remove", args=[self.tree.pk, node.pk]),
            {"mode": "promote_children"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(quick_add.status_code, 403)
        self.assertEqual(move.status_code, 403)
        self.assertEqual(remove.status_code, 403)
        self.assertFalse(Skill.objects.filter(name="越权新增").exists())

    def test_viewer_sees_tree_without_workbench_actions(self):
        self.node("只读技能")
        viewer = self.user_with_permissions("viewer", "view_skilltreeversion")
        self.client.force_login(viewer)

        response = self.client.get(reverse("standards:tree_detail", args=[self.tree.pk]))

        self.assertContains(response, "只读技能")
        self.assertNotContains(response, "新增根技能")
        self.assertNotContains(response, "从树中移除")

    def test_selector_query_count_does_not_grow_with_node_count(self):
        self.admin.has_perm("standards.view_skilltreeversion")
        with CaptureQueriesContext(connection) as small_queries:
            skill_tree_structure(tree_version=self.tree, user=self.admin)
        root = self.node("根")
        for index in range(12):
            self.node(f"技能 {index}", parent=root, order=index * 10)
        with CaptureQueriesContext(connection) as large_queries:
            skill_tree_structure(tree_version=self.tree, user=self.admin)

        self.assertEqual(len(small_queries), len(large_queries))

    def test_legacy_skill_code_no_longer_matches_catalog_search(self):
        skill = self.skill("Linux 服务")
        response = self.client.get(
            reverse(
                "standards:domain_detail",
                kwargs={"project_pk": self.project.pk, "domain_pk": self.linux.pk},
            ),
            {"q": f"SK-{skill.pk:06d}"},
        )

        self.assertNotContains(response, skill.name)
