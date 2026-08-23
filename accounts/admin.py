from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin, GroupAdmin as DefaultGroupAdmin
from django.utils.translation import gettext_lazy as _

from core.utils.admin_deletion import discard_registered_delete_permissions
from standards.models import TechnicalDomainGroupScope
from .admin_forms import GroupPermissionBundleAdminForm, UserPermissionBundleAdminForm
from .models import UserProfile, GroupProfile
from .services.permission_assignments import (
    sync_group_permission_assignments,
    sync_user_permission_assignments,
)
from .services.users import fill_leave_date_on_deactivation

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = '用户信息'
    verbose_name_plural = '用户信息'
    extra = 1
    exclude = ('selected_permission_bundles', 'explicit_permissions')


class CustomUserAdmin(DefaultUserAdmin):
    # 修改列表字段，使用 full_name 作为姓名显示
    list_display = ('username', 'full_name', 'groups_name', 'is_staff', 'is_active', 'date_joined')
    inlines =[UserProfileInline]
    form = UserPermissionBundleAdminForm
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'selected_permission_bundles')}),
        ('高级：额外原生 Django 权限', {'fields': ('explicit_permissions',), 'classes': ('collapse',)}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    def full_name(self, obj):
        """显示姓名（姓+名），无则显示用户名"""
        full_name = f"{obj.last_name}{obj.first_name}".strip()
        return full_name or obj.username
    full_name.short_description = '姓名' # type: ignore

    def groups_name(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])
    groups_name.short_description = '角色' # type: ignore

    def get_deleted_objects(self, objs, request):
        deleted_objects, model_count, perms_needed, protected = (
            super().get_deleted_objects(objs, request)
        )
        discard_registered_delete_permissions(objs, perms_needed)
        return deleted_objects, model_count, perms_needed, protected

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if (
            change
            and 'is_active' in form.changed_data
            and not form.cleaned_data.get('is_active')
        ):
            fill_leave_date_on_deactivation(
                form.instance,
                previous_is_active=True,
            )
        if 'selected_permission_bundles' not in form.cleaned_data:
            return
        sync_user_permission_assignments(
            form.instance,
            form.cleaned_data.get('selected_permission_bundles'),
            form.cleaned_data.get('explicit_permissions'),
        )


class GroupProfileInline(admin.StackedInline):
    model = GroupProfile
    can_delete = False
    verbose_name = '组信息'
    verbose_name_plural = '组信息'
    extra = 1
    exclude = ('selected_permission_bundles', 'explicit_permissions')


class TechnicalDomainGroupScopeInline(admin.TabularInline):
    model = TechnicalDomainGroupScope
    fields = ('technical_domain',)
    extra = 1
    verbose_name = '技术领域范围'
    verbose_name_plural = '技术领域范围'


class CustomGroupAdmin(DefaultGroupAdmin):
    list_display = DefaultGroupAdmin.list_display + ('codename', 'description',)  # type: ignore[assignment]
    inlines = (GroupProfileInline, TechnicalDomainGroupScopeInline)
    form = GroupPermissionBundleAdminForm
    fieldsets = (
        ('基本信息', {'fields': ('name',)}),
        ('业务权限包', {'fields': ('selected_permission_bundles',)}),
        ('高级：额外原生 Django 权限', {'fields': ('explicit_permissions',), 'classes': ('collapse',)}),
    )

    def codename(self, obj):
        return getattr(getattr(obj, 'profile', None), 'codename', "")
    codename.short_description = '英文标识'  # type: ignore[attr-defined]

    def description(self, obj):
        return getattr(getattr(obj, 'profile', None), 'description', "")
    description.short_description = '描述'  # type: ignore[attr-defined]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        sync_group_permission_assignments(
            form.instance,
            form.cleaned_data.get('selected_permission_bundles'),
            form.cleaned_data.get('explicit_permissions'),
        )


# 先注销默认的 UserAdmin 再用自定义的重新注册
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
# admin.site.register(UserProfile)
admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)
