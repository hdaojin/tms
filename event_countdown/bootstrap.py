COUNTDOWN_EVENT_TYPES = [
    {"code": "worldskills", "name": "世界技能大赛", "description": "", "order": 10, "is_active": True},
    {"code": "national", "name": "全国技能大赛", "description": "", "order": 20, "is_active": True},
    {"code": "provincial", "name": "省级技能大赛", "description": "", "order": 30, "is_active": True},
    {"code": "municipal", "name": "市级技能大赛", "description": "", "order": 40, "is_active": True},
    {"code": "school", "name": "校内比赛", "description": "", "order": 50, "is_active": True},
    {"code": "training", "name": "集训活动", "description": "", "order": 60, "is_active": True},
    {"code": "exam", "name": "考核测评", "description": "", "order": 70, "is_active": True},
    {"code": "meeting", "name": "会议活动", "description": "", "order": 80, "is_active": True},
    {"code": "other", "name": "其他活动", "description": "", "order": 90, "is_active": True},
]

BOOTSTRAP_DATA = [
    {"label": "倒计时事件类型", "model": "event_countdown.CountdownEventType", "key_fields": ("code",), "collision_fields": (("name",),), "records": COUNTDOWN_EVENT_TYPES},
]
