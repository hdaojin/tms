from django.core.exceptions import ValidationError

from .models import AssessmentType, CompetitionRole


ASSESSMENT_TYPE_DEFAULTS = (
    ("competition", "正式竞赛", 10),
    ("selection", "选拔赛", 20),
    ("exchange", "交流赛", 30),
    ("mock", "模拟赛", 40),
    ("training_assessment", "训练考核", 50),
    ("training_test", "训练测试", 60),
    ("other", "其他", 70),
)

COMPETITION_ROLE_DEFAULTS = (
    ("project_manager", "项目经理", CompetitionRole.Category.OFFICIAL, 10),
    ("skill_competition_manager", "技能竞赛经理", CompetitionRole.Category.OFFICIAL, 20),
    ("venue_manager", "场地经理", CompetitionRole.Category.OFFICIAL, 30),
    ("team_leader", "领队", CompetitionRole.Category.OFFICIAL, 40),
    ("chief_expert", "专家组长", CompetitionRole.Category.EXPERT, 50),
    ("deputy_chief_expert", "副专家组长", CompetitionRole.Category.EXPERT, 60),
    ("expert", "专家", CompetitionRole.Category.EXPERT, 70),
    ("judge", "裁判", CompetitionRole.Category.EXPERT, 80),
    ("coach", "教练", CompetitionRole.Category.COACH, 90),
    ("competitor", "选手", CompetitionRole.Category.COMPETITOR, 100),
    ("staff", "工作人员", CompetitionRole.Category.STAFF, 110),
    ("observer", "观察员", CompetitionRole.Category.OTHER, 120),
    ("other", "其他", CompetitionRole.Category.OTHER, 999),
)


def _create_defaults(model, definitions):
    created_count = 0
    existing_count = 0
    for code, name, *values in definitions:
        if model.objects.filter(name=name).exclude(code=code).exists():
            raise ValidationError(
                f'{model._meta.verbose_name}“{name}”已被其他代码占用，请先人工修正稳定代码。'
            )
        if model is AssessmentType:
            defaults = {"name": name, "order": values[0]}
        else:
            defaults = {"name": name, "category": values[0], "order": values[1]}
        _obj, created = model.objects.get_or_create(code=code, defaults=defaults)
        created_count += int(created)
        existing_count += int(not created)
    return created_count, existing_count


def bootstrap_defaults():
    type_created, type_existing = _create_defaults(AssessmentType, ASSESSMENT_TYPE_DEFAULTS)
    role_created, role_existing = _create_defaults(CompetitionRole, COMPETITION_ROLE_DEFAULTS)
    return {
        "created": type_created + role_created,
        "existing": type_existing + role_existing,
    }
