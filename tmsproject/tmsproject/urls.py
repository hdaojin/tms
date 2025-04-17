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

admin.site.site_header = "TMS 管理后台"
admin.site.site_title = "TMS 管理后台"
admin.site.index_title = "欢迎来到 TMS 管理后台"

urlpatterns = [
    path("admin/", admin.site.urls, name="admin"),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("articles/", include("articles.urls", namespace="articles")),
    path("traininglogs/", include("traininglogs.urls", namespace="traininglogs")),
    path("", include("pages.urls", namespace="pages")), 
]

# 在开发环境中添加媒体文件的URL配置
# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)