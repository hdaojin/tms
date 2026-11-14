from hashlib import sha256
from secrets import token_urlsafe


def generate_invitation_code() -> str:
    """生成含 256 位随机性的一次性展示凭证。"""
    return token_urlsafe(32)


def invitation_code_digest(code: str) -> str:
    return sha256(code.encode("utf-8")).hexdigest()
