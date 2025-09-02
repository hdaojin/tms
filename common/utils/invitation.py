from django.core import signing
from django.conf import settings
from django.utils import timezone

# 盐值用于签名
INVITATION_SALT = 'invitation-salt'
# 默认有效期（秒），可在 settings.py 中通过 INVITATION_CODE_TIMEOUT 自定义
# DEFAULT_TIMEOUT = 1 * 24 * 3600


def generate_invitation_code():
    """
    生成一个无状态的邀请代码，包含创建时间戳和签名。
    管理员可通过 shell 或命令行调用此函数获取邀请码。
    """
    ts = int(timezone.now().timestamp())
    payload = {'ts': ts}
    return signing.dumps(payload, salt=INVITATION_SALT)


def validate_invitation_code(code):
    """
    验证邀请代码是否合法且未过期。
    返回 True 表示有效，否则 False。
    """
    # timeout = getattr(settings, 'INVITATION_CODE_TIMEOUT', DEFAULT_TIMEOUT)
    timeout = settings.INVITATION_CODE_TIMEOUT
    # 计算当前时间戳与邀请码中的时间戳的差值
    try:
        signing.loads(code, salt=INVITATION_SALT, max_age=timeout)
        return True
    except (signing.SignatureExpired, signing.BadSignature):
        return False
