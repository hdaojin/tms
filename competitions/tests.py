from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .admin import CompetitorAdminForm, ExpertAdminForm
from core.utils.menus import get_layout_sections, get_section_menu, get_sections
from .models import (
	Competition,
	CompetitionModuleAxisMap,
	CompetitionModule,
	CompetitionModuleStandardModuleMap,
	CompetitionPerson,
	CompetitionProject,
	CompetitionResult,
	CompetitionType,
	Competitor,
	CompetitorUser,
	Expert,
	Level,
	Member,
	MemberScope,
	ModuleAxis,
	Project,
	SkillPosition,
	StandardModule,
	StandardModuleAxisMap,
	StandardModuleSet,
)


User = get_user_model()


class StandardModuleSetVersioningTests(TestCase):
	def setUp(self):
		self.competition_type = CompetitionType.objects.create(
			code='WSC',
			name='世界技能大赛',
		)
		self.project = Project.objects.create(
			code='ITNSA',
			name='网络系统管理',
		)

	def test_standard_module_without_module_set_uses_default_current_standard_module_set(self):
		module = StandardModule.objects.create(
			project=self.project,
			code='A',
			name='网络配置',
		)

		self.assertIsNotNone(module.module_set)
		self.assertTrue(module.module_set.is_current)
		self.assertEqual(self.project.current_standard_module_set, module.module_set)
		self.assertEqual(self.project.module_sets.count(), 1)

	def test_switching_current_standard_module_set_retires_previous_one(self):
		previous_module_set = self.project.get_or_create_default_standard_module_set()

		next_module_set = StandardModuleSet.objects.create(
			project=self.project,
			code='2026',
			name='2026 版标准模块',
			is_current=True,
		)

		previous_module_set.refresh_from_db()
		self.assertFalse(previous_module_set.is_current)
		self.assertEqual(self.project.current_standard_module_set, next_module_set)

	def test_same_module_code_can_exist_in_different_module_sets(self):
		default_module_set = self.project.get_or_create_default_standard_module_set()
		historical_module_set = StandardModuleSet.objects.create(
			project=self.project,
			code='2024',
			name='2024 版标准模块',
			is_current=False,
		)

		StandardModule.objects.create(
			project=self.project,
			module_set=historical_module_set,
			code='A',
			name='旧版网络配置',
		)
		current_module = StandardModule.objects.create(
			project=self.project,
			module_set=default_module_set,
			code='A',
			name='新版网络配置',
		)

		self.assertEqual(StandardModule.objects.filter(project=self.project, code='A').count(), 2)
		self.assertTrue(current_module.is_current)

	def test_module_set_must_belong_to_same_project(self):
		other_project = Project.objects.create(
			code='CLD',
			name='云计算',
		)
		other_module_set = StandardModuleSet.objects.create(
			project=other_project,
			code='default',
			name='默认标准模块集',
			is_current=True,
		)

		with self.assertRaises(ValidationError):
			StandardModule.objects.create(
				project=self.project,
				module_set=other_module_set,
				code='B',
				name='错误模块',
			)


