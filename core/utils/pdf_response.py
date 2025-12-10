# core/utils/pdf_response.py
from django.http import FileResponse, Http404


def pdf_inline_response(file_path, filename):
    """
    返回一个PDF文件的inline响应，适合在浏览器中直接预览PDF文件。
    
    参数:
    - file_path: PDF文件的路径
    - filename: 下载时显示的文件名
    返回:
    - FileResponse对象，包含PDF文件内容和适当的HTTP头
    """
    try:
        f = open(file_path, 'rb')
        resp = FileResponse(f, content_type='application/pdf')
    except FileNotFoundError:
        raise Http404("文件未找到")
    except Exception as e:
        raise Http404(f"无法打开文件: {e}")
    
    resp['Content-Disposition'] = f'inline; filename="{filename}"'
    resp["X-Frame-Options"] = "SAMEORIGIN"
    resp["Content-Security-Policy"] = "frame-ancestors \'self\';"
    return resp