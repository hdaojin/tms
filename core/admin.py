from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from .models import SiteConfig


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'site_short_name', 'site_author', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return not SiteConfig.objects.exists() 
    
    def changelist_view(self, request, extra_context=None): # type: ignore
        """
        如果已经有配置，则重定向到编辑页面, 避免多一步点击。
        """
        obj = SiteConfig.objects.first()
        if obj:
            return redirect(reverse("admin:core_siteconfig_change", args=(obj.pk,)))
        return super().changelist_view(request, extra_context)
        