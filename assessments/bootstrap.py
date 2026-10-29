ASSESSMENT_LEVELS = [
    {"code": "world", "name": "世界级", "weight": "1.00", "order": 10, "is_active": True},
    {"code": "national", "name": "国家级", "weight": "1.00", "order": 20, "is_active": True},
    {"code": "provincial", "name": "省级", "weight": "1.00", "order": 30, "is_active": True},
]

ASSESSMENT_SERIES = [
    {"code": "worldskills", "name": "世界技能大赛", "description": "", "order": 10, "is_active": True},
    {"code": "chinaskills", "name": "全国职业技能大赛", "description": "", "order": 20, "is_active": True},
    {"code": "provincialskills", "name": "省级职业技能大赛", "description": "", "order": 30, "is_active": True},
]

ASSESSMENT_TYPES = [
    {"code": "competition", "name": "正式竞赛", "description": "", "order": 10, "is_active": True},
    {"code": "selection", "name": "选拔赛", "description": "", "order": 20, "is_active": True},
    {"code": "exchange", "name": "交流赛", "description": "", "order": 30, "is_active": True},
    {"code": "mock", "name": "模拟赛", "description": "", "order": 40, "is_active": True},
    {"code": "training_assessment", "name": "训练考核", "description": "", "order": 50, "is_active": True},
    {"code": "training_test", "name": "训练测试", "description": "", "order": 60, "is_active": True},
    {"code": "other", "name": "其他", "description": "", "order": 70, "is_active": True},
]

COMPETITION_ROLES = [
    {"code": "skill_competition_manager", "name": "赛项经理", "english_name": "Skill Competition Manager (SCM)", "category": "official", "description": "", "order": 10, "is_active": True},
    {"code": "chief_expert", "name": "首席专家", "english_name": "Chief Expert (CE)", "category": "official", "description": "", "order": 20, "is_active": True},
    {"code": "venue_manager", "name": "场地经理", "english_name": "Workshop Manager (WM)", "category": "official", "description": "", "order": 30, "is_active": True},
    {"code": "workshop_manager_assistant", "name": "场地经理助理", "english_name": "Workshop Manager Assistant (WMA)", "category": "official", "description": "", "order": 40, "is_active": True},
    {"code": "skill_advisor", "name": "技能/技术顾问", "english_name": "Skill Advisor", "category": "official", "description": "", "order": 50, "is_active": True},
    {"code": "competitions_committee_delegate_lead", "name": "竞赛委员会首席代表", "english_name": "Competitions Committee Delegate Lead", "category": "official", "description": "", "order": 60, "is_active": True},
    {"code": "competitions_committee_delegate", "name": "竞赛委员会代表", "english_name": "Competitions Committee Delegate", "category": "official", "description": "", "order": 70, "is_active": True},
    {"code": "expert", "name": "专家", "english_name": "Expert", "category": "expert", "description": "", "order": 80, "is_active": True},
    {"code": "judge", "name": "裁判", "english_name": "Judge", "category": "expert", "description": "", "order": 90, "is_active": True},
    {"code": "coach", "name": "教练", "english_name": "Coach", "category": "expert", "description": "", "order": 100, "is_active": True},
    {"code": "competitor", "name": "选手", "english_name": "Competitor", "category": "competitor", "description": "", "order": 110, "is_active": True},
    {"code": "reserve_competitor", "name": "备选选手", "english_name": "Reserve Competitor", "category": "competitor", "description": "", "order": 120, "is_active": True},
    {"code": "interpreter", "name": "翻译", "english_name": "Interpreter", "category": "other", "description": "", "order": 130, "is_active": True},
    {"code": "team_leader", "name": "领队", "english_name": "Team Leader", "category": "other", "description": "", "order": 140, "is_active": True},
    {"code": "observer", "name": "观察员", "english_name": "Observer", "category": "other", "description": "", "order": 150, "is_active": True},
    {"code": "staff", "name": "工作人员", "english_name": "Staff", "category": "other", "description": "", "order": 160, "is_active": True},
]

BOOTSTRAP_DATA = [
    {"label": "竞赛与考核级别", "model": "assessments.AssessmentLevel", "key_fields": ("code",), "collision_fields": (("name",),), "records": ASSESSMENT_LEVELS},
    {"label": "竞赛与考核系列", "model": "assessments.AssessmentSeries", "key_fields": ("code",), "collision_fields": (("name",),), "records": ASSESSMENT_SERIES},
    {"label": "竞赛与考核类型", "model": "assessments.AssessmentType", "key_fields": ("code",), "collision_fields": (("name",),), "records": ASSESSMENT_TYPES},
    {"label": "赛事角色", "model": "assessments.CompetitionRole", "key_fields": ("code",), "collision_fields": (("name",),), "records": COMPETITION_ROLES},
]
