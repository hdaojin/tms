from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from competitions.models import (
	Competition,
	CompetitionModule,
	CompetitionModuleStandardModuleMap,
	CompetitionProject,
)
from competition_standards.models import (
	CompetitionType,
	Project,
	StandardModule,
	StandardModuleSet,
)
from skills.models import ExamPoint, ExamPointSkill, Skill, Tag, TagGroup, Topic


User = get_user_model()


class ExamPointModelTests(TestCase):
	def setUp(self):
		self.competition_type = CompetitionType.objects.create(
			code='WSC',
			name='世界技能大赛',
		)
		self.project = Project.objects.create(
			competition_type=self.competition_type,
			code='ITNSA',
			name='信息网络布线',
		)
		self.second_project = Project.objects.create(
			competition_type=self.competition_type,
			code='CLD',
			name='云计算',
		)
		self.competition = Competition.objects.create(
			competition_type=self.competition_type,
			name='第47届世界技能大赛',
			code='WSC2024',
		)
		self.competition_project = CompetitionProject.objects.create(
			competition=self.competition,
			project=self.project,
		)
		self.second_competition_project = CompetitionProject.objects.create(
			competition=self.competition,
			project=self.second_project,
		)
		self.module = StandardModule.objects.create(
			project=self.project,
			code='M1',
			name='网络模块',
		)
		self.topic = Topic.objects.create(module=self.module, name='网络基础')
		self.skill = Skill.objects.create(topic=self.topic, name='交换与路由')
		self.auth_topic = Topic.objects.create(module=self.module, name='认证服务')
		self.auth_skill = Skill.objects.create(topic=self.auth_topic, name='LDAP 认证接入')
		self.tag_group = TagGroup.objects.create(name='技术组件', slug='component')
		self.tag = Tag.objects.create(group=self.tag_group, name='openvpn', slug='openvpn')

	def build_exam_point(self, **kwargs):
		defaults = {
			'competition_project': self.competition_project,
			'name': '网络配置考点',
			'difficulty': 3,
			'score': 10,
		}
		defaults.update(kwargs)
		return ExamPoint(**defaults)

	def test_name_is_required(self):
		exam_point = self.build_exam_point(name='')

		with self.assertRaises(ValidationError) as context:
			exam_point.full_clean()

		self.assertIn('name', context.exception.message_dict)

	def test_difficulty_must_be_between_1_and_5(self):
		for difficulty in (0, 6):
			exam_point = self.build_exam_point(
				name=f'非法难度-{difficulty}',
				difficulty=difficulty,
			)

			with self.assertRaises(ValidationError) as context:
				exam_point.full_clean()

			self.assertIn('difficulty', context.exception.message_dict)

		for difficulty in (1, 5):
			exam_point = self.build_exam_point(
				name=f'合法难度-{difficulty}',
				difficulty=difficulty,
			)
			exam_point.full_clean()

	def test_skill_alias_returns_skills_manager(self):
		exam_point = self.build_exam_point()
		exam_point.full_clean()
		exam_point.save()
		ExamPointSkill.objects.create(exam_point=exam_point, skill=self.skill, is_primary=True)

		self.assertEqual(list(exam_point.skills.all()), [self.skill])
		self.assertEqual(list(exam_point.skill.all()), [self.skill])

	def test_topic_uses_competitions_module(self):
		self.assertEqual(self.topic.module, self.module)
		self.assertEqual(self.topic.module.project, self.project)

	def test_exam_point_can_reuse_same_name_under_other_competition_project(self):
		ExamPoint.objects.create(
			competition_project=self.competition_project,
			name='同名考点',
			difficulty=3,
			score='8.00',
		)
		other_exam_point = ExamPoint.objects.create(
			competition_project=self.second_competition_project,
			name='同名考点',
			difficulty=4,
			score='9.00',
		)

		self.assertEqual(other_exam_point.competition, self.competition)
		self.assertEqual(ExamPoint.objects.filter(name='同名考点').count(), 2)

	def test_exam_point_skill_stores_primary_and_weight(self):
		exam_point = ExamPoint.objects.create(
			competition_project=self.competition_project,
			name='综合考点',
			difficulty=4,
			score='15.00',
		)
		relation = ExamPointSkill.objects.create(
			exam_point=exam_point,
			skill=self.auth_skill,
			is_primary=True,
			weight='0.75',
			note='主考认证能力',
		)

		self.assertTrue(relation.is_primary)
		self.assertEqual(str(relation.weight), '0.75')
		self.assertEqual(relation.note, '主考认证能力')

	def test_exam_point_supports_controlled_tags(self):
		exam_point = ExamPoint.objects.create(
			competition_project=self.competition_project,
			name='带标签考点',
			difficulty=2,
			score='5.00',
		)
		exam_point.tags.add(self.tag)

		self.assertEqual(list(exam_point.tags.all()), [self.tag])
		self.assertEqual(self.tag.group, self.tag_group)


class SkillListViewTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='skill-user', password='testpass123')
		competition_type = CompetitionType.objects.create(
			code='WSC',
			name='世界技能大赛',
		)
		project = Project.objects.create(
			competition_type=competition_type,
			code='ITNSA',
			name='信息网络布线',
		)
		other_project = Project.objects.create(
			competition_type=competition_type,
			code='CLD',
			name='云计算',
		)
		self.module_a = StandardModule.objects.create(project=project, code='M1', name='网络模块')
		self.module_b = StandardModule.objects.create(project=other_project, code='M2', name='云平台模块')
		topic_a = Topic.objects.create(module=self.module_a, name='网络基础')
		topic_b = Topic.objects.create(module=self.module_b, name='系统部署')
		self.skill_a = Skill.objects.create(topic=topic_a, name='交换与路由', description='网络配置技能')
		self.skill_b = Skill.objects.create(topic=topic_b, name='容器编排', description='集群管理技能')

	def test_skill_list_view_renders_module_filter(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('skills:skill_list'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '标准模块')
		self.assertContains(response, self.skill_a.name)
		self.assertContains(response, self.skill_b.name)
		self.assertContains(response, '录入考点')

	def test_skill_list_view_filters_by_module(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('skills:skill_list'), {'module': self.module_a.pk})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.skill_a.name)
		self.assertNotContains(response, self.skill_b.name)

	def test_skill_list_view_filters_by_keyword(self):
		self.client.force_login(self.user)

		response = self.client.get(reverse('skills:skill_list'), {'keyword': '容器'})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.skill_b.name)
		self.assertNotContains(response, self.skill_a.name)


class ExamPointCreateViewTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='exam-point-user', password='testpass123')
		self.competition_type = CompetitionType.objects.create(
			code='WSC',
			name='世界技能大赛',
		)
		self.competition = Competition.objects.create(
			competition_type=self.competition_type,
			name='第47届世界技能大赛',
			code='WSC2024',
		)
		self.other_competition = Competition.objects.create(
			competition_type=self.competition_type,
			name='第48届世界技能大赛',
			code='WSC2026',
		)
		self.project = Project.objects.create(
			competition_type=self.competition_type,
			code='ITNSA',
			name='信息网络布线',
		)
		self.second_project = Project.objects.create(
			competition_type=self.competition_type,
			code='NSAUX',
			name='网络系统辅助项目',
		)
		self.other_project = Project.objects.create(
			competition_type=self.competition_type,
			code='CLD',
			name='云计算',
		)
		self.competition_project = CompetitionProject.objects.create(
			competition=self.competition,
			project=self.project,
		)
		self.second_competition_project = CompetitionProject.objects.create(
			competition=self.competition,
			project=self.second_project,
		)
		self.other_competition_project = CompetitionProject.objects.create(
			competition=self.other_competition,
			project=self.other_project,
		)
		self.module = StandardModule.objects.create(project=self.project, code='M1', name='网络模块')
		self.second_module = StandardModule.objects.create(project=self.project, code='M2', name='服务模块')
		self.same_competition_other_project_module = StandardModule.objects.create(
			project=self.second_project,
			code='M9',
			name='辅助模块',
		)
		self.other_module = StandardModule.objects.create(project=self.other_project, code='M3', name='离线模块')
		self.official_module = CompetitionModule.objects.create(
			competition_project=self.competition_project,
			code=self.module.code,
			name=self.module.name,
		)
		CompetitionModuleStandardModuleMap.objects.create(
			competition_module=self.official_module,
			module=self.module,
			is_primary=True,
		)
		self.second_official_module = CompetitionModule.objects.create(
			competition_project=self.competition_project,
			code=self.second_module.code,
			name=self.second_module.name,
		)
		CompetitionModuleStandardModuleMap.objects.create(
			competition_module=self.second_official_module,
			module=self.second_module,
			is_primary=True,
		)
		self.secondary_project_official_module = CompetitionModule.objects.create(
			competition_project=self.second_competition_project,
			code=self.same_competition_other_project_module.code,
			name=self.same_competition_other_project_module.name,
		)
		CompetitionModuleStandardModuleMap.objects.create(
			competition_module=self.secondary_project_official_module,
			module=self.same_competition_other_project_module,
			is_primary=True,
		)
		self.other_official_module = CompetitionModule.objects.create(
			competition_project=self.other_competition_project,
			code=self.other_module.code,
			name=self.other_module.name,
		)
		CompetitionModuleStandardModuleMap.objects.create(
			competition_module=self.other_official_module,
			module=self.other_module,
			is_primary=True,
		)

		self.topic = Topic.objects.create(module=self.module, name='网络基础')
		self.auth_topic = Topic.objects.create(module=self.module, name='认证服务')
		self.skill = Skill.objects.create(topic=self.topic, name='交换与路由')
		self.auth_skill = Skill.objects.create(topic=self.auth_topic, name='LDAP 认证接入')
		self.other_skill = Skill.objects.create(topic=self.topic, name='网络安全')
		self.other_project_topic = Topic.objects.create(module=self.same_competition_other_project_module, name='外部专题')
		self.other_project_skill = Skill.objects.create(topic=self.other_project_topic, name='其他项目技能')
		self.existing_exam_point = ExamPoint.objects.create(
			competition_project=self.competition_project,
			name='已有考点',
			difficulty=3,
			score='12.00',
		)
		ExamPointSkill.objects.create(exam_point=self.existing_exam_point, skill=self.skill, is_primary=True)
		self.other_project_exam_point = ExamPoint.objects.create(
			competition_project=self.second_competition_project,
			name='已有考点-其他项目',
			difficulty=2,
			score='7.00',
		)
		ExamPointSkill.objects.create(exam_point=self.other_project_exam_point, skill=self.other_project_skill, is_primary=True)

		self.create_url = reverse('skills:exam_point_create')
		self.dependency_url = reverse('skills:exam_point_dependency_fields')
		self.topic_suggestion_url = reverse('skills:exam_point_topic_suggestions')
		self.name_suggestion_url = reverse('skills:exam_point_name_suggestions')

	def login(self):
		self.client.force_login(self.user)

	def test_create_view_renders_relationship_help(self):
		self.login()

		response = self.client.get(self.create_url)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '关系说明')
		self.assertContains(response, '可跨同一模块下多个专题复用已有技能点')
		self.assertContains(response, '保存考点')

	def test_dependency_endpoint_returns_only_modules_of_selected_competition_project(self):
		self.login()

		response = self.client.get(self.dependency_url, {'competition_project': self.competition_project.pk})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, f'{self.module.code} - {self.module.name}')
		self.assertContains(response, f'{self.second_module.code} - {self.second_module.name}')
		self.assertNotContains(response, self.same_competition_other_project_module.name)
		self.assertNotContains(response, self.other_module.name)

	def test_dependency_endpoint_uses_current_module_mappings_only(self):
		self.login()
		self.official_module.module_mappings.filter(module=self.module).update(is_primary=False)
		new_module_set = StandardModuleSet.objects.create(
			project=self.project,
			code='2026',
			name='2026 版标准模块',
			is_current=True,
		)
		replacement_module = StandardModule.objects.create(
			project=self.project,
			module_set=new_module_set,
			code='NM1',
			name='新网络模块',
		)
		CompetitionModuleStandardModuleMap.objects.create(
			competition_module=self.official_module,
			module=replacement_module,
			is_primary=True,
			weight='1.00',
		)

		response = self.client.get(self.dependency_url, {'competition_project': self.competition_project.pk})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, f'{replacement_module.code} - {replacement_module.name}')
		self.assertNotContains(response, f'{self.module.code} - {self.module.name}')
		self.assertNotContains(response, f'{self.second_module.code} - {self.second_module.name}')

	def test_topic_suggestion_endpoint_lists_existing_topics(self):
		self.login()

		response = self.client.get(
			self.topic_suggestion_url,
			{
				'competition_project': self.competition_project.pk,
				'module': self.module.pk,
				'new_topic_name': '网络',
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.topic.name)

	def test_name_suggestion_endpoint_lists_existing_exam_points_within_competition_project(self):
		self.login()

		response = self.client.get(
			self.name_suggestion_url,
			{'competition_project': self.competition_project.pk, 'name': '已有'},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.existing_exam_point.name)
		self.assertNotContains(response, self.other_project_exam_point.name)
		self.assertContains(response, self.skill.name)

	def test_create_view_reuses_existing_topic_and_skill_when_names_match(self):
		self.login()

		response = self.client.post(
			self.create_url,
			{
				'competition_project': self.competition_project.pk,
				'module': self.module.pk,
				'topic_mode': 'new',
				'new_topic_name': self.topic.name,
				'new_topic_description': '不会重复创建专题',
				'name': '新考点-复用',
				'detail_content': '复用已有专题和技能',
				'difficulty': 4,
				'score': '15.00',
				'new_skill_names': [self.skill.name],
			},
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(Topic.objects.filter(module=self.module, name=self.topic.name).count(), 1)
		self.assertEqual(Skill.objects.filter(topic=self.topic, name=self.skill.name).count(), 1)
		exam_point = ExamPoint.objects.get(name='新考点-复用')
		self.assertEqual(list(exam_point.skills.all()), [self.skill])
		self.assertTrue(exam_point.exam_point_skills.get(skill=self.skill).is_primary)

	def test_create_view_allows_existing_skills_across_topics_within_same_module(self):
		self.login()

		response = self.client.post(
			self.create_url,
			{
				'competition_project': self.competition_project.pk,
				'module': self.module.pk,
				'topic_mode': 'existing',
				'name': '新考点-综合技能',
				'detail_content': '跨多个专题复用已有技能点',
				'difficulty': 4,
				'score': '18.00',
				'existing_skills': [self.skill.pk, self.auth_skill.pk],
				'new_skill_names': [''],
			},
		)

		self.assertEqual(response.status_code, 302)
		exam_point = ExamPoint.objects.get(name='新考点-综合技能')
		self.assertCountEqual(
			exam_point.skills.values_list('name', flat=True),
			[self.skill.name, self.auth_skill.name],
		)
		self.assertFalse(exam_point.exam_point_skills.filter(is_primary=True).exists())

	def test_create_view_combines_existing_and_new_skills_under_selected_topic(self):
		self.login()

		response = self.client.post(
			self.create_url,
			{
				'competition_project': self.competition_project.pk,
				'module': self.module.pk,
				'topic_mode': 'existing',
				'existing_topic': self.auth_topic.pk,
				'existing_skills': [self.skill.pk],
				'name': '新考点-混合技能',
				'detail_content': '同时复用和新增技能点',
				'difficulty': 5,
				'score': '20.00',
				'new_skill_names': ['用户目录同步'],
			},
		)

		self.assertEqual(response.status_code, 302)
		new_skill = Skill.objects.get(topic=self.auth_topic, name='用户目录同步')
		exam_point = ExamPoint.objects.get(name='新考点-混合技能')
		self.assertCountEqual(exam_point.skills.values_list('name', flat=True), [self.skill.name, new_skill.name])

	def test_create_view_rejects_duplicate_exam_point_name_in_same_competition_project(self):
		self.login()

		response = self.client.post(
			self.create_url,
			{
				'competition_project': self.competition_project.pk,
				'module': self.module.pk,
				'topic_mode': 'existing',
				'existing_skills': [self.skill.pk],
				'name': self.existing_exam_point.name,
				'detail_content': '重复考点',
				'difficulty': 3,
				'score': '9.00',
				'new_skill_names': [''],
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '当前具体赛项下已存在同名考点')
		self.assertEqual(
			ExamPoint.objects.filter(
				competition_project=self.competition_project,
				name=self.existing_exam_point.name,
			).count(),
			1,
		)

	def test_create_view_rejects_module_outside_selected_competition_project(self):
		self.login()

		response = self.client.post(
			self.create_url,
			{
				'competition_project': self.competition_project.pk,
				'module': self.other_module.pk,
				'topic_mode': 'new',
				'new_topic_name': '错误模块专题',
				'name': '越界考点',
				'detail_content': '不应允许提交',
				'difficulty': 3,
				'score': '6.00',
				'new_skill_names': ['新技能'],
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '选择一个有效的选项')
		self.assertFalse(ExamPoint.objects.filter(name='越界考点').exists())
