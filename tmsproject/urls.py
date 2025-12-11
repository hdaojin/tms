"""
URL configuration for tmsproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_not_required  # type: ignore
# from django.contrib.flatpages import views as flatpage_views

from core.home.views import HomeView

admin.site.site_header = "TMS 管理后台"
admin.site.site_title = "TMS 管理后台"
admin.site.index_title = "欢迎来到 TMS 管理后台"

urlpatterns = [
    path("admin/", admin.site.urls),
    # path("pages/", include("django.contrib.flatpages.urls")),  # 内置的 flatpages 应用
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("samba/", include("samba.urls", namespace="samba")),
    path("articles/", include("articles.urls", namespace="articles")),
    path("traininglogs/", include("traininglogs.urls", namespace="traininglogs")),
    path("meeting/", include("meeting.urls", namespace="meeting")),
    path("notices/", include("notices.urls", namespace="notices")),
    path("notes/", include("notes.urls", namespace="notes")),
    # path("competitions/", include("competitions.urls", namespace="competitions")),
    path("", login_not_required(HomeView.as_view()), name="home"),
]

# 在开发环境中添加静态文件和媒体文件的URL配置
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=getattr(settings, 'STATICFILES_DIRS', [settings.BASE_DIR / 'static'])[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=getattr(settings, 'MEDIA_ROOT', None))

# # Flatpages 全局兜底（不要 pages 前缀）：必须放在最后，避免吞掉其它路由与静态路由
# urlpatterns += [
#     path("<path:url>", login_not_required(flatpage_views.flatpage), name="flatpage"),
# ]