class CompetitionModuleStandardModuleMapTests(TestCase):
	def setUp(self):
		self.competition_type = CompetitionType.objects.create(
			code='WSC-CM',
			name='模块映射测试赛事',
		)
		self.project = Project.objects.create(
			code='ITNSA-CM',
			name='模块映射测试项目',
		)
		self.module = StandardModule.objects.create(
			project=self.project,
			code='A',
			name='网络配置',
		)
		self.second_module = StandardModule.objects.create(
			project=self.project,
			code='B',
			name='服务部署',
		)
		self.primary_axis = ModuleAxis.objects.create(
			project=self.project,
			code='AX-A',
			name='A 主线',
		)
		self.secondary_axis = ModuleAxis.objects.create(
			project=self.project,
			code='AX-B',
			name='B 主线',
		)
		self.competition = Competition.objects.create(
			competition_type=self.competition_type,
			name='第47届世界技能大赛',
			code='WSC2024-CM',
		)
		self.competition_project = CompetitionProject.objects.create(
			competition=self.competition,
			project=self.project,
		)

	def create_competition_module(self, code='A', name='网络配置', primary_standard_module=None):
		competition_module = CompetitionModule.objects.create(
			competition_project=self.competition_project,
			code=code,
			name=name,
		)
		if primary_standard_module is not None:
			CompetitionModuleStandardModuleMap.objects.create(
				competition_module=competition_module,
				module=primary_standard_module,
				is_primary=True,
			)
		return competition_module

	def test_competition_module_requires_code_and_name(self):
		competition_module = CompetitionModule(
			competition_project=self.competition_project,
			code='',
			name='',
		)

		with self.assertRaises(ValidationError) as context:
			competition_module.full_clean()

		self.assertIn('code', context.exception.message_dict)
		self.assertIn('name', context.exception.message_dict)

	def test_competition_module_uses_primary_mapping(self):
		competition_module = self.create_competition_module(primary_standard_module=self.module)

		self.assertEqual(competition_module.primary_standard_module, self.module)
		mapping = competition_module.module_mappings.get(module=self.module)
		self.assertTrue(mapping.is_primary)

	def test_competition_module_falls_back_to_single_mapping_when_no_primary_exists(self):
		competition_module = self.create_competition_module(code='B', name='服务部署')
		CompetitionModuleStandardModuleMap.objects.create(
			competition_module=competition_module,
			module=self.second_module,
			is_primary=False,
		)

		self.assertEqual(competition_module.primary_standard_module, self.second_module)

	def test_competition_module_can_map_to_multiple_standard_modules(self):
		competition_module = self.create_competition_module(primary_standard_module=self.module)
		CompetitionModuleStandardModuleMap.objects.create(
			competition_module=competition_module,
			module=self.second_module,
			weight='0.40',
		)

		self.assertEqual(competition_module.module_mappings.count(), 2)
		self.assertCountEqual(
			competition_module.module_mappings.values_list('module__name', flat=True),
			['网络配置', '服务部署'],
		)

	def test_competition_module_inline_can_display_mapping_summary(self):
		competition_module = self.create_competition_module(primary_standard_module=self.module)
		CompetitionModuleAxisMap.objects.create(
			competition_module=competition_module,
			module_axis=self.primary_axis,
			is_primary=True,
		)
		CompetitionModuleStandardModuleMap.objects.create(
			competition_module=competition_module,
			module=self.second_module,
			weight='0.40',
		)

		competition_project_admin = admin.site._registry[CompetitionProject]
		inline = competition_project_admin.inlines[0](CompetitionProject, admin.site)
		summary = inline.mapped_modules_summary(competition_module)
		axis_summary = inline.mapped_axes_summary(competition_module)

		self.assertEqual(
			inline.fields,
			('sort_order', 'code', 'name', 'mapped_modules_summary', 'mapped_axes_summary'),
		)
		self.assertIn('★ A - 网络配置', summary)
		self.assertIn('B - 服务部署', summary)
		self.assertIn('★ AX-A - A 主线', axis_summary)

	def test_only_one_primary_mapping_is_allowed_per_competition_module(self):
		competition_module = self.create_competition_module(primary_standard_module=self.module)
		duplicate_primary_mapping = CompetitionModuleStandardModuleMap(
			competition_module=competition_module,
			module=self.second_module,
			is_primary=True,
		)

		with self.assertRaises(ValidationError) as context:
			duplicate_primary_mapping.full_clean()

		self.assertIn('is_primary', context.exception.message_dict)

	def test_mapping_module_must_match_competition_project_project(self):
		other_project = Project.objects.create(
			code='CLD-CM',
			name='其他项目',
		)
		other_module = StandardModule.objects.create(
			project=other_project,
			code='Z',
			name='越界模块',
		)
		competition_module = self.create_competition_module(primary_standard_module=self.module)

		with self.assertRaises(ValidationError):
			CompetitionModuleStandardModuleMap.objects.create(
				competition_module=competition_module,
				module=other_module,
			)

	def test_standard_module_primary_axis_comes_from_primary_axis_mapping(self):
		StandardModuleAxisMap.objects.create(
			module=self.module,
			module_axis=self.primary_axis,
			is_primary=True,
		)
		StandardModuleAxisMap.objects.create(
			module=self.module,
			module_axis=self.secondary_axis,
			weight='0.40',
		)

		self.assertEqual(self.module.primary_axis, self.primary_axis)

	def test_competition_module_primary_axis_falls_back_to_primary_standard_module_axis(self):
		StandardModuleAxisMap.objects.create(
			module=self.module,
			module_axis=self.primary_axis,
			is_primary=True,
		)
		competition_module = self.create_competition_module(primary_standard_module=self.module)

		self.assertEqual(competition_module.primary_axis, self.primary_axis)

	def test_competition_module_primary_axis_prefers_direct_axis_mapping(self):
		StandardModuleAxisMap.objects.create(
			module=self.module,
			module_axis=self.primary_axis,
			is_primary=True,
		)
		competition_module = self.create_competition_module(primary_standard_module=self.module)
		CompetitionModuleAxisMap.objects.create(
			competition_module=competition_module,
			module_axis=self.secondary_axis,
			is_primary=True,
		)

		self.assertEqual(competition_module.primary_axis, self.secondary_axis)


