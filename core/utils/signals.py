# core/utils/signals.py
"""
通用信号处理模块
提供文件清理等常用信号处理器的工厂函数
"""
from __future__ import annotations

import logging
from typing import Any, Type

from django.db import models
from django.db.models.signals import post_delete, pre_save


logger = logging.getLogger(__name__)


def register_file_cleanup_signals(
    model: Type[models.Model],
    file_field: str = "file",
) -> None:
    """
    为模型注册文件清理信号处理器
    
    会自动注册：
    1. post_delete: 删除记录时删除关联文件
    2. pre_save: 更新记录且文件被替换时删除旧文件
    
    Args:
        model: 需要注册信号的 Django 模型类
        file_field: 文件字段名称，默认为 "file"
    
    用法:
        # 在模型文件末尾调用
        from core.utils.signals import register_file_cleanup_signals
        register_file_cleanup_signals(Meeting, file_field="file")
    """
    
    def delete_file_on_delete(sender: Type[models.Model], instance: Any, **kwargs: Any) -> None:
        """删除记录后删除关联的物理文件"""
        file_obj = getattr(instance, file_field, None)
        if file_obj and getattr(file_obj, 'name', None):
            storage = file_obj.storage
            try:
                if storage.exists(file_obj.name):
                    storage.delete(file_obj.name)
                    logger.debug(f"已删除文件: {file_obj.name}")
            except Exception as e:
                logger.exception(f"删除文件失败 {file_obj.name}: {e}")
    
    def delete_old_file_on_change(sender: Type[models.Model], instance: Any, **kwargs: Any) -> None:
        """更新记录时，若文件被替换则删除旧文件"""
        if not instance.pk:
            return
        
        try:
            old_instance = model.objects.get(pk=instance.pk)
        except model.DoesNotExist:
            return
        
        old_file = getattr(old_instance, file_field, None)
        new_file = getattr(instance, file_field, None)
        
        if old_file and getattr(old_file, 'name', None):
            # 检查文件是否被替换（文件名不同或新文件为空）
            if (not new_file) or (old_file.name != getattr(new_file, 'name', None)):
                storage = old_file.storage
                try:
                    if storage.exists(old_file.name):
                        storage.delete(old_file.name)
                        logger.debug(f"已删除旧文件: {old_file.name}")
                except Exception as e:
                    logger.exception(f"删除旧文件失败 {old_file.name}: {e}")
    
    # 使用 dispatch_uid 避免重复注册
    uid_prefix = f"{model._meta.app_label}_{model._meta.model_name}"
    
    post_delete.connect(
        delete_file_on_delete,
        sender=model,
        dispatch_uid=f"{uid_prefix}_delete_file",
        weak=False,
    )
    
    pre_save.connect(
        delete_old_file_on_change,
        sender=model,
        dispatch_uid=f"{uid_prefix}_delete_old_file",
        weak=False,
    )
