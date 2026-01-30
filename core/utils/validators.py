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
