from django.core.exceptions import ValidationError

from .models import ForumCategory, ForumModule, ForumPostType, ForumSourceRole


FORUM_CATEGORY_DEFAULTS = (
    ("official", "官方发布"),
    ("technical", "技术讨论"),
    ("rules", "竞赛规则"),
    ("marking", "评分"),
    ("environment", "竞赛环境"),
    ("infrastructure", "基础设施"),
    ("other", "其他"),
)

FORUM_MODULE_DEFAULTS = (
    ("general", "综合"),
    ("module-a", "模块 A"),
    ("module-b", "模块 B"),
    ("module-c", "模块 C"),
    ("module-d", "模块 D"),
    ("other", "其他"),
)

FORUM_SOURCE_ROLE_DEFAULTS = (
    ("worldskills_official", "世界技能组织官方", True, False),
    ("chief_expert", "首席专家", False, False),
    ("deputy_chief_expert", "副首席专家", False, False),
    ("expert", "专家", False, False),
    ("organizer", "竞赛组织方", False, False),
    ("other", "其他", False, True),
)

FORUM_POST_TYPE_DEFAULTS = (
    ("discussion", "专家讨论", False),
    ("official_reply", "官方回复", True),
    ("official_notice", "官方通知", True),
    ("rule_change", "规则变更", True),
    ("important_reminder", "重要提醒", False),
)


def _bootstrap_slugged(model, definitions):
    created_count = 0
    existing_count = 0
    for sort_order, definition in enumerate(definitions):
        slug, name, *flags = definition
        if model.objects.filter(name=name).exclude(slug=slug).exists():
            raise ValidationError(f"{model._meta.verbose_name}“{name}”已被其他标识占用，请先人工修正。")
        defaults = {"name": name, "sort_order": sort_order}
        if model is ForumSourceRole:
            defaults.update({"is_official": flags[0], "allows_detail": flags[1]})
        _obj, created = model.objects.get_or_create(slug=slug, defaults=defaults)
        created_count += int(created)
        existing_count += int(not created)
    return created_count, existing_count


def bootstrap_defaults():
    created_count = 0
    existing_count = 0
    for model, definitions in (
        (ForumCategory, FORUM_CATEGORY_DEFAULTS),
        (ForumModule, FORUM_MODULE_DEFAULTS),
        (ForumSourceRole, FORUM_SOURCE_ROLE_DEFAULTS),
    ):
        created, existing = _bootstrap_slugged(model, definitions)
        created_count += created
        existing_count += existing

    for order, (code, name, is_official) in enumerate(FORUM_POST_TYPE_DEFAULTS, start=1):
        if ForumPostType.objects.filter(name=name).exclude(code=code).exists():
            raise ValidationError(f"论坛信息类型“{name}”已被其他代码占用，请先人工修正。")
        _obj, created = ForumPostType.objects.get_or_create(
            code=code,
            defaults={"name": name, "is_official": is_official, "order": order * 10},
        )
        created_count += int(created)
        existing_count += int(not created)

    return {"created": created_count, "existing": existing_count}
