FORUM_CATEGORIES = [
    {"slug": "official", "name": "官方发布", "sort_order": 10, "is_active": True},
    {"slug": "technical", "name": "技术讨论", "sort_order": 20, "is_active": True},
    {"slug": "rules", "name": "竞赛规则", "sort_order": 30, "is_active": True},
    {"slug": "marking", "name": "评分", "sort_order": 40, "is_active": True},
    {"slug": "environment", "name": "竞赛环境", "sort_order": 50, "is_active": True},
    {"slug": "infrastructure", "name": "基础设施", "sort_order": 60, "is_active": True},
    {"slug": "other", "name": "其他", "sort_order": 70, "is_active": True},
]

FORUM_MODULES = [
    {"slug": "general", "name": "综合", "sort_order": 10, "is_active": True},
    {"slug": "module-a", "name": "模块 A", "sort_order": 20, "is_active": True},
    {"slug": "module-b", "name": "模块 B", "sort_order": 30, "is_active": True},
    {"slug": "module-c", "name": "模块 C", "sort_order": 40, "is_active": True},
    {"slug": "module-d", "name": "模块 D", "sort_order": 50, "is_active": True},
    {"slug": "other", "name": "其他", "sort_order": 60, "is_active": True},
]

FORUM_SOURCE_ROLES = [
    {"slug": "worldskills_official", "name": "世界技能组织官方", "sort_order": 10, "is_active": True, "is_official": True, "allows_detail": False},
    {"slug": "chief_expert", "name": "首席专家", "sort_order": 20, "is_active": True, "is_official": False, "allows_detail": False},
    {"slug": "deputy_chief_expert", "name": "副首席专家", "sort_order": 30, "is_active": True, "is_official": False, "allows_detail": False},
    {"slug": "expert", "name": "专家", "sort_order": 40, "is_active": True, "is_official": False, "allows_detail": False},
    {"slug": "organizer", "name": "竞赛组织方", "sort_order": 50, "is_active": True, "is_official": False, "allows_detail": False},
    {"slug": "other", "name": "其他", "sort_order": 60, "is_active": True, "is_official": False, "allows_detail": True},
]

FORUM_POST_TYPES = [
    {"code": "discussion", "name": "专家讨论", "description": "", "order": 10, "is_active": True, "is_official": False},
    {"code": "official_reply", "name": "官方回复", "description": "", "order": 20, "is_active": True, "is_official": True},
    {"code": "official_notice", "name": "官方通知", "description": "", "order": 30, "is_active": True, "is_official": True},
    {"code": "rule_change", "name": "规则变更", "description": "", "order": 40, "is_active": True, "is_official": True},
    {"code": "important_reminder", "name": "重要提醒", "description": "", "order": 50, "is_active": True, "is_official": False},
]

BOOTSTRAP_DATA = [
    {"label": "论坛分类", "model": "worldskills_forum.ForumCategory", "key_fields": ("slug",), "collision_fields": (("name",),), "records": FORUM_CATEGORIES},
    {"label": "论坛模块", "model": "worldskills_forum.ForumModule", "key_fields": ("slug",), "collision_fields": (("name",),), "records": FORUM_MODULES},
    {"label": "论坛来源身份", "model": "worldskills_forum.ForumSourceRole", "key_fields": ("slug",), "collision_fields": (("name",),), "records": FORUM_SOURCE_ROLES},
    {"label": "论坛信息类型", "model": "worldskills_forum.ForumPostType", "key_fields": ("code",), "collision_fields": (("name",),), "records": FORUM_POST_TYPES},
]
