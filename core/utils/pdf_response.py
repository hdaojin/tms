# core/utils/pdf_response.py
"""
PDF 文件响应工具模块
提供 PDF 文件的内联预览响应功能
"""
from __future__ import annotations

from typing import Any, Callable, Type

from django.http import FileResponse, Http404, HttpRequest
from django.shortcuts import get_object_or_404
from django.db import models


def pdf_inline_response(file_path: str, filename: str) -> FileResponse:
    """
    返回一个 PDF 文件的 inline 响应，适合在浏览器中直接预览 PDF 文件。
    
    Args:
        file_path: PDF 文件的路径
        filename: 下载时显示的文件名
        
    Returns:
        FileResponse 对象，包含 PDF 文件内容和适当的 HTTP 头
        
    Raises:
        Http404: 文件未找到或无法打开时抛出
    """
    try:
        f = open(file_path, 'rb')
        resp = FileResponse(f, content_type='application/pdf')
    except FileNotFoundError:
        raise Http404("文件未找到")
    except Exception as e:
        raise Http404(f"无法打开文件: {e}")
    
    resp['Content-Disposition'] = f'inline; filename="{filename}"'
    resp['X-Frame-Options'] = 'SAMEORIGIN'
    return resp


def create_pdf_preview_view(
    model: Type[models.Model],
    file_field: str = "file",
    filename_property: str = "filename",
    permission_checker: Callable[[HttpRequest, Any], bool] | None = None,
) -> Callable[[HttpRequest, int], FileResponse]:
    """
    创建一个 PDF 预览视图函数的工厂函数
    
    Args:
        model: Django 模型类
        file_field: 文件字段名称，默认 "file"
        filename_property: 文件名属性名称，默认 "filename"
        permission_checker: 可选的权限检查函数，签名为 (request, obj) -> bool
                           返回 True 表示有权限，返回 False 或 None 表示无权限
    
    Returns:
        一个视图函数
    
    用法:
        # 简单用法（任何登录用户都可以预览）
        meeting_pdf_inline = create_pdf_preview_view(Meeting)
        
        # 带权限检查
        def check_traininglog_access(request, obj):
            # 你的权限检查逻辑
            return True
        
        traininglog_pdf_inline = create_pdf_preview_view(
            TrainingLog, 
            permission_checker=check_traininglog_access
        )
    """
    
    def pdf_preview_view(request: HttpRequest, pk: int) -> FileResponse:
        obj = get_object_or_404(model, pk=pk)
        
        # 权限检查
        if permission_checker is not None:
            if not permission_checker(request, obj):
                raise Http404("无法预览该 PDF 文件。")
        
        # 获取文件和文件名
        file_obj = getattr(obj, file_field, None)
        if not file_obj:
            raise Http404("文件不存在。")
        
        filename = getattr(obj, filename_property, None)
        if not filename:
            from pathlib import Path
            filename = Path(file_obj.name).name
        
        return pdf_inline_response(file_obj.path, filename)
    
    return pdf_preview_view
