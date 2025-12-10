from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin, GroupAdmin as DefaultGroupAdmin

from .models import UserProfile, GroupProfile

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = '用户信息'
    verbose_name_plural = '用户信息'
    extra = 1


class CustomUserAdmin(DefaultUserAdmin):
    # 修改列表字段，使用 full_name 作为姓名显示
    list_display = ('username', 'full_name', 'groups_name', 'is_staff', 'is_active', 'date_joined')
    inlines =[UserProfileInline]
    
    def full_name(self, obj):
        return obj.first_name
    full_name.short_description = '姓名' # type: ignore

    def groups_name(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])
    groups_name.short_description = '角色' # type: ignore


class GroupProfileInline(admin.StackedInline):
    model = GroupProfile
    can_delete = False
    verbose_name = '组信息'
    verbose_name_plural = '组信息'
    extra = 1


class CustomGroupAdmin(DefaultGroupAdmin):
    list_display = DefaultGroupAdmin.list_display + ('codename', 'description',)  # type: ignore[assignment]
    inlines = (GroupProfileInline,)

    def codename(self, obj):
        return getattr(getattr(obj, 'profile', None), 'codename', "")
    codename.short_description = '英文标识'  # type: ignore[attr-defined]

    def description(self, obj):
        return getattr(getattr(obj, 'profile', None), 'description', "")
    description.short_description = '描述'  # type: ignore[attr-defined]


# 先注销默认的 UserAdmin 再用自定义的重新注册
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
# admin.site.register(UserProfile)
admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)
