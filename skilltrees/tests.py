from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from assessments.models import Assessment, AssessmentModule
from competition_standards.models import CompetitionType, Project, StandardModule, TrainingCycle
from core.constants import GROUP_COACH
from marking.models import (
    MarkingAspect,
    MarkingAspectSkillNodeMap,
    MarkingScheme,
    MarkingSchemeImport,
    MarkingSubCriterion,
)

from .models import SkillNode, SkillTree


User = get_user_model()


class SkillTreeModelTests(TestCase):
    def setUp(self):
        competition_type = CompetitionType.objects.create(code="WSC-TREE", name="技能树测试赛事")
        self.project = Project.objects.create(
            competition_type=competition_type,
            code="ITNSA-TREE",
            name="技能树测试赛项",
        )
        module_set = self.project.get_or_create_default_standard_module_set()
        self.module = StandardModule.objects.create(
            project=self.project,
            module_set=module_set,
            code="A",
            name="Linux environments",
        )

    def test_only_one_current_tree_is_kept_per_standard_module(self):
        first_tree = SkillTree.objects.create(
            module=self.module,
            name="Linux 技能树",
            version="v1",
            is_current=True,
        )
        second_tree = SkillTree.objects.create(
            module=self.module,
            name="Linux 技能树",
            version="v2",
            is_current=True,
        )

        first_tree.refresh_from_db()
        second_tree.refresh_from_db()
        self.assertFalse(first_tree.is_current)
        self.assertTrue(second_tree.is_current)

    def test_node_parent_must_belong_to_same_tree(self):
        other_module = StandardModule.objects.create(
            project=self.project,
            module_set=self.module.module_set,
            code="B",
            name="Module B",
        )
        first_tree = SkillTree.objects.create(module=self.module, name="A 树", version="v1")
        second_tree = SkillTree.objects.create(module=other_module, name="B 树", version="v1")
        parent = SkillNode.objects.create(tree=first_tree, code="A-1", name="A 节点")

        with self.assertRaises(ValidationError):
            SkillNode.objects.create(
                tree=second_tree,
                parent=parent,
                code="B-1",
                name="B 节点",
            )


class SkillTreeViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="skilltree-admin",
            password="testpass123",
            email="skilltree-admin@example.com",
        )
        coach_group = Group.objects.create(name=GROUP_COACH)
        self.user.groups.add(coach_group)
        competition_type = CompetitionType.objects.create(code="WSC-TREE-VIEW", name="技能树页面测试赛事")
        self.project = Project.objects.create(
            competition_type=competition_type,
            code="ITNSA-TREE-VIEW",
            name="技能树页面测试赛项",
        )
        self.module_set = self.project.get_or_create_default_standard_module_set()
        self.module = StandardModule.objects.create(
            project=self.project,
            module_set=self.module_set,
            code="A",
            name="Linux environments",
        )
        self.tree = SkillTree.objects.create(
            module=self.module,
            name="Linux 技能树",
            version="v1",
            is_current=True,
            created_by=self.user,
        )

    def create_scheme_with_aspects(self):
        suffix = MarkingScheme.objects.count() + 1
        training_cycle = TrainingCycle.objects.create(
            code=f"TC-TREE-{suffix}",
            name=f"技能树测试周期 {suffix}",
            project=self.project,
            module_set=self.module_set,
            start_date=date(2026, 1, 1),
        )
        assessment = Assessment.objects.create(
            name=f"技能树考点测试 {suffix}",
            training_cycle=training_cycle,
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 2),
        )
        assessment_module = AssessmentModule.objects.create(
            assessment=assessment,
            module=self.module,
            responsible_coach=self.user,
            max_score=Decimal("1.00"),
        )
        content_type = ContentType.objects.get_for_model(AssessmentModule, for_concrete_model=False)
        source_import = MarkingSchemeImport.objects.create(
            file=f"schemes/tree-coverage-{suffix}.xlsx",
            original_filename=f"tree-coverage-{suffix}.xlsx",
            file_sha256=f"{suffix:064d}"[-64:],
            parser_version="test",
            target_content_type=content_type,
            target_object_id=assessment_module.pk,
            uploaded_by=self.user,
        )
        scheme = MarkingScheme.objects.create(
            source_import=source_import,
            standard_module=self.module,
            target_content_type=content_type,
            target_object_id=assessment_module.pk,
            title=f"技能树考点覆盖评分方案 {suffix}",
            module_code=self.module.code,
            module_name=self.module.name,
            total_mark=Decimal("1.00"),
            parser_version="test",
        )
        subcriterion = MarkingSubCriterion.objects.create(
            scheme=scheme,
            code="A1",
            name="Linux 基础",
            day_of_marking="Day 1",
            sort_order=1,
        )
        aspect_a = MarkingAspect.objects.create(
            scheme=scheme,
            subcriterion=subcriterion,
            code="A1.1",
            aspect_type=MarkingAspect.AspectType.MEASUREMENT,
            description="配置主机名",
            max_mark=Decimal("0.20"),
            source_row_number=101,
            sort_order=1,
        )
        aspect_b = MarkingAspect.objects.create(
            scheme=scheme,
            subcriterion=subcriterion,
            code="A1.2",
            aspect_type=MarkingAspect.AspectType.MEASUREMENT,
            description="配置 SSH 服务",
            max_mark=Decimal("0.30"),
            source_row_number=102,
            sort_order=2,
        )
        return scheme, aspect_a, aspect_b

    def test_manual_skill_node_create_view_adds_node(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("skilltrees:node_create", args=[self.tree.pk]),
            {
                "code": "LIN-1",
                "name": "主机名配置",
                "node_type": SkillNode.NodeType.SKILL,
                "difficulty": "3",
                "sort_order": "1",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(SkillNode.objects.filter(tree=self.tree, code="LIN-1").exists())

    def test_manual_skill_node_create_view_adds_child_node(self):
        parent = SkillNode.objects.create(
            tree=self.tree,
            code="LIN",
            name="Linux 基础",
            node_type=SkillNode.NodeType.CATEGORY,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("skilltrees:node_create", args=[self.tree.pk]),
            {
                "parent": str(parent.pk),
                "code": "LIN-SSH",
                "name": "SSH 认证",
                "node_type": SkillNode.NodeType.SKILL,
                "difficulty": "3",
                "sort_order": "1",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        child = SkillNode.objects.get(tree=self.tree, code="LIN-SSH")
        self.assertEqual(child.parent, parent)

    def test_deactivate_node_keeps_node_for_history(self):
        node = SkillNode.objects.create(tree=self.tree, code="LIN-1", name="主机名配置")
        self.client.force_login(self.user)

        response = self.client.post(reverse("skilltrees:node_deactivate", args=[node.pk]))

        self.assertEqual(response.status_code, 302)
        node.refresh_from_db()
        self.assertFalse(node.is_active)

    def test_detail_defaults_to_list_view(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("skilltrees:detail", args=[self.tree.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view_mode"], "list")
        self.assertContains(response, 'id="skillnode-inline-form-panel"')
        self.assertContains(response, 'data-testid="skillnode-inline-form-row"')
        self.assertContains(response, "快速新增节点")
        self.assertContains(response, 'data-testid="skilltree-list-view"')
        self.assertContains(response, "说明")
        self.assertContains(response, "排序")
        self.assertContains(response, "创建时间")
        self.assertContains(response, "更新时间")
        self.assertContains(response, "?view=tree")
        self.assertNotContains(response, reverse("skilltrees:node_create", args=[self.tree.pk]))

    def test_detail_list_view_shows_complete_node_fields(self):
        description = (
            "这是用于验证列表完整展示的技能节点说明，包含较长的操作背景、训练目标、"
            "验收口径和后续分析用途，页面不应再把这段内容截断为摘要。"
        )
        node = SkillNode.objects.create(
            tree=self.tree,
            code="LIN-FULL",
            name="完整字段节点",
            node_type=SkillNode.NodeType.TASK,
            description=description,
            difficulty=5,
            sort_order=9,
            is_active=False,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("skilltrees:detail", args=[self.tree.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(node.pk))
        self.assertContains(response, "LIN-FULL")
        self.assertContains(response, "完整字段节点")
        self.assertContains(response, "训练任务")
        self.assertContains(response, description)
        self.assertContains(response, "5")
        self.assertContains(response, "9")
        self.assertContains(response, "停用")
        self.assertContains(response, timezone.localtime(node.created_at).strftime("%Y-%m-%d %H:%M"))
        self.assertContains(response, timezone.localtime(node.updated_at).strftime("%Y-%m-%d %H:%M"))

    def test_detail_list_view_shows_direct_and_rollup_aspect_coverage(self):
        parent = SkillNode.objects.create(
            tree=self.tree,
            code="LIN",
            name="Linux 基础",
            node_type=SkillNode.NodeType.CATEGORY,
            sort_order=1,
        )
        hostname_skill = SkillNode.objects.create(
            tree=self.tree,
            parent=parent,
            code="LIN-HOST",
            name="主机名配置",
            sort_order=1,
        )
        ssh_skill = SkillNode.objects.create(
            tree=self.tree,
            parent=parent,
            code="LIN-SSH",
            name="SSH 服务",
            sort_order=2,
        )
        scheme, aspect_a, aspect_b = self.create_scheme_with_aspects()
        MarkingAspectSkillNodeMap.objects.create(
            aspect=aspect_a,
            skill_node=hostname_skill,
            is_primary=True,
            weight=Decimal("1.00"),
        )
        MarkingAspectSkillNodeMap.objects.create(
            aspect=aspect_b,
            skill_node=ssh_skill,
            weight=Decimal("0.50"),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("skilltrees:detail", args=[self.tree.pk]))

        self.assertEqual(response.status_code, 200)
        nodes = {node.code: node for node in response.context["nodes"]}
        self.assertEqual(nodes["LIN-HOST"].aspect_coverage_count, 1)
        self.assertEqual(nodes["LIN-HOST"].aspect_coverage_total_mark, Decimal("0.20"))
        self.assertEqual(nodes["LIN"].aspect_coverage_count, 2)
        self.assertEqual(nodes["LIN"].aspect_coverage_total_mark, Decimal("0.50"))
        self.assertEqual(len(nodes["LIN"].aspect_coverage_groups), 2)
        self.assertContains(response, "考点覆盖")
        self.assertContains(response, "2 项 / 0.50 分")
        self.assertContains(response, "1 项 / 0.20 分")
        self.assertContains(response, "主技能 1")
        self.assertContains(response, "后代汇总")
        self.assertContains(response, "直接关联")
        self.assertContains(response, "配置主机名")
        self.assertContains(response, "配置 SSH 服务")
        self.assertContains(response, scheme.title)
        self.assertContains(response, reverse("marking:scheme_detail", args=[scheme.pk]))

    def test_detail_invalid_view_falls_back_to_list_view(self):
        self.client.force_login(self.user)

        response = self.client.get(f"{reverse('skilltrees:detail', args=[self.tree.pk])}?view=mind")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view_mode"], "list")
        self.assertContains(response, 'data-testid="skilltree-list-view"')
        self.assertNotContains(response, 'data-testid="skilltree-tree-view"')

    def test_detail_tree_view_builds_read_only_hierarchy(self):
        root_b = SkillNode.objects.create(
            tree=self.tree,
            code="NET",
            name="网络服务",
            node_type=SkillNode.NodeType.TOPIC,
            sort_order=2,
        )
        root_a = SkillNode.objects.create(
            tree=self.tree,
            code="LIN",
            name="Linux 基础",
            node_type=SkillNode.NodeType.CATEGORY,
            sort_order=1,
        )
        child = SkillNode.objects.create(
            tree=self.tree,
            parent=root_a,
            code="LIN.SSH",
            name="SSH 认证",
            node_type=SkillNode.NodeType.SKILL,
            description="配置 SSH 密钥认证。",
            difficulty=4,
            sort_order=1,
            is_active=False,
        )
        self.client.force_login(self.user)

        response = self.client.get(f"{reverse('skilltrees:detail', args=[self.tree.pk])}?view=tree")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view_mode"], "tree")
        self.assertContains(response, 'data-testid="skilltree-tree-view"')
        self.assertNotContains(response, reverse("skilltrees:node_edit", args=[root_a.pk]))
        self.assertNotContains(response, reverse("skilltrees:node_edit", args=[child.pk]))
        self.assertContains(response, "LIN")
        self.assertContains(response, "Linux 基础")
        self.assertContains(response, "分类")
        self.assertContains(response, "LIN.SSH")
        self.assertContains(response, "SSH 认证")
        self.assertContains(response, "配置 SSH 密钥认证。")
        self.assertContains(response, "停用")
        self.assertEqual(
            [(row["node"].code, row["depth"]) for row in response.context["tree_rows"]],
            [(root_a.code, 0), (child.code, 1), (root_b.code, 0)],
        )

    def test_detail_tree_view_shows_empty_state(self):
        self.client.force_login(self.user)

        response = self.client.get(f"{reverse('skilltrees:detail', args=[self.tree.pk])}?view=tree")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["view_mode"], "tree")
        self.assertContains(response, 'id="skillnode-inline-form-panel"')
        self.assertContains(response, 'data-testid="skilltree-tree-view"')
        self.assertContains(response, "暂无技能节点。")

    def test_detail_tree_view_shows_aspect_coverage_badges_and_grouped_rollup(self):
        parent = SkillNode.objects.create(
            tree=self.tree,
            code="LIN",
            name="Linux 基础",
            node_type=SkillNode.NodeType.CATEGORY,
            sort_order=1,
        )
        hostname_skill = SkillNode.objects.create(
            tree=self.tree,
            parent=parent,
            code="LIN-HOST",
            name="主机名配置",
            sort_order=1,
        )
        ssh_skill = SkillNode.objects.create(
            tree=self.tree,
            parent=parent,
            code="LIN-SSH",
            name="SSH 服务",
            sort_order=2,
        )
        scheme, aspect_a, aspect_b = self.create_scheme_with_aspects()
        MarkingAspectSkillNodeMap.objects.create(
            aspect=aspect_a,
            skill_node=hostname_skill,
            is_primary=True,
        )
        MarkingAspectSkillNodeMap.objects.create(
            aspect=aspect_b,
            skill_node=ssh_skill,
        )
        self.client.force_login(self.user)

        response = self.client.get(f"{reverse('skilltrees:detail', args=[self.tree.pk])}?view=tree")

        self.assertEqual(response.status_code, 200)
        rows = {row["node"].code: row["node"] for row in response.context["tree_rows"]}
        self.assertEqual(rows["LIN"].aspect_coverage_count, 2)
        self.assertEqual(rows["LIN"].aspect_coverage_total_mark, Decimal("0.50"))
        self.assertEqual(rows["LIN-HOST"].aspect_coverage_count, 1)
        self.assertContains(response, 'data-testid="skilltree-tree-view"')
        self.assertContains(response, "后代汇总：2 项 / 0.50 分")
        self.assertContains(response, "直接关联：1 项 / 0.20 分")
        self.assertContains(response, "查看后代技能点考点")
        self.assertContains(response, "查看直接关联考点")
        self.assertContains(response, "LIN-HOST")
        self.assertContains(response, "LIN-SSH")
        self.assertContains(response, "主技能")
        self.assertContains(response, scheme.title)

    def test_detail_hides_inline_form_without_add_permission(self):
        viewer = User.objects.create_user(
            username="skilltree-viewer",
            password="testpass123",
            email="skilltree-viewer@example.com",
        )
        self.client.force_login(viewer)

        response = self.client.get(reverse("skilltrees:detail", args=[self.tree.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="skillnode-inline-form-panel"')
        response = self.client.post(
            reverse("skilltrees:node_quick_create", args=[self.tree.pk]),
            {
                "code": "NOPE",
                "name": "无权限节点",
                "node_type": SkillNode.NodeType.SKILL,
                "difficulty": "3",
                "sort_order": "1",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_htmx_inline_create_root_node_refreshes_list_view(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("skilltrees:node_quick_create", args=[self.tree.pk]),
            {
                "view": "list",
                "code": "ROOT",
                "name": "根节点",
                "node_type": SkillNode.NodeType.CATEGORY,
                "difficulty": "2",
                "sort_order": "1",
                "is_active": "on",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(SkillNode.objects.filter(tree=self.tree, code="ROOT").exists())
        self.assertContains(response, 'id="skillnode-inline-form-panel"')
        self.assertContains(response, 'id="skilltree-view-panel" hx-swap-oob="outerHTML"')
        self.assertContains(response, 'data-testid="skilltree-list-view"')
        self.assertContains(response, "ROOT")
        self.assertContains(response, "技能节点已保存。")
        self.assertContains(response, "ROOT - 根节点")

    def test_htmx_inline_create_child_node_refreshes_tree_view(self):
        parent = SkillNode.objects.create(tree=self.tree, code="LIN", name="Linux 基础")
        self.client.force_login(self.user)

        response = self.client.post(
            f"{reverse('skilltrees:node_quick_create', args=[self.tree.pk])}?view=tree",
            {
                "view": "tree",
                "parent": str(parent.pk),
                "code": "LIN-SSH",
                "name": "SSH 认证",
                "node_type": SkillNode.NodeType.SKILL,
                "difficulty": "3",
                "sort_order": "1",
                "is_active": "on",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        child = SkillNode.objects.get(tree=self.tree, code="LIN-SSH")
        self.assertEqual(child.parent, parent)
        self.assertContains(response, 'id="skilltree-view-panel" hx-swap-oob="outerHTML"')
        self.assertContains(response, 'data-testid="skilltree-tree-view"')
        self.assertContains(response, "LIN-SSH")
        self.assertContains(response, "SSH 认证")

    def test_htmx_inline_create_invalid_data_returns_form_errors_only(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("skilltrees:node_quick_create", args=[self.tree.pk]),
            {
                "view": "list",
                "name": "缺少代码",
                "node_type": SkillNode.NodeType.SKILL,
                "difficulty": "3",
                "sort_order": "1",
                "is_active": "on",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SkillNode.objects.filter(tree=self.tree, name="缺少代码").exists())
        self.assertContains(response, 'id="skillnode-inline-form-panel"')
        self.assertContains(response, "这个字段是必填")
        self.assertNotContains(response, "hx-swap-oob")

    def test_non_htmx_inline_create_redirects_back_to_current_view(self):
        self.client.force_login(self.user)

        response = self.client.post(
            f"{reverse('skilltrees:node_quick_create', args=[self.tree.pk])}?view=tree",
            {
                "view": "tree",
                "code": "NET",
                "name": "网络服务",
                "node_type": SkillNode.NodeType.TOPIC,
                "difficulty": "3",
                "sort_order": "1",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith(f"{reverse('skilltrees:detail', args=[self.tree.pk])}?view=tree"))
        self.assertTrue(SkillNode.objects.filter(tree=self.tree, code="NET").exists())
