"""默认角色声明；授权仅由实际 Django Permission 和对象范围决定。"""

COMMON_BUNDLES = [
    "accounts.manage_own_profile",
    "notices.view_notices",
    "behaviors.view_own_conduct",
    "feedback.submit_feedback",
    "feedback.reply_feedback",
]

DEFAULT_ROLES = [
    {
        "codename": "competitor",
        "name": "选手",
        "description": "维护本人训练执行和日志，查看标准、本人相关竞赛与评分。仍需显式周期成员身份和任务分配。",
        "bundles": [
            *COMMON_BUNDLES,
            "training.competitor",
            "standards.view_standard",
            "assessments.view_assessments",
            "scoring.view_own_results",
            "behaviors.conduct_subject",
        ],
    },
    {
        "codename": "coach",
        "name": "教练",
        "description": "请配置技术领域，或复制为各领域教练组。维护范围还取决于对象归属和显式分配；不包含新增竞赛与考核及全系统训练统筹。",
        "bundles": [
            *COMMON_BUNDLES,
            "training.view_training",
            "training.maintain_own_logs",
            "training.maintain_tasks",
            "standards.view_standard",
            "standards.maintain_skills",
            "standards.edit_current_tree",
            "assessments.view_assessments",
            "assessments.maintain_scoped_assessments",
            "scoring.maintain_scoring",
            "evidence.view_evidence",
            "evidence.edit_evidence",
        ],
    },
    {
        "codename": "assistant",
        "name": "班务",
        "description": "协助管理班级日常事务，可录入和查看全体奖惩、发布通知、上传会议；不包含账号管理、完整用户资料或奖惩审核。",
        "bundles": [
            *COMMON_BUNDLES,
            "behaviors.record_conduct",
            "behaviors.view_all_conduct_records",
            "notices.publish_notice",
            "meetings.upload_meeting",
        ],
    },
]
