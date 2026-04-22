from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase

from .admin import CompetitorAdminForm, ExpertAdminForm
from .models import (
	Competition,
	CompetitionModule,
	CompetitionModuleMapping,
	CompetitionProject,
	CompetitionResult,
	CompetitionType,
	Competitor,
	CompetitorUser,
	Expert,
	Level,
	Member,
	MemberScope,
	Module,
	ModuleSet,
	Project,
	SkillPosition,
)


User = get_user_model()


class ModuleSetVersioningTests(TestCase):
	def setUp(self):
		self.competition_type = CompetitionType.objects.create(
			code='WSC',
			name='世界技能大赛',
		)
		self.project = Project.objects.create(
			competition_type=self.competition_type,
			code='ITNSA',
			name='网络系统管理',
		)

	def test_module_without_module_set_uses_default_current_module_set(self):
		module = Module.objects.create(
			project=self.project,
			code='A',
			name='网络配置',
		)

		self.assertIsNotNone(module.module_set)
		self.assertTrue(module.module_set.is_current)
		self.assertEqual(self.project.current_module_set, module.module_set)
		self.assertEqual(self.project.module_sets.count(), 1)

	def test_switching_current_module_set_retires_previous_one(self):
		previous_module_set = self.project.get_or_create_default_module_set()

		next_module_set = ModuleSet.objects.create(
			project=self.project,
			code='2026',
			name='2026 版标准模块',
			is_current=True,
		)

		previous_module_set.refresh_from_db()
		self.assertFalse(previous_module_set.is_current)
		self.assertEqual(self.project.current_module_set, next_module_set)

	def test_same_module_code_can_exist_in_different_module_sets(self):
		default_module_set = self.project.get_or_create_default_module_set()
		historical_module_set = ModuleSet.objects.create(
			project=self.project,
			code='2024',
			name='2024 版标准模块',
			is_current=False,
		)

		Module.objects.create(
			project=self.project,
			module_set=historical_module_set,
			code='A',
			name='旧版网络配置',
		)
		current_module = Module.objects.create(
			project=self.project,
			module_set=default_module_set,
			code='A',
			name='新版网络配置',
		)

		self.assertEqual(Module.objects.filter(project=self.project, code='A').count(), 2)
		self.assertTrue(current_module.is_current)

	def test_module_set_must_belong_to_same_project(self):
		other_project = Project.objects.create(
			competition_type=self.competition_type,
			code='CLD',
			name='云计算',
		)
		other_module_set = ModuleSet.objects.create(
			project=other_project,
			code='default',
			name='默认标准模块集',
			is_current=True,
		)

		with self.assertRaises(ValidationError):
			Module.objects.create(
				project=self.project,
				module_set=other_module_set,
				code='B',
				name='错误模块',
			)


class CompetitionModuleMappingTests(TestCase):
	def setUp(self):
		self.competition_type = CompetitionType.objects.create(
			code='WSC-CM',
			name='模块映射测试赛事',
		)
		self.project = Project.objects.create(
			competition_type=self.competition_type,
			code='ITNSA-CM',
			name='模块映射测试项目',
		)
		self.module = Module.objects.create(
			project=self.project,
			code='A',
			name='网络配置',
		)
		self.second_module = Module.objects.create(
			project=self.project,
			code='B',
			name='服务部署',
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

	def create_competition_module(self, code='A', name='网络配置', primary_module=None):
		competition_module = CompetitionModule.objects.create(
			competition_project=self.competition_project,
			code=code,
			name=name,
		)
		if primary_module is not None:
			CompetitionModuleMapping.objects.create(
				competition_module=competition_module,
				module=primary_module,
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
		competition_module = self.create_competition_module(primary_module=self.module)

		self.assertEqual(competition_module.primary_module, self.module)
		mapping = competition_module.module_mappings.get(module=self.module)
		self.assertTrue(mapping.is_primary)

	def test_competition_module_falls_back_to_single_mapping_when_no_primary_exists(self):
		competition_module = self.create_competition_module(code='B', name='服务部署')
		CompetitionModuleMapping.objects.create(
			competition_module=competition_module,
			module=self.second_module,
			is_primary=False,
		)

		self.assertEqual(competition_module.primary_module, self.second_module)

	def test_competition_module_can_map_to_multiple_standard_modules(self):
		competition_module = self.create_competition_module(primary_module=self.module)
		CompetitionModuleMapping.objects.create(
			competition_module=competition_module,
			module=self.second_module,
			weight='0.40',
		)

		self.assertEqual(competition_module.module_mappings.count(), 2)
		self.assertCountEqual(
			competition_module.module_mappings.values_list('module__name', flat=True),
			['网络配置', '服务部署'],
		)

	def test_only_one_primary_mapping_is_allowed_per_competition_module(self):
		competition_module = self.create_competition_module(primary_module=self.module)
		duplicate_primary_mapping = CompetitionModuleMapping(
			competition_module=competition_module,
			module=self.second_module,
			is_primary=True,
		)

		with self.assertRaises(ValidationError) as context:
			duplicate_primary_mapping.full_clean()

		self.assertIn('is_primary', context.exception.message_dict)

	def test_mapping_module_must_match_competition_project_project(self):
		other_project = Project.objects.create(
			competition_type=self.competition_type,
			code='CLD-CM',
			name='其他项目',
		)
		other_module = Module.objects.create(
			project=other_project,
			code='Z',
			name='越界模块',
		)
		competition_module = self.create_competition_module(primary_module=self.module)

		with self.assertRaises(ValidationError):
			CompetitionModuleMapping.objects.create(
				competition_module=competition_module,
				module=other_module,
			)


class CompetitionArchiveIntegrityTests(TestCase):
	def setUp(self):
		self.competition_type = CompetitionType.objects.create(
			code='WSC-ARCHIVE',
			name='归档完整性测试赛事',
		)
		self.project = Project.objects.create(
			competition_type=self.competition_type,
			code='ITNSA-ARCHIVE',
			name='归档完整性测试项目',
		)
		self.module = Module.objects.create(
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
		CompetitionModuleMapping.objects.create(
			competition_module=self.competition_module,
			module=self.module,
			is_primary=True,
		)
		self.competitor = Competitor.objects.create(
			competition_project=self.competition_project,
			name='选手甲',
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
			name='未绑定赛项选手',
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
			competition_type=self.competition_type,
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

	def test_competitor_rejects_member_with_mismatched_level(self):
		competitor = Competitor(
			competition_project=self.competition_project,
			name='选手甲',
			member=self.province_member,
		)

		with self.assertRaises(ValidationError) as context:
			competitor.full_clean()

		self.assertIn('member', context.exception.message_dict)

	def test_expert_rejects_member_with_mismatched_level(self):
		expert = Expert(
			competition_project=self.competition_project,
			name='专家甲',
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
			ModuleSet,
			CompetitionModule,
			CompetitionModuleMapping,
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
			Module,
			CompetitionProject,
			Member,
			CompetitionResult,
		)

		for model in visible_models:
			self.assertTrue(admin.site._registry[model].get_model_perms(self.request))