class CompetitionArchiveIntegrityTests(TestCase):
	def setUp(self):
		self.competition_type = CompetitionType.objects.create(
			code='WSC-ARCHIVE',
			name='归档完整性测试赛事',
		)
		self.project = Project.objects.create(
			code='ITNSA-ARCHIVE',
			name='归档完整性测试项目',
		)
		self.module = StandardModule.objects.create(
			project=self.project,
			code='A',
			name='网络配置',
		)
		self.member = Member.objects.create(name='中国', code='CN', level=MemberScope.INTERNATIONAL)
		self.competition = Competition.objects.create(
			competition_type=self.competition_type,
			name='第47届世界技能大赛',
			code='WSC2024-ARCHIVE',
		)
		self.competition_project = CompetitionProject.objects.create(
			competition=self.competition,
			project=self.project,
		)
		self.competition_module = CompetitionModule.objects.create(
			competition_project=self.competition_project,
			code='A',
			name='网络配置',
		)
		CompetitionModuleStandardModuleMap.objects.create(
			competition_module=self.competition_module,
			module=self.module,
			is_primary=True,
		)
		self.competitor_person = CompetitionPerson.objects.create(name='选手甲')
		self.competitor = Competitor.objects.create(
			competition_project=self.competition_project,
			person=self.competitor_person,
			member=self.member,
		)

	def test_competition_result_must_be_unique_per_competitor(self):
		CompetitionResult.objects.create(competitor=self.competitor, score_700='680.00')
		duplicate_result = CompetitionResult(competitor=self.competitor, score_700='675.00')

		with self.assertRaises(ValidationError):
			duplicate_result.full_clean()

	def test_competitor_requires_competition_project(self):
		competitor = Competitor(
			competition_project=None,
			person=self.competitor_person,
			member=self.member,
		)

		with self.assertRaises(ValidationError):
			competitor.full_clean()

	def test_deleting_project_is_protected_when_competition_project_exists(self):
		with self.assertRaises(ProtectedError):
			self.project.delete()

	def test_deleting_competitor_is_protected_when_result_exists(self):
		CompetitionResult.objects.create(competitor=self.competitor, score_700='680.00')

		with self.assertRaises(ProtectedError):
			self.competitor.delete()


