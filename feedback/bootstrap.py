from django.core.exceptions import ValidationError

from .models import FeedbackCategory


FEEDBACK_CATEGORY_DEFAULTS = (
    ("bug", "Bug反馈", False, 10),
    ("feature", "功能需求", False, 20),
    ("suggestion", "意见建议", False, 30),
    ("complaint", "我要投诉", True, 40),
)


def bootstrap_defaults():
    created_count = 0
    existing_count = 0
    for code, name, default_private, order in FEEDBACK_CATEGORY_DEFAULTS:
        if FeedbackCategory.objects.filter(name=name).exclude(code=code).exists():
            raise ValidationError(f"反馈分类“{name}”已被其他代码占用，请先人工修正稳定代码。")
        _category, created = FeedbackCategory.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "default_private": default_private,
                "order": order,
            },
        )
        created_count += int(created)
        existing_count += int(not created)
    return {"created": created_count, "existing": existing_count}
