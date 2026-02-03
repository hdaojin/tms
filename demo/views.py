from django.views.generic import TemplateView
from django.contrib import messages
from django.conf import settings
from django.http import Http404

from core.utils.mixins import TitleMixin


class DemoBaseView(TemplateView):
    """
    Demo 视图基类
    确保只在开发模式下可访问
    """
    def dispatch(self, request, *args, **kwargs):
        if not settings.DEBUG:
            raise Http404("Demo pages are only available in development mode")
        return super().dispatch(request, *args, **kwargs)


class FileUploadDemoView(TitleMixin, DemoBaseView):
    """文件上传组件演示视图"""
    template_name = "demo/file_upload_demo.html"
    title = "文件上传组件演示"
    title_icon = "icon-[tabler--upload]"
    
    def post(self, request, *args, **kwargs):
        """处理文件上传"""
        # 获取所有上传的文件
        uploaded_files = []
        for key in request.FILES:
            files = request.FILES.getlist(key)
            for file in files:
                uploaded_files.append(f"{key}: {file.name} ({file.size} bytes)")
        
        if uploaded_files:
            messages.success(
                request, 
                f"成功接收到 {len(uploaded_files)} 个文件：<br>" + "<br>".join(uploaded_files)
            )
        else:
            messages.info(request, "未选择任何文件")
        
        return self.get(request, *args, **kwargs)


class ComponentsDemoView(TitleMixin, DemoBaseView):
    """组件演示列表页"""
    template_name = "demo/components_list.html"
    title = "组件演示中心"
    title_icon = "icon-[tabler--components]"
