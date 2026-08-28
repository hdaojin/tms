CONDUCT_SEVERITIES = [
    {"code": "MINOR", "name": "轻微", "description": "", "is_active": True},
    {"code": "MODERATE", "name": "一般", "description": "", "is_active": True},
    {"code": "SEVERE", "name": "严重", "description": "", "is_active": True},
    {"code": "CRITICAL", "name": "特别严重", "description": "", "is_active": True},
]

CONDUCT_SEVERITY_RULES = [
    {"nature": "REWARD", "severity": "MINOR", "label": "鼓励", "multiplier": "0.00", "order": 10, "is_default": False},
    {"nature": "REWARD", "severity": "MODERATE", "label": "表扬", "multiplier": "1.00", "order": 20, "is_default": True},
    {"nature": "REWARD", "severity": "SEVERE", "label": "嘉奖", "multiplier": "2.00", "order": 30, "is_default": False},
    {"nature": "REWARD", "severity": "CRITICAL", "label": "特别嘉奖", "multiplier": "3.00", "order": 40, "is_default": False},
    {"nature": "PENALTY", "severity": "MINOR", "label": "轻微", "multiplier": "0.00", "order": 10, "is_default": False},
    {"nature": "PENALTY", "severity": "MODERATE", "label": "一般", "multiplier": "1.00", "order": 20, "is_default": True},
    {"nature": "PENALTY", "severity": "SEVERE", "label": "严重", "multiplier": "2.00", "order": 30, "is_default": False},
    {"nature": "PENALTY", "severity": "CRITICAL", "label": "特别严重", "multiplier": "3.00", "order": 40, "is_default": False},
]

CONDUCT_CATEGORIES = [
    {"code": "attendance", "nature": "PENALTY", "name": "考勤", "description": "考勤类惩罚事项", "order": 10, "is_active": True},
    {"code": "competition_award", "nature": "REWARD", "name": "竞赛获奖", "description": "竞赛获奖类奖励事项", "order": 10, "is_active": True},
]

CONDUCT_ITEMS = [
    {"category": "attendance", "code": "late", "name": "迟到", "default_score": "-1.00", "description": "考勤类惩罚事项：迟到。", "is_active": True},
    {"category": "attendance", "code": "early_leave", "name": "早退", "default_score": "-1.00", "description": "考勤类惩罚事项：早退。", "is_active": True},
    {"category": "attendance", "code": "absence", "name": "旷课", "default_score": "-5.00", "description": "考勤类惩罚事项：旷课。", "is_active": True},
    {"category": "competition_award", "code": "municipal", "name": "市级", "default_score": "1.00", "description": "竞赛获奖类奖励事项：市级。", "is_active": True},
    {"category": "competition_award", "code": "provincial", "name": "省级", "default_score": "5.00", "description": "竞赛获奖类奖励事项：省级。", "is_active": True},
    {"category": "competition_award", "code": "national", "name": "国家级", "default_score": "10.00", "description": "竞赛获奖类奖励事项：国家级。", "is_active": True},
    {"category": "competition_award", "code": "world", "name": "世界级", "default_score": "20.00", "description": "竞赛获奖类奖励事项：世界级。", "is_active": True},
]

BOOTSTRAP_DATA = [
    {"label": "奖惩严重程度", "model": "behaviors.ConductSeverity", "key_fields": ("code",), "collision_fields": (("name",),), "records": CONDUCT_SEVERITIES},
    {
        "label": "严重程度系数规则",
        "model": "behaviors.ConductSeverityRule",
        "key_fields": ("nature", "severity"),
        "records": CONDUCT_SEVERITY_RULES,
        "relations": {"severity": {"model": "behaviors.ConductSeverity", "key_fields": ("code",)}},
        "default_switch_field": "is_default",
        "default_switch_scope_fields": ("nature",),
        "default_requires_active_relation": "severity",
    },
    {"label": "奖惩分类", "model": "behaviors.ConductCategory", "key_fields": ("code",), "collision_fields": (("nature", "name"),), "records": CONDUCT_CATEGORIES},
    {
        "label": "奖惩事项",
        "model": "behaviors.ConductItem",
        "key_fields": ("category", "code"),
        "collision_fields": (("category", "name"),),
        "records": CONDUCT_ITEMS,
        "relations": {"category": {"model": "behaviors.ConductCategory", "key_fields": ("code",)}},
    },
]