class CompetitionMemberLevelTests(TestCase):
	def setUp(self):
		self.competition_type = CompetitionType.objects.create(
			code='WSC-LEVEL',
			name='代表队层级测试赛事',
			level=Level.INTERNATIONAL,
		)
		self.project = Project.objects.create(
			code='ITNSA-LEVEL',
			name='代表队层级测试项目',
		)
		self.competition = Competition.objects.create(
			competition_type=self.competition_type,
			name='第47届世界技能大赛',
			code='WSC2024-LEVEL',
		)
		self.competition_project = CompetitionProject.objects.create(
			competition=self.competition,
			project=self.project,
		)
		self.country_member = Member.objects.create(
			name='中国',
			code='CN',
			level=MemberScope.INTERNATIONAL,
		)
		self.province_member = Member.objects.create(
			name='浙江省',
			code='ZJ',
			level=MemberScope.NATIONAL,
		)
		self.expert_person = CompetitionPerson.objects.create(
			name='专家甲',
			organization='测试单位',
		)
		self.competitor_person = CompetitionPerson.objects.create(
			name='选手甲',
			organization='测试单位',
		)

	def test_competitor_rejects_member_with_mismatched_level(self):
		competitor = Competitor(
			competition_project=self.competition_project,
			person=self.competitor_person,
			member=self.province_member,
		)

		with self.assertRaises(ValidationError) as context:
			competitor.full_clean()

		self.assertIn('member', context.exception.message_dict)

	def test_expert_rejects_member_with_mismatched_level(self):
		expert = Expert(
			competition_project=self.competition_project,
			person=self.expert_person,
			member=self.province_member,
		)

		with self.assertRaises(ValidationError) as context:
			expert.full_clean()

		self.assertIn('member', context.exception.message_dict)

	def test_member_forms_only_show_matching_level_choices(self):
		competitor_form = CompetitorAdminForm(competition_project=self.competition_project)
		expert_form = ExpertAdminForm(competition_project=self.competition_project)

		self.assertEqual(
			list(competitor_form.fields['member'].queryset.values_list('pk', flat=True)),
			[self.country_member.pk],
		)
		self.assertEqual(
			list(expert_form.fields['member'].queryset.values_list('pk', flat=True)),
			[self.country_member.pk],
		)

	def test_member_forms_handle_unsaved_competition_project(self):
		unsaved_competition_project = CompetitionProject()

		competitor_form = CompetitorAdminForm(competition_project=unsaved_competition_project)
		expert_form = ExpertAdminForm(competition_project=unsaved_competition_project)

		self.assertFalse(competitor_form.fields['member'].queryset.exists())
		self.assertFalse(expert_form.fields['member'].queryset.exists())
		self.assertEqual(
			competitor_form.fields['member'].help_text,
			'请先选择具体赛项，再选择匹配层级的代表队。',
		)
		self.assertEqual(
			expert_form.fields['member'].help_text,
			'请先选择具体赛项，再选择匹配层级的代表队。',
		)


class CompetitionAdminVisibilityTests(TestCase):
	def setUp(self):
		self.request = RequestFactory().get('/admin/')
		self.request.user = User.objects.create_superuser(
			username='admin-user',
			email='admin@example.com',
			password='testpass123',
		)

	def test_secondary_models_are_hidden_from_admin_index(self):
		hidden_models = (
			StandardModuleSet,
			CompetitionModuleStandardModuleMap,
			StandardModuleAxisMap,
			CompetitionModuleAxisMap,
			CompetitorUser,
			Competitor,
			Expert,
			SkillPosition,
		)

		for model in hidden_models:
			self.assertEqual(admin.site._registry[model].get_model_perms(self.request), {})

	def test_core_models_remain_visible_on_admin_index(self):
		visible_models = (
			CompetitionType,
			Competition,
			Project,
			StandardModule,
			ModuleAxis,
			CompetitionModule,
			CompetitionPerson,
			CompetitionProject,
			Member,
			CompetitionResult,
		)

		for model in visible_models:
			self.assertTrue(admin.site._registry[model].get_model_perms(self.request))

	def test_competition_project_admin_exposes_module_entry_link(self):
		competition_type = CompetitionType.objects.create(
			code='WSC-ADMIN',
			name='后台入口测试赛事',
		)
		project = Project.objects.create(
			code='ITNSA-ADMIN',
			name='后台入口测试项目',
		)
		competition = Competition.objects.create(
			competition_type=competition_type,
			name='第48届世界技能大赛',
			code='48WSC-ADMIN',
		)
		competition_project = CompetitionProject.objects.create(
			competition=competition,
			project=project,
		)
		CompetitionModule.objects.create(
			competition_project=competition_project,
			code='A',
			name='网络配置',
		)

		competition_project_admin = admin.site._registry[CompetitionProject]
		link_html = competition_project_admin.module_entry_link(competition_project)

		self.assertIn('进入具体赛项模块', link_html)
		self.assertIn('competition_project__id__exact={}'.format(competition_project.pk), link_html)
		self.assertIn('>进入具体赛项模块（1）<', link_html)

	def test_competition_module_admin_uses_module_fields_as_edit_links(self):
		competition_module_admin = admin.site._registry[CompetitionModule]

		self.assertEqual(
			competition_module_admin.get_list_display_links(self.request, competition_module_admin.list_display),
			('code', 'name'),
		)


