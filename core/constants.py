# core/constants.py
"""
全局常量定义模块
将硬编码的字符串统一管理，方便维护和修改
"""

# ============ 用户组名称常量 ============
GROUP_COACH = "教练"
GROUP_COMPETITOR = "选手"

# 所有需要特殊处理的组名列表
SPECIAL_GROUPS = [GROUP_COACH, GROUP_COMPETITOR]


# ============ 文件上传相关常量 ============
# 默认允许的文件扩展名
DEFAULT_ALLOWED_EXTENSIONS = ['pdf']

# 通知附件允许的扩展名
NOTICE_ALLOWED_EXTENSIONS = [
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'md',
    'jpg', 'jpeg', 'png', 'gif', 'txt',
    'zip', 'rar', '7z', 'tar', 'gz', 'bz2',
]


# ============ 默认配置值 ============
DEFAULT_UPLOAD_MAX_SIZE_MB = 100  # 默认上传文件最大尺寸，单位 MB
DEFAULT_CACHE_TIMEOUT = 300  # 默认缓存超时时间，单位秒
DEFAULT_INVITATION_CODE_TIMEOUT = 24 * 60 * 60  # 邀请码超时时间，单位秒
