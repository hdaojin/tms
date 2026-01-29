# core/utils/validators.py
"""
通用验证器模块
提供文件大小、日期等常用验证器，避免在各应用中重复定义
"""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.constants import DEFAULT_UPLOAD_MAX_SIZE_MB


def get_max_upload_size_mb() -> int:
    """获取配置的最大上传文件大小（MB）"""
    return getattr(settings, 'UPLOAD_MAX_SIZE_MB', DEFAULT_UPLOAD_MAX_SIZE_MB)


def validate_file_size(file: Any, max_size_mb: int | None = None) -> None:
    """
    验证上传文件大小不超过指定限制
    
    Args:
        file: 上传的文件对象
        max_size_mb: 最大文件大小（MB），默认使用 settings.UPLOAD_MAX_SIZE_MB
    
    Raises:
        ValidationError: 文件大小超过限制时抛出
    """
    if max_size_mb is None:
        max_size_mb = get_max_upload_size_mb()
    
    file_size = getattr(file, 'size', 0)
    if file_size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"上传文件大小不能超过 {max_size_mb}MB。")


def validate_date_not_future(date: Any, field_name: str = "日期") -> None:
    """
    验证日期不能晚于今天
    
    Args:
        date: 要验证的日期
        field_name: 字段名称，用于错误消息
    
    Raises:
        ValidationError: 日期晚于今天时抛出
    """
    if date and date > timezone.localdate():
        raise ValidationError(f"{field_name}不能晚于今天。")


def validate_date_not_past(date: Any, field_name: str = "日期") -> None:
    """
    验证日期不能早于今天
    
    Args:
        date: 要验证的日期
        field_name: 字段名称，用于错误消息
    
    Raises:
        ValidationError: 日期早于今天时抛出
    """
    if date and date < timezone.localdate():
        raise ValidationError(f"{field_name}不能早于今天。")


def validate_pdf_file(file: Any) -> None:
    """
    验证文件是否为 PDF 格式
    
    Args:
        file: 上传的文件对象
    
    Raises:
        ValidationError: 文件不是 PDF 格式时抛出
    """
    name_lower = getattr(file, 'name', '').lower()
    if not name_lower.endswith('.pdf'):
        raise ValidationError("上传文件格式必须为 .pdf。")


# ============ 可调用的验证器类（用于模型字段） ============

class FileSizeValidator:
    """
    文件大小验证器类，可用于模型字段的 validators 参数
    
    用法:
        file = models.FileField(validators=[FileSizeValidator(max_size_mb=10)])
    """
    
    def __init__(self, max_size_mb: int | None = None):
        self.max_size_mb = max_size_mb
    
    def __call__(self, file: Any) -> None:
        validate_file_size(file, self.max_size_mb)
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, FileSizeValidator) and self.max_size_mb == other.max_size_mb
    
    def deconstruct(self) -> tuple[str, tuple, dict]:
        """支持 Django 迁移序列化"""
        return (
            'core.utils.validators.FileSizeValidator',
            (),
            {'max_size_mb': self.max_size_mb},
        )


class DateNotFutureValidator:
    """
    日期不能为未来的验证器类
    
    用法:
        date = models.DateField(validators=[DateNotFutureValidator("训练日期")])
    """
    
    def __init__(self, field_name: str = "日期"):
        self.field_name = field_name
    
    def __call__(self, date: Any) -> None:
        validate_date_not_future(date, self.field_name)
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, DateNotFutureValidator) and self.field_name == other.field_name
    
    def deconstruct(self) -> tuple[str, tuple, dict]:
        """支持 Django 迁移序列化"""
        return (
            'core.utils.validators.DateNotFutureValidator',
            (),
            {'field_name': self.field_name},
        )


class DateNotPastValidator:
    """
    日期不能为过去的验证器类
    
    用法:
        date = models.DateField(validators=[DateNotPastValidator("开始日期")])
    """
    
    def __init__(self, field_name: str = "日期"):
        self.field_name = field_name
    
    def __call__(self, date: Any) -> None:
        validate_date_not_past(date, self.field_name)
    
    def __eq__(self, other: object) -> bool:
        return isinstance(other, DateNotPastValidator) and self.field_name == other.field_name
    
    def deconstruct(self) -> tuple[str, tuple, dict]:
        """支持 Django 迁移序列化"""
        return (
            'core.utils.validators.DateNotPastValidator',
            (),
            {'field_name': self.field_name},
        )
