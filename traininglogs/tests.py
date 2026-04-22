import shutil
import tempfile
from datetime import date, timedelta
from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from core.constants import GROUP_COACH, GROUP_COMPETITOR
from competitions.models import CompetitionType, Project, StandardModule, StandardModuleSet

from .forms import TrainingLogCreateForm
from .models import TrainingLog


TEST_MEDIA_ROOT = Path(tempfile.mkdtemp())
User = get_user_model()


class TrainingLogCreateFormTestCase(TestCase):
	def setUp(self):
		competition_type = CompetitionType.objects.create(
			code='WSC',
			name='世界技能大赛',
		)
		self.project = Project.objects.create(
			code='ITNSA',
			name='网络系统管理',
		)
		StandardModule.objects.create(project=self.project, code='A', name='网络配置')
		StandardModule.objects.create(project=self.project, code='B', name='服务部署')

	def test_module_field_uses_radio_select_widget(self):
		form = TrainingLogCreateForm()
		module_field = form.fields['module']

		self.assertIsInstance(module_field.widget, forms.RadioSelect)
		self.assertTrue(module_field.required)
		self.assertIsNone(module_field.empty_label)
		self.assertEqual(module_field.widget.attrs['class'], 'radio radio-primary')
		self.assertEqual(
			[choice.choice_label for choice in form['module']],
			['A - 网络配置', 'B - 服务部署'],
		)

	def test_module_field_only_lists_current_standard_module_set_modules(self):
		current_standard_module_set = self.project.current_standard_module_set
		historical_module_set = StandardModuleSet.objects.create(
			project=self.project,
			code='2024',
			name='2024 版标准模块',
			is_current=False,
		)
		StandardModule.objects.create(
			project=self.project,
			module_set=historical_module_set,
			code='C',
			name='历史模块',
		)

		form = TrainingLogCreateForm()

		self.assertIsNotNone(current_standard_module_set)
		self.assertEqual(
			[choice.choice_label for choice in form['module']],
			['A - 网络配置', 'B - 服务部署'],
		)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class TrainingLogDuplicateValidationTestCase(TestCase):
	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

	def setUp(self):
		competition_type = CompetitionType.objects.create(
			code='WSC-DUP',
			name='重复校验赛事',
		)
		project = Project.objects.create(
			code='ITNSA-DUP',
			name='重复校验项目',
		)
		self.module = StandardModule.objects.create(project=project, code='A', name='网络配置')

		self.user = User.objects.create_user(username='coach-dup', password='testpass123')
		self.other_user = User.objects.create_user(username='coach-other', password='testpass123')
		add_permission = Permission.objects.get(codename='add_traininglog')
		self.user.user_permissions.add(add_permission)
		self.other_user.user_permissions.add(add_permission)

		today = timezone.localdate()
		self.training_date = date(today.year, today.month, min(today.day, 28))
		self.existing_log = TrainingLog.objects.create(
			module=self.module,
			task='已有日志',
			training_date=self.training_date,
			file=self._build_upload_file('existing.pdf'),
			uploaded_by=self.user,
		)

	def _build_upload_file(self, name='sample.pdf'):
		return SimpleUploadedFile(name, b'%PDF-1.4 training log', content_type='application/pdf')

	def test_form_rejects_duplicate_training_log_for_same_user_and_date(self):
		form = TrainingLogCreateForm(
			data={
				'training_date': self.training_date.isoformat(),
				'module': self.module.pk,
				'task': '重复日志',
			},
			files={'file': self._build_upload_file('duplicate.pdf')},
			user=self.user,
		)

		self.assertFalse(form.is_valid())
		self.assertIn('training_date', form.errors)
		self.assertEqual(len(form.errors['training_date']), 1)
		self.assertIn('同一训练日期只能上传一条训练日志', form.errors['training_date'][0])

	def test_form_allows_same_user_on_different_date(self):
		other_date = self.training_date - timedelta(days=1)
		form = TrainingLogCreateForm(
			data={
				'training_date': other_date.isoformat(),
				'module': self.module.pk,
				'task': '新日期日志',
			},
			files={'file': self._build_upload_file('another-day.pdf')},
			user=self.user,
		)

		self.assertTrue(form.is_valid(), form.errors)

	def test_model_clean_rejects_duplicate_training_log_for_same_user_and_date(self):
		duplicate_log = TrainingLog(
			module=self.module,
			task='模型重复日志',
			training_date=self.training_date,
			file=self._build_upload_file('model-duplicate.pdf'),
			uploaded_by=self.user,
		)

		with self.assertRaises(ValidationError) as exc_info:
			duplicate_log.clean()

		self.assertIn('training_date', exc_info.exception.message_dict)

	def test_same_date_is_allowed_for_different_user(self):
		other_log = TrainingLog.objects.create(
			module=self.module,
			task='其他人的日志',
			training_date=self.training_date,
			file=self._build_upload_file('other-user.pdf'),
			uploaded_by=self.other_user,
		)

		self.assertIsNotNone(other_log.pk)
		self.assertEqual(
			TrainingLog.objects.filter(training_date=self.training_date).count(),
			2,
		)

	def test_upload_view_rejects_duplicate_training_log(self):
		self.client.force_login(self.user)

		response = self.client.post(
			reverse('traininglogs:traininglog_upload'),
			{
				'training_date': self.training_date.isoformat(),
				'module': self.module.pk,
				'task': '重复上传',
				'file': self._build_upload_file('view-duplicate.pdf'),
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, '同一训练日期只能上传一条训练日志')
		self.assertEqual(
			TrainingLog.objects.filter(uploaded_by=self.user, training_date=self.training_date).count(),
			1,
		)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class TrainingLogListViewTestCase(TestCase):
	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

	def setUp(self):
		competition_type = CompetitionType.objects.create(
			code='WSC-LIST',
			name='列表测试赛事',
		)
		project = Project.objects.create(
			code='ITNSA-LIST',
			name='列表测试项目',
		)
		self.module = StandardModule.objects.create(project=project, code='M1', name='模块一')

		self.superuser = User.objects.create_superuser(
			username='admin',
			email='admin@example.com',
			password='testpass123',
		)
		self.client.force_login(self.superuser)

		coach_group = Group.objects.create(name=GROUP_COACH)
		competitor_group = Group.objects.create(name=GROUP_COMPETITOR)

		self.coach_user = User.objects.create_user(username='coach1', password='testpass123')
		self.coach_user.groups.add(coach_group)

		self.competitor_user = User.objects.create_user(username='competitor1', password='testpass123')
		self.competitor_user.groups.add(competitor_group)

		today = timezone.localdate()
		self.current_month_date = date(today.year, today.month, 10)
		prev_year = today.year if today.month > 1 else today.year - 1
		prev_month = today.month - 1 or 12
		self.previous_month_date = date(prev_year, prev_month, 10)

		self.current_coach_log = self._create_traininglog(
			user=self.coach_user,
			training_date=self.current_month_date,
			suffix='coach-current',
		)
		self.previous_coach_log = self._create_traininglog(
			user=self.coach_user,
			training_date=self.previous_month_date,
			suffix='coach-previous',
		)
		self.current_competitor_log = self._create_traininglog(
			user=self.competitor_user,
			training_date=self.current_month_date,
			suffix='competitor-current',
		)
		self.previous_competitor_log = self._create_traininglog(
			user=self.competitor_user,
			training_date=self.previous_month_date,
			suffix='competitor-previous',
		)

	def _create_traininglog(self, user, training_date, suffix):
		return TrainingLog.objects.create(
			module=self.module,
			task=f'任务-{suffix}',
			training_date=training_date,
			file=SimpleUploadedFile(
				f'{suffix}.pdf',
				b'%PDF-1.4 test file',
				content_type='application/pdf',
			),
			uploaded_by=user,
		)

	def test_coach_list_defaults_to_current_month(self):
		response = self.client.get(reverse('traininglogs:traininglog_coach_list'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'id="month-select"')
		self.assertEqual(list(response.context['object_list']), [self.current_coach_log])
		self.assertEqual(response.context['selected_year'], self.current_month_date.year)
		self.assertEqual(response.context['selected_month'], self.current_month_date.month)
		self.assertEqual(len(response.context['months']), 12)
		self.assertNotContains(response, self.current_competitor_log.task)

	def test_coach_list_can_filter_specific_month(self):
		response = self.client.get(
			reverse('traininglogs:traininglog_coach_list'),
			{'year': self.previous_month_date.year, 'month': self.previous_month_date.month},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context['object_list']), [self.previous_coach_log])
		self.assertEqual(response.context['selected_year'], self.previous_month_date.year)
		self.assertEqual(response.context['selected_month'], self.previous_month_date.month)

	def test_competitor_list_defaults_to_current_month(self):
		response = self.client.get(reverse('traininglogs:traininglog_competitor_list'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context['object_list']), [self.current_competitor_log])
		self.assertNotContains(response, self.current_coach_log.task)

	def test_my_list_defaults_to_current_month_for_current_user(self):
		self.client.force_login(self.coach_user)
		response = self.client.get(reverse('traininglogs:traininglog_list'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'id="month-select"')
		self.assertEqual(list(response.context['object_list']), [self.current_coach_log])
		self.assertEqual(response.context['selected_year'], self.current_month_date.year)
		self.assertEqual(response.context['selected_month'], self.current_month_date.month)
		self.assertEqual(len(response.context['months']), 12)
		self.assertNotContains(response, self.current_competitor_log.task)

	def test_my_list_can_filter_specific_month_for_current_user(self):
		self.client.force_login(self.coach_user)
		response = self.client.get(
			reverse('traininglogs:traininglog_list'),
			{'year': self.previous_month_date.year, 'month': self.previous_month_date.month},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context['object_list']), [self.previous_coach_log])
		self.assertEqual(response.context['selected_year'], self.previous_month_date.year)
		self.assertEqual(response.context['selected_month'], self.previous_month_date.month)
