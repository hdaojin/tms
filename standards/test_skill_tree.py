from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .forms import SkillTreeVersionForm
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
from .selectors import search_skill_tree_nodes, skill_tree_structure
from .services import (
    attach_existing_skill_to_tree,
    clone_skill_tree_version,
    create_skill_in_tree,
    move_skill_tree_node,
    remove_skill_tree_node,
    reorder_skill_tree_node,
    set_current_skill_tree_version,
    set_skill_related_domains,
)


User = get_user_model()


class SkillTreeFixtureMixin:
    def setUp(self):
        super().setUp()
        self.project = SkillProject.objects.create(code="NS", name="网络系统管理", is_default=True)
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
            technical_domain=self.linux,
            version="2026",
            name="2026 Linux 技能树",
            is_current=True,
        )

    def skill(self, name, domain=None, **kwargs):
        return Skill.objects.create(
            skill_project=self.project,
            primary_domain=domain or self.linux,
            name=name,
            **kwargs,
        )

    def node(self, name, *, parent=None, order=0, skill=None):
        return SkillTreeNode.objects.create(
            tree_version=self.tree,
            parent=parent,
            skill=skill or self.skill(name),
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
        return User.objects.create_superuser(username="project-admin")

    def domain_user(self, username="domain-maintainer", *codenames, domain=None):
        user = User.objects.create_user(username=username)
        group = Group.objects.create(name=f"{username}-group")
        group.permissions.add(
            *Permission.objects.filter(
                content_type__app_label="standards",
                codename__in=codenames,
            )
        )
        TechnicalDomainGroupScope.objects.create(group=group, technical_domain=domain or self.linux)
        user.groups.add(group)
        return User.objects.get(pk=user.pk)


class DomainOwnedSkillTreeModelTests(SkillTreeFixtureMixin, TestCase):
    def test_versions_are_unique_and_current_per_domain(self):
        windows_tree = SkillTreeVersion.objects.create(
            technical_domain=self.windows,
            version="2026",
            name="2026 Windows 技能树",
            is_current=True,
        )
        self.assertTrue(self.tree.is_current)
        self.assertTrue(windows_tree.is_current)

        replacement = SkillTreeVersion.objects.create(
            technical_domain=self.linux,
            version="2027",
            name="2027 Linux 技能树",
            is_current=True,
        )
        self.tree.refresh_from_db()
        self.assertFalse(self.tree.is_current)
        self.assertTrue(replacement.is_current)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SkillTreeVersion.objects.create(
                technical_domain=self.linux,
                version="2027",
                name="重复版本",
            )

    def test_node_domain_is_derived_and_skill_must_allow_it(self):
        node = self.node("用户与权限")
        self.assertEqual(node.technical_domain, self.linux)
        self.assertEqual(node.skill_project, self.project)

        windows_skill = self.skill("Windows 服务", self.windows)
        with self.assertRaisesMessage(ValidationError, "未关联技能树所属技术领域"):
            SkillTreeNode.objects.create(tree_version=self.tree, skill=windows_skill)

        windows_skill.related_domains.add(self.linux)
        shared_node = SkillTreeNode.objects.create(tree_version=self.tree, skill=windows_skill)
        self.assertEqual(shared_node.technical_domain, self.linux)

    def test_parent_must_share_tree_and_tree_allows_arbitrary_depth(self):
        root = self.node("系统管理", order=10)
        child = self.node("用户管理", parent=root, order=10)
        grandchild = self.node("sudo", parent=child, order=10)
        self.assertEqual(grandchild.get_full_path(), "系统管理 / 用户管理 / sudo")

        other_tree = SkillTreeVersion.objects.create(
            technical_domain=self.linux,
            version="历史",
            name="历史版本",
        )
        with self.assertRaisesMessage(ValidationError, "同一技能树版本"):
            SkillTreeNode.objects.create(
                tree_version=other_tree,
                parent=root,
                skill=self.skill("错误父节点"),
            )

    def test_same_skill_once_per_tree_but_reusable_across_domains(self):
        shared = self.skill("网络服务")
        shared.related_domains.add(self.windows)
        SkillTreeNode.objects.create(tree_version=self.tree, skill=shared)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SkillTreeNode.objects.create(tree_version=self.tree, skill=shared)

        windows_tree = SkillTreeVersion.objects.create(
            technical_domain=self.windows,
            version="2026",
            name="Windows 2026",
        )
        SkillTreeNode.objects.create(tree_version=windows_tree, skill=shared)
        self.assertEqual(shared.tree_nodes.count(), 2)

    def test_based_on_is_same_domain_and_immutable(self):
        derived = SkillTreeVersion.objects.create(
            technical_domain=self.linux,
            based_on=self.tree,
            version="2027",
            name="2027",
        )
        windows_tree = SkillTreeVersion.objects.create(
            technical_domain=self.windows,
            version="2027",
            name="Windows 2027",
        )
        derived.based_on = windows_tree
        with self.assertRaisesMessage(ValidationError, "创建后不能更改基于版本"):
            derived.save()

        invalid = SkillTreeVersion(
            technical_domain=self.windows,
            based_on=self.tree,
            version="2028",
            name="错误来源",
        )
        with self.assertRaisesMessage(ValidationError, "同一技术领域"):
            invalid.save()

    def test_related_domain_cannot_be_removed_while_tree_uses_it(self):
        shared = self.skill("共享服务")
        shared.related_domains.add(self.windows)
        windows_tree = SkillTreeVersion.objects.create(
            technical_domain=self.windows,
            version="2026",
            name="Windows 2026",
        )
        SkillTreeNode.objects.create(tree_version=windows_tree, skill=shared)
        with self.assertRaises(ValidationError):
            set_skill_related_domains(shared, [])


class SkillTreeServiceTests(SkillTreeFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.actor = self.project_admin()

    def test_create_attach_move_reorder_and_remove(self):
        root = create_skill_in_tree(
            tree_version=self.tree,
            parent=None,
            name="系统管理",
            actor=self.actor,
        )
        child = create_skill_in_tree(
            tree_version=self.tree,
            parent=root,
            name="用户管理",
            actor=self.actor,
        )
        sibling_skill = self.skill("软件包管理")
        sibling = attach_existing_skill_to_tree(
            tree_version=self.tree,
            parent=None,
            skill=sibling_skill,
            actor=self.actor,
        )
        self.assertEqual((root.order, sibling.order), (10, 20))

        reorder_skill_tree_node(node=sibling, direction="up", actor=self.actor)
        sibling.refresh_from_db()
        self.assertEqual(sibling.order, 10)

        move_skill_tree_node(node=sibling, new_parent=root, actor=self.actor)
        sibling.refresh_from_db()
        self.assertEqual(sibling.parent, root)

        removed = remove_skill_tree_node(node=root, mode="promote_children", actor=self.actor)
        child.refresh_from_db()
        sibling.refresh_from_db()
        self.assertEqual(removed, 1)
        self.assertIsNone(child.parent)
        self.assertIsNone(sibling.parent)
        self.assertTrue(Skill.objects.filter(pk=root.skill_id).exists())

    def test_move_rejects_other_tree_parent_and_descendant(self):
        root = self.node("根")
        child = self.node("子", parent=root)
        with self.assertRaisesMessage(ValidationError, "自身或其下级"):
            move_skill_tree_node(node=root, new_parent=child, actor=self.actor)

        other_tree = SkillTreeVersion.objects.create(
            technical_domain=self.linux,
            version="2027",
            name="2027",
        )
        other_parent = SkillTreeNode.objects.create(
            tree_version=other_tree,
            skill=self.skill("另一版本根"),
        )
        with self.assertRaisesMessage(ValidationError, "当前技能树版本"):
            move_skill_tree_node(node=root, new_parent=other_parent, actor=self.actor)

    def test_domain_scope_permission_is_required(self):
        outsider = self.user_with_permissions(
            "outsider",
            "add_skill",
            "add_skilltreenode",
        )
        with self.assertRaises(PermissionDenied):
            create_skill_in_tree(
                tree_version=self.tree,
                parent=None,
                name="无权技能",
                actor=outsider,
            )

    def test_same_group_scope_allows_tree_node_maintenance(self):
        maintainer = self.domain_user(
            "linux-maintainer",
            "add_skill",
            "add_skilltreenode",
        )

        node = create_skill_in_tree(
            tree_version=self.tree,
            parent=None,
            name="受控技能",
            actor=maintainer,
        )

        self.assertEqual(node.technical_domain, self.linux)


class SkillTreeCloneTests(SkillTreeFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.actor = self.project_admin()
        self.root = self.node("根", order=10)
        self.child = self.node("子", parent=self.root, order=20)

    def test_clone_preserves_structure_reuses_skills_and_is_not_current(self):
        clone = clone_skill_tree_version(
            source_version=self.tree,
            version="2027",
            name="2027 Linux 技能树",
            description="由 2026 复制",
            actor=self.actor,
        )
        clone_nodes = list(clone.nodes.order_by("order", "pk"))
        self.assertEqual(clone.based_on, self.tree)
        self.assertFalse(clone.is_current)
        self.assertEqual({node.skill_id for node in clone_nodes}, {self.root.skill_id, self.child.skill_id})
        cloned_child = next(node for node in clone_nodes if node.skill_id == self.child.skill_id)
        self.assertEqual(cloned_child.parent.skill_id, self.root.skill_id)
        self.assertNotIn(cloned_child.pk, {self.root.pk, self.child.pk})

        cloned_child.order = 99
        cloned_child.save()
        self.child.refresh_from_db()
        self.assertEqual(self.child.order, 20)

    def test_domain_group_cannot_govern_versions(self):
        maintainer = self.domain_user(
            "version-outsider",
            "add_skilltreeversion",
            "change_skilltreeversion",
        )

        with self.assertRaises(PermissionDenied):
            clone_skill_tree_version(
                source_version=self.tree,
                version="2028",
                name="2028",
                description="",
                actor=maintainer,
            )
        with self.assertRaises(PermissionDenied):
            set_current_skill_tree_version(tree_version=self.tree, actor=maintainer)

    def test_form_supports_current_history_and_blank_modes(self):
        history = SkillTreeVersion.objects.create(
            technical_domain=self.linux,
            version="2025",
            name="2025",
        )
        SkillTreeNode.objects.create(tree_version=history, skill=self.skill("历史技能"))

        current_form = SkillTreeVersionForm(
            data={
                "creation_mode": "current",
                "version": "2027",
                "name": "2027",
                "description": "",
            },
            technical_domain=self.linux,
            actor=self.actor,
        )
        self.assertTrue(current_form.is_valid(), current_form.errors)
        self.assertEqual(current_form.save().based_on, self.tree)

        history_form = SkillTreeVersionForm(
            data={
                "creation_mode": "existing",
                "source_version": history.pk,
                "version": "2028",
                "name": "2028",
                "description": "",
            },
            technical_domain=self.linux,
            actor=self.actor,
        )
        self.assertTrue(history_form.is_valid(), history_form.errors)
        self.assertEqual(history_form.save().based_on, history)

        blank_form = SkillTreeVersionForm(
            data={
                "creation_mode": "blank",
                "version": "2029",
                "name": "2029",
                "description": "",
            },
            technical_domain=self.linux,
            actor=self.actor,
        )
        self.assertTrue(blank_form.is_valid(), blank_form.errors)
        blank = blank_form.save()
        self.assertIsNone(blank.based_on)
        self.assertFalse(blank.nodes.exists())

    def test_set_current_is_separate_and_scoped_per_domain(self):
        clone = clone_skill_tree_version(
            source_version=self.tree,
            version="2027",
            name="2027",
            description="",
            actor=self.actor,
        )
        set_current_skill_tree_version(tree_version=clone, actor=self.actor)
        clone.refresh_from_db()
        self.tree.refresh_from_db()
        self.assertTrue(clone.is_current)
        self.assertFalse(self.tree.is_current)


class SkillTreeSelectorAndPageTests(SkillTreeFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = self.project_admin()
        self.client.force_login(self.user)
        self.root = self.node("网络服务", order=10)
        self.child = self.node("DNS 服务", parent=self.root, order=10)
        SkillTerm.objects.create(
            skill_project=self.project,
            skill=self.child.skill,
            term="域名解析",
            kind=SkillTerm.Kind.ALIAS,
        )

    def test_structure_and_search_use_single_domain_tree(self):
        domain = skill_tree_structure(tree_version=self.tree, user=self.user)
        self.assertEqual(domain, self.linux)
        self.assertEqual(domain.tree_roots, [self.root])
        self.assertEqual(domain.tree_roots[0].tree_children, [self.child])

        results = search_skill_tree_nodes(tree_version=self.tree, user=self.user, query="域名解析")
        self.assertEqual([node.pk for node in results], [self.child.pk])
        self.assertEqual(results[0].full_path, "网络服务 / DNS 服务")
        self.assertEqual(search_skill_tree_nodes(tree_version=self.tree, user=self.user, query=""), [])

    def test_tree_and_list_views_and_filters(self):
        wsos = WSOSVersion.objects.create(
            skill_project=self.project,
            code="2026",
            name="WSOS 2026",
            is_current=True,
        )
        section = WSOSSection.objects.create(wsos_version=wsos, code="1", name="工作组织", weight=20)
        SkillWSOSMap.objects.create(skill=self.child.skill, wsos_section=section)

        tree_response = self.client.get(reverse("standards:tree_detail", args=[self.tree.pk]))
        self.assertContains(tree_response, "网络服务")
        self.assertContains(tree_response, reverse("standards:tree_node_list", args=[self.tree.pk]))

        listed = self.client.get(
            reverse("standards:tree_node_list", args=[self.tree.pk]),
            {"q": "DNS", "wsos": "mapped"},
        )
        self.assertContains(listed, "DNS 服务")
        self.assertEqual([node.pk for node in listed.context["table"].data], [self.child.pk])

        unmapped = self.client.get(
            reverse("standards:tree_node_list", args=[self.tree.pk]),
            {"wsos": "unmapped"},
        )
        self.assertContains(unmapped, "网络服务")
        self.assertEqual([node.pk for node in unmapped.context["table"].data], [self.root.pk])

    def test_search_fragment_returns_path(self):
        response = self.client.get(
            reverse("standards:tree_search", args=[self.tree.pk]),
            {"q": "域名解析"},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, "网络服务 / DNS 服务")

    def test_version_list_filters_by_project_domain_and_current(self):
        other = SkillTreeVersion.objects.create(
            technical_domain=self.windows,
            version="2026",
            name="Windows 2026",
        )
        response = self.client.get(
            reverse("standards:tree_list"),
            {"project": self.project.pk, "domain": self.linux.pk, "current": "1"},
        )
        self.assertContains(response, self.tree.name)
        self.assertNotContains(response, other.name)
