FEEDBACK_CATEGORIES = [
    {"code": "bug", "name": "Bug反馈", "description": "", "default_private": False, "order": 10, "is_active": True},
    {"code": "feature", "name": "功能需求", "description": "", "default_private": False, "order": 20, "is_active": True},
    {"code": "suggestion", "name": "意见建议", "description": "", "default_private": False, "order": 30, "is_active": True},
    {"code": "complaint", "name": "我要投诉", "description": "", "default_private": True, "order": 40, "is_active": True},
]

BOOTSTRAP_DATA = [
    {"label": "反馈分类", "model": "feedback.FeedbackCategory", "key_fields": ("code",), "collision_fields": (("name",),), "records": FEEDBACK_CATEGORIES},
]
