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

# 所有需要特殊处理的组名列表
SPECIAL_GROUPS = [GROUP_COACH, GROUP_COMPETITOR]


# ============ 默认配置值 ============
DEFAULT_UPLOAD_MAX_SIZE_MB = 100  # 默认上传文件最大尺寸，单位 MB
DEFAULT_CACHE_TIMEOUT = 300  # 默认缓存超时时间，单位秒
INVITATION_CODE_TIMEOUT = 24 * 60 * 60  # 邀请码超时时间，单位秒


# ============ 文件扩展名常量 ============
# 默认允许的文件扩展名
DEFAULT_ALLOWED_EXTENSIONS = ['pdf']

# 考核文件允许的扩展名
ASSESSMENT_ALLOWED_EXTENSIONS = [
    'xls', 'xlsx', 'csv', 'pdf', 'doc', 'docx',
    'jpg', 'jpeg', 'png',
    'zip', '7z', 'gz', 'bz2', 'rar',
]

# 竞赛文件允许的扩展名
COMPETITION_ALLOWED_EXTENSIONS = [
    'xls', 'xlsx', 'csv', 'pdf', 'doc', 'docx',
    'jpg', 'jpeg', 'png',
    'zip', '7z', 'gz', 'bz2', 'rar',
]

# 训练日志允许的扩展名
TRAININGLOG_ALLOWED_EXTENSIONS = ['doc', 'docx', 'pdf']

# 通知附件允许的扩展名
NOTICE_ALLOWED_EXTENSIONS = [
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'md',
    'jpg', 'jpeg', 'png', 'gif', 'txt',
    'zip', 'rar', '7z', 'tar', 'gz', 'bz2',
]


# ============ 文件上传路径 ============
# 笔记目录（私有，完整路径）
NOTES_ROOT = PRIVATE_MEDIA_ROOT / "notes"

# 考核文件上传目录（私有，完整路径）
ASSESSMENT_UPLOAD_DIR = PRIVATE_MEDIA_ROOT / "assessment"

# 竞赛文件上传目录（私有，完整路径）
COMPETITION_UPLOAD_DIR = PRIVATE_MEDIA_ROOT / "competitions"

# 训练日志上传目录（公共，相对于 MEDIA_ROOT）
TRAININGLOG_UPLOAD_DIR = "traininglogs"

# 会议记录上传目录（公共，相对于 MEDIA_ROOT）
MEETING_UPLOAD_DIR = "meetings"

# 通知附件上传目录（公共，相对于 MEDIA_ROOT）
NOTICE_UPLOAD_DIR = "notices"