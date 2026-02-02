# core/utils/upload.py
"""
文件上传处理工具模块
提供 HTMX 文件上传的 Mixin 和辅助函数
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.http import JsonResponse, HttpResponse

from core.constants import DEFAULT_UPLOAD_MAX_SIZE_MB


class FileUploadMixin:
    """
    文件上传处理 Mixin，用于视图类
    
    使用示例：
    ```python
    class MyUploadView(FileUploadMixin, View):
        upload_field_name = 'file'
        allowed_extensions = ['pdf', 'doc', 'docx']
        max_size_mb = 50
        
        def handle_uploaded_file(self, file, request):
            # 处理上传的文件
            instance = MyModel.objects.create(file=file, user=request.user)
            return instance
    ```
    """
    
    # 配置项（子类可覆盖）
    upload_field_name: str = 'file'
    allowed_extensions: list[str] | None = None
    max_size_mb: int = DEFAULT_UPLOAD_MAX_SIZE_MB
    
    def validate_file(self, file: UploadedFile) -> list[str]:
        """
        验证上传的文件，返回错误列表
        
        Args:
            file: 上传的文件对象
            
        Returns:
            错误消息列表，空列表表示验证通过
        """
        errors = []
        
        # 检查文件大小
        if file.size > self.max_size_mb * 1024 * 1024:
            errors.append(f"文件大小不能超过 {self.max_size_mb}MB")
        
        # 检查文件扩展名
        if self.allowed_extensions:
            ext = Path(file.name).suffix.lower().lstrip('.')
            if ext not in self.allowed_extensions:
                allowed = ', '.join(self.allowed_extensions)
                errors.append(f"不支持的文件格式，仅支持：{allowed}")
        
        return errors
    
    def handle_uploaded_file(self, file: UploadedFile, request) -> Any:
        """
        处理上传的文件（子类必须实现）
        
        Args:
            file: 验证通过的文件对象
            request: HTTP 请求对象
            
        Returns:
            处理结果（如模型实例）
        """
        raise NotImplementedError("子类必须实现 handle_uploaded_file 方法")
    
    def get_success_response(self, result: Any, request) -> HttpResponse:
        """
        返回上传成功的响应
        
        Args:
            result: handle_uploaded_file 的返回值
            request: HTTP 请求对象
            
        Returns:
            HTTP 响应对象
        """
        # 检查是否为 HTMX 请求
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '<div class="alert alert-success">'
                '<span class="icon-[tabler--check] size-5"></span>'
                '<span>文件上传成功！</span>'
                '</div>'
            )
        return JsonResponse({'success': True, 'message': '文件上传成功'})
    
    def get_error_response(self, errors: list[str], request) -> HttpResponse:
        """
        返回上传失败的响应
        
        Args:
            errors: 错误消息列表
            request: HTTP 请求对象
            
        Returns:
            HTTP 响应对象
        """
        if request.headers.get('HX-Request'):
            error_html = ''.join(f'<li>{e}</li>' for e in errors)
            return HttpResponse(
                f'<div class="alert alert-error">'
                f'<span class="icon-[tabler--alert-circle] size-5"></span>'
                f'<ul class="list-disc list-inside">{error_html}</ul>'
                f'</div>',
                status=400
            )
        return JsonResponse({'success': False, 'errors': errors}, status=400)
    
    def post(self, request, *args, **kwargs):
        """处理 POST 请求（文件上传）"""
        files = request.FILES.getlist(self.upload_field_name)
        
        if not files:
            return self.get_error_response(['请选择要上传的文件'], request)
        
        all_errors = []
        results = []
        
        for file in files:
            # 验证文件
            errors = self.validate_file(file)
            if errors:
                all_errors.extend([f"「{file.name}」: {e}" for e in errors])
                continue
            
            try:
                result = self.handle_uploaded_file(file, request)
                results.append(result)
            except ValidationError as e:
                all_errors.append(f"「{file.name}」: {e.message}")
            except Exception as e:
                all_errors.append(f"「{file.name}」: 上传失败 - {str(e)}")
        
        if all_errors and not results:
            return self.get_error_response(all_errors, request)
        
        return self.get_success_response(results, request)


def validate_upload_file(
    file: UploadedFile,
    allowed_extensions: list[str] | None = None,
    max_size_mb: int = DEFAULT_UPLOAD_MAX_SIZE_MB,
) -> None:
    """
    验证上传文件的辅助函数
    
    Args:
        file: 上传的文件对象
        allowed_extensions: 允许的扩展名列表
        max_size_mb: 最大文件大小（MB）
        
    Raises:
        ValidationError: 验证失败时抛出
    """
    # 检查文件大小
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"文件大小不能超过 {max_size_mb}MB")
    
    # 检查文件扩展名
    if allowed_extensions:
        ext = Path(file.name).suffix.lower().lstrip('.')
        if ext not in allowed_extensions:
            allowed = ', '.join(allowed_extensions)
            raise ValidationError(f"不支持的文件格式，仅支持：{allowed}")


def get_file_icon_class(filename: str) -> str:
    """
    根据文件名获取对应的 Iconify 图标类
    
    Args:
        filename: 文件名
        
    Returns:
        Iconify 图标类名
    """
    ext = Path(filename).suffix.lower().lstrip('.')
    
    icons = {
        'pdf': 'icon-[tabler--file-type-pdf]',
        'doc': 'icon-[tabler--file-type-doc]',
        'docx': 'icon-[tabler--file-type-docx]',
        'xls': 'icon-[tabler--file-type-xls]',
        'xlsx': 'icon-[tabler--file-type-xls]',
        'ppt': 'icon-[tabler--file-type-ppt]',
        'pptx': 'icon-[tabler--file-type-ppt]',
        'txt': 'icon-[tabler--file-type-txt]',
        'csv': 'icon-[tabler--file-type-csv]',
        'zip': 'icon-[tabler--file-zip]',
        'rar': 'icon-[tabler--file-zip]',
        '7z': 'icon-[tabler--file-zip]',
        'tar': 'icon-[tabler--file-zip]',
        'gz': 'icon-[tabler--file-zip]',
        'jpg': 'icon-[tabler--photo]',
        'jpeg': 'icon-[tabler--photo]',
        'png': 'icon-[tabler--photo]',
        'gif': 'icon-[tabler--photo]',
        'webp': 'icon-[tabler--photo]',
        'mp4': 'icon-[tabler--video]',
        'avi': 'icon-[tabler--video]',
        'mkv': 'icon-[tabler--video]',
        'mp3': 'icon-[tabler--music]',
        'wav': 'icon-[tabler--music]',
    }
    
    return icons.get(ext, 'icon-[tabler--file]')


def is_image_file(filename: str) -> bool:
    """
    判断文件是否为图片
    
    Args:
        filename: 文件名
        
    Returns:
        是否为图片文件
    """
    ext = Path(filename).suffix.lower().lstrip('.')
    return ext in {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'}


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        格式化后的大小字符串
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.2f} MB"
    else:
        return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"
