from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from decimal import Decimal

from core.constants import GROUP_COMPETITOR
from .models import ConductType, ConductRecord, ConductSummary


User = get_user_model()


class ConductTypeTestCase(TestCase):
    """奖惩类型测试"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    def test_create_reward_type(self):
        """测试创建奖励类型"""
        conduct_type = ConductType.objects.create(
            name='优秀作业',
            category='REWARD',
            score=Decimal('5.0'),
            created_by=self.user
        )
        self.assertEqual(conduct_type.name, '优秀作业')
        self.assertEqual(conduct_type.category, 'REWARD')
        self.assertTrue(conduct_type.score > 0)
    
    def test_create_penalty_type(self):
        """测试创建惩罚类型"""
        conduct_type = ConductType.objects.create(
            name='迟到',
            category='PENALTY',
            score=Decimal('-3.0'),
            created_by=self.user
        )
        self.assertEqual(conduct_type.category, 'PENALTY')
        self.assertTrue(conduct_type.score < 0)


class ConductRecordTestCase(TestCase):
    """奖惩记录测试"""
    
    def setUp(self):
        # 创建选手组
        self.competitor_group = Group.objects.create(name=GROUP_COMPETITOR)
        
        # 创建学生用户
        self.student = User.objects.create_user(
            username='student1',
            password='testpass123'
        )
        self.student.groups.add(self.competitor_group)
        
        # 创建教练用户
        self.coach = User.objects.create_user(
            username='coach1',
            password='testpass123'
        )
        
        # 创建奖惩类型
        self.reward_type = ConductType.objects.create(
            name='优秀表现',
            category='REWARD',
            score=Decimal('10.0'),
            created_by=self.coach
        )
    
    def test_create_record(self):
        """测试创建奖惩记录"""
        record = ConductRecord.objects.create(
            student=self.student,
            record_type=self.reward_type,
            score=self.reward_type.score,
            reason='表现优异',
            recorded_by=self.coach
        )
        self.assertEqual(record.student, self.student)
        self.assertEqual(record.status, 'PENDING')
        self.assertEqual(record.score, Decimal('10.0'))
    
    def test_approve_record_updates_summary(self):
        """测试审核通过后更新汇总"""
        record = ConductRecord.objects.create(
            student=self.student,
            record_type=self.reward_type,
            score=self.reward_type.score,
            reason='表现优异',
            recorded_by=self.coach,
            status='PENDING'
        )
        
        # 审核通过
        record.status = 'APPROVED'
        record.reviewed_by = self.coach
        record.save()
        
        # 检查汇总是否更新
        summary = ConductSummary.objects.get(student=self.student)
        self.assertEqual(summary.total_score, Decimal('10.0'))
        self.assertEqual(summary.reward_count, 1)


class ConductSummaryTestCase(TestCase):
    """奖惩汇总测试"""
    
    def setUp(self):
        self.competitor_group = Group.objects.create(name=GROUP_COMPETITOR)
        self.student = User.objects.create_user(
            username='student1',
            password='testpass123'
        )
        self.student.groups.add(self.competitor_group)
        
        self.coach = User.objects.create_user(
            username='coach1',
            password='testpass123'
        )
        
        self.reward_type = ConductType.objects.create(
            name='优秀',
            category='REWARD',
            score=Decimal('5.0'),
            created_by=self.coach
        )
        
        self.penalty_type = ConductType.objects.create(
            name='迟到',
            category='PENALTY',
            score=Decimal('-3.0'),
            created_by=self.coach
        )
    
    def test_summary_calculation(self):
        """测试汇总计算"""
        # 创建奖励记录
        ConductRecord.objects.create(
            student=self.student,
            record_type=self.reward_type,
            score=Decimal('5.0'),
            reason='表现优异',
            recorded_by=self.coach,
            status='APPROVED'
        )
        
        # 创建惩罚记录
        ConductRecord.objects.create(
            student=self.student,
            record_type=self.penalty_type,
            score=Decimal('-3.0'),
            reason='迟到',
            recorded_by=self.coach,
            status='APPROVED'
        )
        
        # 检查汇总
        summary = ConductSummary.objects.get(student=self.student)
        self.assertEqual(summary.total_score, Decimal('2.0'))
        self.assertEqual(summary.reward_count, 1)
        self.assertEqual(summary.penalty_count, 1)
