from collections import Counter
from django.contrib.auth import get_user_model
from django.db import transaction
from training.models import TrainingPlan
from training.plan_workbooks import preview_import

plan = TrainingPlan.objects.get(pk=2)
user = get_user_model().objects.get(pk=1)
path = 'outputs/01a1a1e4/测试月计划-优化排班.xlsx'
with open(path, 'rb') as f:
    rows, _ = preview_import(plan, user, f)
print('当前名单:', dict(Counter(row['status'] for row in rows)))
with transaction.atomic():
    plan.responsible_coaches.add(6, 10)
    with open(path, 'rb') as f:
        rows, payload = preview_import(plan, user, f)
    print('模拟补齐名单:', dict(Counter(row['status'] for row in rows)), '变更:', len(payload))
    print('错误:', [(row['row'], row['message']) for row in rows if row['status'] == '错误'][:3])
    transaction.set_rollback(True)
