# core/constants.py
"""
全局常量定义模块
将硬编码的字符串统一管理，方便维护和修改
"""

from pathlib import Path


# ============ 项目路径常量 ============
# 项目根目录（core/constants.py -> core -> tms）
BASE_DIR = Path(__file__).resolve().parent.parent

# 私有媒体文件根目录（通过 Django 处理，可控制访问权限）
PRIVATE_MEDIA_ROOT = BASE_DIR / "media-private"


# ============ 用户组名称常量 ============
GROUP_COACH = "教练"
GROUP_COMPETITOR = "选手"
GROUP_ASSISTANT = "班务"

# 所有需要特殊处理的组名列表
SPECIAL_GROUPS = [GROUP_COACH, GROUP_COMPETITOR]


# ============ 操行管理常量 ============
# 操行性质
CONDUCT_NATURE_REWARD = 'REWARD'
CONDUCT_NATURE_PENALTY = 'PENALTY'

CONDUCT_SEVERITY_MINOR = 'MINOR'
CONDUCT_SEVERITY_MODERATE = 'MODERATE'
CONDUCT_SEVERITY_SEVERE = 'SEVERE'
CONDUCT_SEVERITY_CRITICAL = 'CRITICAL'

CONDUCT_NATURE_CHOICES = [
    (CONDUCT_NATURE_REWARD, '奖励'),
    (CONDUCT_NATURE_PENALTY, '惩罚'),
]

CONDUCT_SEVERITY_CHOICES = [
    (CONDUCT_SEVERITY_MINOR, '轻微'),
    (CONDUCT_SEVERITY_MODERATE, '一般'),
    (CONDUCT_SEVERITY_SEVERE, '严重'),
    (CONDUCT_SEVERITY_CRITICAL, '特别严重'),
]

# 操行性质显示名称映射
CONDUCT_NATURE_NAMES = {
    CONDUCT_NATURE_REWARD: '奖励',
    CONDUCT_NATURE_PENALTY: '惩罚',
}

CONDUCT_SEVERITY_NAMES = {
    CONDUCT_SEVERITY_MINOR: '轻微',
    CONDUCT_SEVERITY_MODERATE: '一般',
    CONDUCT_SEVERITY_SEVERE: '严重',
    CONDUCT_SEVERITY_CRITICAL: '特别严重',
}

CONDUCT_REWARD_SEVERITY_NAMES = {
    CONDUCT_SEVERITY_MINOR: '鼓励',
    CONDUCT_SEVERITY_MODERATE: '表扬',
    CONDUCT_SEVERITY_SEVERE: '嘉奖',
    CONDUCT_SEVERITY_CRITICAL: '特别嘉奖',
}

CONDUCT_PENALTY_SEVERITY_NAMES = {
    CONDUCT_SEVERITY_MINOR: '轻微',
    CONDUCT_SEVERITY_MODERATE: '一般',
    CONDUCT_SEVERITY_SEVERE: '严重',
    CONDUCT_SEVERITY_CRITICAL: '特别严重',
}


# ============ 默认配置值 ============
DEFAULT_CACHE_TIMEOUT = 300  # 默认缓存超时时间，单位秒
INVITATION_CODE_TIMEOUT = 24 * 60 * 60  # 邀请码超时时间，单位秒


# ============ 允许上传的文件扩展名和大小常量 ============
# 默认允许的文件扩展名和大小
DEFAULT_ALLOWED_EXTENSIONS = ['pdf']
DEFAULT_UPLOAD_MAX_SIZE_MB = 100 

# 新标准链路资料文件允许的扩展名和大小
ARCHIVE_ALLOWED_EXTENSIONS = [
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'zip', 'gz', 'bz2', 'rar', '7z',
    'json', 'txt', 'csv', 'png', 'jpg', 'jpeg',
]
ARCHIVE_UPLOAD_MAX_SIZE_MB = 100

# 评分表与结果包允许的扩展名和大小
SCORING_WORKBOOK_ALLOWED_EXTENSIONS = ['xlsx']
SCORING_WORKBOOK_UPLOAD_MAX_SIZE_MB = 50
SCORING_RESULT_PACKAGE_ALLOWED_EXTENSIONS = ['json', 'zip']
SCORING_RESULT_PACKAGE_UPLOAD_MAX_SIZE_MB = 100

# 训练日志允许的扩展名和大小
TRAINING_LOG_ALLOWED_EXTENSIONS = ['doc', 'docx', 'pdf', 'txt', 'md']
TRAINING_LOG_UPLOAD_MAX_SIZE_MB = 20


# 通知附件允许的扩展名和大小
NOTICE_ALLOWED_EXTENSIONS = [
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'md', 'txt',
    'jpg', 'jpeg', 'png', 'gif',
    'zip', 'rar', '7z', 'tar', 'gz', 'bz2',
]
NOTICE_UPLOAD_MAX_SIZE_MB = 100

# 操行记录附件允许的扩展名和大小
CONDUCT_ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png']
CONDUCT_UPLOAD_MAX_SIZE_MB = 50


# ============ 文件上传路径 ============
# 笔记目录（私有，完整路径）
NOTES_ROOT = PRIVATE_MEDIA_ROOT / "notes"

# 资料资产上传目录（私有，完整路径）
ARCHIVE_UPLOAD_DIR = PRIVATE_MEDIA_ROOT / "archives"

# 奖惩记录附件上传目录（公共，相对于 MEDIA_ROOT）
BEHAVIORS_UPLOAD_DIR = Path("behaviors")

# 会议记录上传目录（公共，相对于 MEDIA_ROOT）
MEETINGS_UPLOAD_DIR = "meetings"

# 通知附件上传目录（公共，相对于 MEDIA_ROOT）
NOTICE_UPLOAD_DIR = "notices"