class CompetitionFrontendViewTests(TestCase):
	def setUp(self):
		self.viewer = User.objects.create_user(username='viewer', password='testpass123')
		self.editor = User.objects.create_user(username='editor', password='testpass123')
		permissions = Permission.objects.filter(
			codename__in=['add_competitor', 'add_competitionresult', 'add_expert', 'add_skillposition'],
		)
		self.editor.user_permissions.add(*permissions)

		self.competition_type = CompetitionType.objects.create(
			code='WSC-FRONTEND',
			name='前台视图测试赛事',
			level=Level.INTERNATIONAL,
		)
		self.project = Project.objects.create(
			code='ITNSA-FRONTEND',
			name='前台视图测试项目',
		)
		self.module = StandardModule.objects.create(
			project=self.project,
			code='A',
			name='网络配置',
		)
		self.competition = Competition.objects.create(
			competition_type=self.competition_type,
			name='第47届世界技能大赛',
			code='WSC2024-FRONTEND',
		)
		self.competition_project = CompetitionProject.objects.create(
			competition=self.competition,
			project=self.project,
		)
		self.competition_module = CompetitionModule.objects.create(
			competition_project=self.competition_project,
			code='A',
			name='网络配置',
		)
		CompetitionModuleStandardModuleMap.objects.create(
			competition_module=self.competition_module,
			module=self.module,
			is_primary=True,
		)
		self.expert_person = CompetitionPerson.objects.create(
			name='专家甲',
			organization='专家单位',
		)
		self.staff_person = CompetitionPerson.objects.create(
			name='岗位甲',
			organization='岗位单位',
		)
		self.available_competitor_person = CompetitionPerson.objects.create(
			name='选手甲',
			organization='选手单位',
		)
		self.archived_competitor_person = CompetitionPerson.objects.create(
			name='选手乙',
			organization='选手单位',
		)
		self.country_member = Member.objects.create(
			name='中国',
			code='CN-FRONTEND',
			level=MemberScope.INTERNATIONAL,
		)
		self.province_member = Member.objects.create(
			name='浙江省',
			code='ZJ-FRONTEND',
			level=MemberScope.NATIONAL,
		)
		self.available_competitor = Competitor.objects.create(
			competition_project=self.competition_project,
			person=self.available_competitor_person,
			member=self.country_member,
		)
		self.archived_competitor = Competitor.objects.create(
			competition_project=self.competition_project,
			person=self.archived_competitor_person,
			member=self.country_member,
		)
		CompetitionResult.objects.create(
			competitor=self.archived_competitor,
			score_700='680.00',
			rank=2,
		)
		Expert.objects.create(
			competition_project=self.competition_project,
			person=self.expert_person,
			member=self.country_member,
		)
		SkillPosition.objects.create(
			competition_project=self.competition_project,
			person=self.staff_person,
			position_name='首席专家',
		)

	def test_competition_list_requires_login(self):
		response = self.client.get(reverse('competitions:competition_list'))

		self.assertEqual(response.status_code, 302)
		self.assertIn('/accounts/login/', response.url)

	def test_logged_in_user_can_view_competition_pages(self):
		self.client.force_login(self.viewer)

		list_response = self.client.get(reverse('competitions:competition_list'))
		detail_response = self.client.get(reverse('competitions:competition_detail', args=[self.competition.pk]))
		project_response = self.client.get(reverse('competitions:competitionproject_detail', args=[self.competition_project.pk]))

		self.assertEqual(list_response.status_code, 200)
		self.assertContains(list_response, '第47届世界技能大赛')
		self.assertEqual(detail_response.status_code, 200)
		self.assertContains(detail_response, '前台视图测试项目')
		self.assertEqual(project_response.status_code, 200)
		self.assertContains(project_response, '当前要求代表队层级')
		self.assertContains(project_response, '选手甲')
		self.assertContains(project_response, '专家甲')

	def test_competitor_create_requires_add_permission(self):
		self.client.force_login(self.viewer)

		response = self.client.get(
			reverse('competitions:competitor_create'),
			{'competition_project': self.competition_project.pk},
		)

		self.assertEqual(response.status_code, 403)

	def test_competitor_create_form_filters_members_by_level(self):
		self.client.force_login(self.editor)

		response = self.client.get(
			reverse('competitions:competitor_create'),
			{'competition_project': self.competition_project.pk},
		)

		self.assertEqual(response.status_code, 200)
		form = response.context['form']
		self.assertEqual(
			list(form.fields['member'].queryset.values_list('pk', flat=True)),
			[self.country_member.pk],
		)

	def test_competitor_create_page_uses_narrow_form_layout(self):
		self.client.force_login(self.editor)

		response = self.client.get(
			reverse('competitions:competitor_create'),
			{'competition_project': self.competition_project.pk},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'max-w-2xl')

	def test_competitionresult_create_form_only_shows_competitors_without_results(self):
		self.client.force_login(self.editor)

		response = self.client.get(
			reverse('competitions:competitionresult_create'),
			{'competition_project': self.competition_project.pk},
		)

		self.assertEqual(response.status_code, 200)
		form = response.context['form']
		self.assertEqual(
			list(form.fields['competitor'].queryset.values_list('pk', flat=True)),
			[self.available_competitor.pk],
		)

	def test_competitor_create_can_reuse_existing_person(self):
		self.client.force_login(self.editor)
		reusable_person = CompetitionPerson.objects.create(
			name='选手丙',
			organization='复用单位',
		)

		response = self.client.post(
			reverse('competitions:competitor_create'),
			{
				'competition_project': self.competition_project.pk,
				'person': reusable_person.pk,
				'member': self.country_member.pk,
				'gender': 'M',
			},
		)

		self.assertRedirects(
			response,
			reverse('competitions:competitionproject_detail', args=[self.competition_project.pk]),
		)
		self.assertTrue(
			Competitor.objects.filter(
				competition_project=self.competition_project,
				person=reusable_person,
				member=self.country_member,
				gender='M',
			).exists()
		)

	def test_competitor_create_can_create_new_person_inline(self):
		self.client.force_login(self.editor)

		response = self.client.post(
			reverse('competitions:competitor_create'),
			{
				'competition_project': self.competition_project.pk,
				'person': '',
				'new_person_name': '选手丙',
				'new_person_organization': '复用单位',
				'gender': 'F',
				'member': self.country_member.pk,
			},
		)

		self.assertRedirects(
			response,
			reverse('competitions:competitionproject_detail', args=[self.competition_project.pk]),
		)
		self.assertTrue(
			CompetitionPerson.objects.filter(name='选手丙', organization='复用单位').exists()
		)
		self.assertTrue(
			Competitor.objects.filter(
				competition_project=self.competition_project,
				person__name='选手丙',
				member=self.country_member,
				gender='F',
			).exists()
		)

	def test_expert_create_can_reuse_existing_person(self):
		self.client.force_login(self.editor)
		reusable_person = CompetitionPerson.objects.create(
			name='专家乙',
			organization='复用单位',
		)

		response = self.client.post(
			reverse('competitions:expert_create'),
			{
				'competition_project': self.competition_project.pk,
				'person': reusable_person.pk,
				'member': self.country_member.pk,
			},
		)

		self.assertRedirects(
			response,
			reverse('competitions:competitionproject_detail', args=[self.competition_project.pk]),
		)
		self.assertTrue(
			Expert.objects.filter(
				competition_project=self.competition_project,
				person=reusable_person,
				member=self.country_member,
			).exists()
		)

	def test_skillposition_create_can_create_new_person_inline(self):
		self.client.force_login(self.editor)

		response = self.client.post(
			reverse('competitions:skillposition_create'),
			{
				'competition_project': self.competition_project.pk,
				'person': '',
				'new_person_name': '岗位乙',
				'new_person_organization': '服务单位',
				'position_name': '场地经理',
				'remarks': '复用录入',
			},
		)

		self.assertRedirects(
			response,
			reverse('competitions:competitionproject_detail', args=[self.competition_project.pk]),
		)
		self.assertTrue(
			CompetitionPerson.objects.filter(name='岗位乙', organization='服务单位').exists()
		)
		self.assertTrue(
			SkillPosition.objects.filter(
				competition_project=self.competition_project,
				person__name='岗位乙',
				position_name='场地经理',
			).exists()
		)


