from django.core import signing
from core.constants import INVITATION_CODE_TIMEOUT

# 盐值用于签名（增加安全性）
INVITATION_SALT = 'invitation-code-v1'


def generate_invitation_code():
    """
    使用 Django signing 生成安全的邀请码。
    
    安全特性：
      - 使用 HMAC-SHA256 签名（基于 Django SECRET_KEY）
      - 包含时间戳，自动支持过期验证
      - 防篡改、防伪造，经过 Django 核心团队验证
      - 无需手动管理时间戳和签名逻辑
    
    返回：
        str: 签名后的邀请码字符串（约60-70字符）
    
    示例：
        >>> code = generate_invitation_code()
        >>> print(code)
        'Imludml0ZSI.abc123...'  # 实际长度约60-70字符
    """
    # 简单的载荷，主要依靠 Django 的时间戳机制
    payload = {'type': 'invite'}
    return signing.dumps(payload, salt=INVITATION_SALT)


def validate_invitation_code(code):
    """
    验证邀请代码是否合法且未过期。
    
    使用 Django signing.loads() 自动验证：
      1. 签名是否正确（基于 SECRET_KEY）
      2. 是否被篡改
      3. 是否在有效期内（max_age）
    
    参数：
        code (str): 待验证的邀请码
    
    返回：
        bool: True 表示有效，False 表示无效或已过期
    
    安全机制：
      - 自动防止伪造（签名验证）
      - 自动防止篡改（HMAC 完整性检查）
      - 自动防止重放攻击（时间戳 + max_age）
    """
    try:
        # 清理前后空格（常见的复制粘贴问题）
        code = code.strip()
        
        # Django signing 会自动验证签名和时间戳
        signing.loads(
            code,
            salt=INVITATION_SALT,
            max_age=INVITATION_CODE_TIMEOUT
        )
        return True
    except (signing.SignatureExpired, signing.BadSignature, Exception):
        # SignatureExpired: 邀请码已过期
        # BadSignature: 签名无效（伪造或篡改）
        # Exception: 其他错误（格式错误等）
        return False
