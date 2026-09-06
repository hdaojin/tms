from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from assessments.models import Assessment, AssessmentModule, AssessmentType
from notes.models import NoteRepo
from scoring.models import ScoringScheme
from standards.models import Skill, SkillProject, SkillTreeVersion, TechnicalDomain, WSOSVersion
from training.models import TrainingCycle, TrainingPlan


class BreadcrumbPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(username='breadcrumb-admin')
        cls.project = SkillProject.objects.create(code='BC', name='网络系统管理')
        cls.domain = TechnicalDomain.objects.create(skill_project=cls.project, code='LINUX', name='Linux')
        cls.tree = SkillTreeVersion.objects.create(
            technical_domain=cls.domain,
            version='2026',
            name='技能树 2026',
            is_current=True,
        )
        cls.assessment = Assessment.objects.create(
            skill_project=cls.project,
            code='BC',
            name='第48届世界技能大赛',
            assessment_type=AssessmentType.objects.create(code='bc', name='竞赛'),
            start_date=date(2026, 9, 1),
            created_by=cls.admin,
        )
        cls.module = AssessmentModule.objects.create(assessment=cls.assessment, code='A', name='Module A')
        cls.scheme = ScoringScheme.objects.create(
            assessment_module=cls.module,
            title='评分方案',
            module_code='A',
            module_name='Module A',
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def assert_breadcrumbs(self, response, labels):
        self.assertEqual(response.status_code, 200)
        crumbs = list(response.context['breadcrumbs'])
        self.assertEqual([c.label for c in crumbs], labels)
        self.assertIsNone(crumbs[-1].url)
        soup = BeautifulSoup(response.content, 'html.parser')
        navs = soup.select('nav[aria-label="面包屑"]')
        self.assertEqual(len(navs), 1)
        self.assertEqual(navs[0].select_one('[aria-current="page"]').text.strip(), labels[-1])
        self.assertIsNone(navs[0].select('li')[-1].find('a'))
        return crumbs

    def test_training_cycle_plan_and_create(self):
        cycle = TrainingCycle.objects.create(
            skill_project=self.project,
            code='BC',
            name='2026 世赛冲刺周期',
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )
        plan = TrainingPlan.objects.create(
            training_cycle=cycle,
            title='九月训练计划',
            objective='训练',
            created_by=self.admin,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )
        for name, args, labels in [
            ('cycle_list', [], ['训练周期']),
            ('cycle_detail', [cycle.pk], ['训练周期', cycle.name]),
            ('plan_detail', [plan.pk], ['训练计划', plan.title]),
            ('plan_create', [], ['训练计划', '新增训练计划']),
        ]:
            with self.subTest(page=name):
                self.assert_breadcrumbs(
                    self.client.get(reverse(f'training:{name}', args=args)), ['首页', '训练', *labels]
                )

    def test_assessment_tabs_module_and_scheme(self):
        url = reverse('assessments:assessment_detail', args=[self.assessment.pk])
        for tab in ['', '?tab=modules', '?tab=documents', '?tab=not-a-tab']:
            self.assert_breadcrumbs(self.client.get(url + tab), ['首页', '竞赛与考核', self.assessment.name])
        self.assert_breadcrumbs(
            self.client.get(reverse('assessments:module_detail', args=[self.module.pk])),
            ['首页', '竞赛与考核', self.assessment.name, self.module.name],
        )
        self.assert_breadcrumbs(
            self.client.get(reverse('scoring:scheme_detail', args=[self.scheme.pk])),
            ['首页', '竞赛与考核', self.assessment.name, self.module.name, '评分方案'],
        )

    def test_standards_real_domain_tree_skill_and_wsos(self):
        prefix = ['首页', '标准', '技能项目', self.project.name]
        self.assert_breadcrumbs(self.client.get(reverse('standards:project_detail', args=[self.project.pk])), prefix)
        url = reverse('standards:current_domain_tree', args=[self.project.pk, self.domain.pk])
        self.assert_breadcrumbs(self.client.get(url), [*prefix, 'Linux', 'Linux当前技能树'])
        self.assert_breadcrumbs(
            self.client.get(reverse('standards:tree_detail', args=[self.tree.pk])),
            [*prefix, 'Linux', self.tree.name],
        )
        skill = Skill.objects.create(skill_project=self.project, primary_domain=self.domain, name='DHCP 服务')
        self.assert_breadcrumbs(
            self.client.get(reverse('standards:skill_detail', args=[skill.pk])),
            [*prefix, 'Linux', skill.name],
        )
        self.tree.is_current = False
        self.tree.save()
        self.assert_breadcrumbs(self.client.get(url), [*prefix, 'Linux', 'Linux当前技能树'])
        wsos = WSOSVersion.objects.create(skill_project=self.project, code='BC', name='WSOS 2026')
        self.assert_breadcrumbs(
            self.client.get(reverse('standards:wsos_detail', args=[wsos.pk])),
            ['首页', '标准', 'WSOS', wsos.name],
        )

    def test_scoring_permission_does_not_grant_assessment_or_module_visibility(self):
        user = get_user_model().objects.create_user(username='breadcrumb-scorer')
        user.user_permissions.add(Permission.objects.get(codename='view_scoringscheme'))
        self.assessment.created_by = user
        self.assessment.save()
        self.client.force_login(user)
        crumbs = self.assert_breadcrumbs(
            self.client.get(reverse('scoring:scheme_detail', args=[self.scheme.pk])),
            ['首页', '评分方案'],
        )
        self.assertNotIn(self.assessment.name, [c.label for c in crumbs])
        self.assertEqual(self.client.get(reverse('assessments:module_detail', args=[self.module.pk])).status_code, 403)
        user.user_permissions.add(Permission.objects.get(codename='view_assessment'))
        self.assert_breadcrumbs(
            self.client.get(reverse('scoring:scheme_detail', args=[self.scheme.pk])),
            ['首页', '竞赛与考核', self.assessment.name, '评分方案'],
        )

    def test_module_scope_denies_other_assessment(self):
        user = get_user_model().objects.create_user(username='breadcrumb-outsider')
        user.user_permissions.add(Permission.objects.get(codename='view_assessmentmodule'))
        self.client.force_login(user)
        response = self.client.get(reverse('assessments:module_detail', args=[self.module.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, self.assessment.name, status_code=404)

    def test_notes_single_breadcrumb_and_denied_repo(self):
        with TemporaryDirectory() as directory, self.settings(NOTES_ROOT=directory):
            root = Path(directory) / 'debian'
            root.mkdir()
            (root / 'README.md').write_text('# Debian\n\n- [DHCP 服务](dhcp.md)\n', encoding='utf-8')
            (root / 'dhcp.md').write_text('---\ntask: DHCP 服务\n---\n# DHCP\n', encoding='utf-8')
            repo = NoteRepo.objects.create(slug='debian', relative_path='debian', title='Debian 教学讲义')
            url = reverse('notes:note_detail', kwargs={'repo': repo.slug, 'slug': 'dhcp'})
            response = self.client.get(url)
            self.assert_breadcrumbs(response, ['首页', '资料', '笔记仓库', repo.title, 'DHCP 服务'])
            self.assertEqual(len(BeautifulSoup(response.content, 'html.parser').select('.breadcrumbs')), 1)
            self.assert_breadcrumbs(
                self.client.get(reverse('notes:note_repo_index', kwargs={'repo': repo.slug})),
                ['首页', '资料', '笔记仓库', repo.title, 'README'],
            )
            user = get_user_model().objects.create_user(username='breadcrumb-notes-denied')
            user.user_permissions.add(Permission.objects.get(codename='view_noterepo'))
            repo.allowed_groups.add(Group.objects.create(name='私有笔记组'))
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
            self.assertNotContains(response, repo.title, status_code=403)
