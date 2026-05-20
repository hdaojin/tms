from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin, GroupAdmin as DefaultGroupAdmin
from django.utils.translation import gettext_lazy as _

from behaviors.services import discard_conduct_summary_delete_permission
from .admin_forms import GroupPermissionBundleAdminForm, UserPermissionBundleAdminForm
from .models import UserProfile, GroupProfile
from .services.permission_bundles import sync_group_permission_bundles, sync_user_permission_bundles

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = '用户信息'
    verbose_name_plural = '用户信息'
    extra = 1
    exclude = ('selected_permission_bundles',)


class CustomUserAdmin(DefaultUserAdmin):
    # 修改列表字段，使用 full_name 作为姓名显示
    list_display = ('username', 'full_name', 'groups_name', 'is_staff', 'is_active', 'date_joined')
    inlines =[UserProfileInline]
    form = UserPermissionBundleAdminForm
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'selected_permission_bundles', 'user_permissions')}),
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
        # 允许级联删除奖惩汇总（单独删除仍被 ConductSummaryAdmin 拦截）
        discard_conduct_summary_delete_permission(perms_needed)
        return deleted_objects, model_count, perms_needed, protected

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if 'selected_permission_bundles' not in form.cleaned_data:
            return
        sync_user_permission_bundles(
            form.instance,
            form.cleaned_data.get('selected_permission_bundles'),
            form.cleaned_data.get('user_permissions'),
        )


class GroupProfileInline(admin.StackedInline):
    model = GroupProfile
    can_delete = False
    verbose_name = '组信息'
    verbose_name_plural = '组信息'
    extra = 1
    exclude = ('selected_permission_bundles',)


class CustomGroupAdmin(DefaultGroupAdmin):
    list_display = DefaultGroupAdmin.list_display + ('codename', 'description',)  # type: ignore[assignment]
    inlines = (GroupProfileInline,)
    form = GroupPermissionBundleAdminForm
    fieldsets = (
        (None, {'fields': ('name', 'selected_permission_bundles', 'permissions')}),
    )

    def codename(self, obj):
        return getattr(getattr(obj, 'profile', None), 'codename', "")
    codename.short_description = '英文标识'  # type: ignore[attr-defined]

    def description(self, obj):
        return getattr(getattr(obj, 'profile', None), 'description', "")
    description.short_description = '描述'  # type: ignore[attr-defined]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        sync_group_permission_bundles(
            form.instance,
            form.cleaned_data.get('selected_permission_bundles'),
            form.cleaned_data.get('permissions'),
        )


# 先注销默认的 UserAdmin 再用自定义的重新注册
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
# admin.site.register(UserProfile)
admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)
