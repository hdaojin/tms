#!/usr/bin/env python
"""
Conduct 应用功能验证脚本
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tmsproject.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from conduct.models import ConductCategory, ConductItem, ConductRecord, ConductSummary
from core.constants import GROUP_COMPETITOR, CONDUCT_NATURE_CHOICES, CONDUCT_NATURE_REWARD, CONDUCT_NATURE_PENALTY

User = get_user_model()

def main():
    print("=" * 60)
    print("Conduct 应用功能验证")
    print("=" * 60)
    
    # 1. 检查奖惩分类和事项
    print("\n1. 奖惰分类和事项统计：")
    reward_categories = ConductCategory.objects.filter(nature=CONDUCT_NATURE_REWARD).count()
    penalty_categories = ConductCategory.objects.filter(nature=CONDUCT_NATURE_PENALTY).count()
    reward_items = ConductItem.objects.filter(category__nature=CONDUCT_NATURE_REWARD).count()
    penalty_items = ConductItem.objects.filter(category__nature=CONDUCT_NATURE_PENALTY).count()
    print(f"   奖励分类: {reward_categories} 个")
    print(f"   奖励事项: {reward_items} 个")
    print(f"   惩罚分类: {penalty_categories} 个")
    print(f"   惩罚事项: {penalty_items} 个")
    
    # 2. 检查选手组
    print("\n2. 选手组信息：")
    try:
        competitor_group = Group.objects.get(name=GROUP_COMPETITOR)
        student_count = User.objects.filter(groups=competitor_group, is_active=True).count()
        print(f"   选手组名称: {competitor_group.name}")
        print(f"   当前选手数: {student_count} 人")
    except Group.DoesNotExist:
        print(f"   ⚠️  警告：选手组 '{GROUP_COMPETITOR}' 不存在")
    
    # 3. 检查奖惩记录
    print("\n3. 奖惩记录统计：")
    total_records = ConductRecord.objects.count()
    pending_records = ConductRecord.objects.filter(status='PENDING').count()
    approved_records = ConductRecord.objects.filter(status='APPROVED').count()
    rejected_records = ConductRecord.objects.filter(status='REJECTED').count()
    print(f"   总记录数: {total_records}")
    print(f"   待审核: {pending_records}")
    print(f"   已通过: {approved_records}")
    print(f"   已驳回: {rejected_records}")
    
    # 4. 检查汇总表
    print("\n4. 奖惩汇总统计：")
    summary_count = ConductSummary.objects.count()
    print(f"   汇总记录数: {summary_count}")
    if summary_count > 0:
        top_student = ConductSummary.objects.order_by('-total_score').first()
        if top_student:
            print(f"   排名第一: {top_student.student.display_name}")
            print(f"   总分: {top_student.total_score:+.1f}")
    
    # 5. 检查URL配置
    print("\n5. URL路由检查：")
    from django.urls import reverse
    urls_to_check = [
        ('conduct:type_list', '奖惩类型列表'),
        ('conduct:record_list', '奖惩记录列表'),
        ('conduct:summary_list', '排行榜'),
        ('conduct:my_conduct', '我的奖惩'),
    ]
    
    for url_name, description in urls_to_check:
        try:
            url = reverse(url_name)
            print(f"   ✓ {description}: {url}")
        except Exception as e:
            print(f"   ✗ {description}: 错误 - {e}")
    
    print("\n" + "=" * 60)
    print("✅ 验证完成！")
    print("=" * 60)

if __name__ == '__main__':
    main()