class CompetitionReusableDataTests(TestCase):
	def setUp(self):
		self.international_type = CompetitionType.objects.create(
			code='WSC-REUSE',
			name='复用测试国际赛事',
			level=Level.INTERNATIONAL,
		)
		self.national_type = CompetitionType.objects.create(
			code='NSC-REUSE',
			name='复用测试国家赛事',
			level=Level.NATIONAL,
		)
		self.project = Project.objects.create(
			code='ITNSA-REUSE',
			name='可复用项目',
		)
		self.int_competition = Competition.objects.create(
			competition_type=self.international_type,
			name='国际赛',
			code='WSC2026-REUSE',
		)
		self.national_competition = Competition.objects.create(
			competition_type=self.national_type,
			name='国赛',
			code='NSC2026-REUSE',
		)
		self.int_project = CompetitionProject.objects.create(
			competition=self.int_competition,
			project=self.project,
		)
		self.national_project = CompetitionProject.objects.create(
			competition=self.national_competition,
			project=self.project,
		)

	def test_project_can_be_reused_across_competition_types(self):
		self.assertEqual(
			CompetitionProject.objects.filter(project=self.project).count(),
			2,
		)

	def test_competition_person_can_be_reused_for_experts_across_projects(self):
		person = CompetitionPerson.objects.create(name='复用专家', organization='专家库')
		international_member = Member.objects.create(
			name='中国队',
			code='CN-REUSE-INT',
			level=MemberScope.INTERNATIONAL,
		)
		national_member = Member.objects.create(
			name='浙江队',
			code='ZJ-REUSE-NAT',
			level=MemberScope.NATIONAL,
		)

		Expert.objects.create(
			competition_project=self.int_project,
			person=person,
			member=international_member,
		)
		Expert.objects.create(
			competition_project=self.national_project,
			person=person,
			member=national_member,
		)

		self.assertEqual(person.expert_assignments.count(), 2)

	def test_competition_person_can_be_reused_for_competitors_across_projects(self):
		person = CompetitionPerson.objects.create(name='复用选手', organization='选手库')
		international_member = Member.objects.create(
			name='中国队',
			code='CN-REUSE-COMP-INT',
			level=MemberScope.INTERNATIONAL,
		)
		national_member = Member.objects.create(
			name='浙江队',
			code='ZJ-REUSE-COMP-NAT',
			level=MemberScope.NATIONAL,
		)

		Competitor.objects.create(
			competition_project=self.int_project,
			person=person,
			member=international_member,
			gender='M',
		)
		Competitor.objects.create(
			competition_project=self.national_project,
			person=person,
			member=national_member,
			gender='M',
		)

		self.assertEqual(person.competitor_assignments.count(), 2)

	def test_competition_person_can_be_reused_for_skill_positions_across_projects(self):
		person = CompetitionPerson.objects.create(name='复用岗位人员', organization='服务保障中心')

		SkillPosition.objects.create(
			competition_project=self.int_project,
			person=person,
			position_name='首席专家',
		)
		SkillPosition.objects.create(
			competition_project=self.national_project,
			person=person,
			position_name='场地经理',
		)

		self.assertEqual(person.skill_position_assignments.count(), 2)


class CompetitionMenuConfigTests(TestCase):
	def test_assessment_section_is_renamed_and_includes_competitions(self):
		cache.clear()
		assessment_section = next(
			section for section in get_sections() if section.get('section') == 'assessment'
		)

		self.assertEqual(assessment_section['label'], '竞赛')
		self.assertIn('competitions', assessment_section['include'])
		self.assertEqual(assessment_section['include'][0], 'competitions')
		self.assertNotIn('competition', get_layout_sections('header_menu'))

	def test_assessment_section_menu_contains_competitions_entry(self):
		cache.clear()
		user = User.objects.create_user(username='menu-user', password='testpass123')

		menu_items = get_section_menu('assessment', user)
		group_names = [item.name for item in menu_items]

		self.assertIn('竞赛信息', group_names)
		self.assertEqual(group_names[0], '竞赛信息')
