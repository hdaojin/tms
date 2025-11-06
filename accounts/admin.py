from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from .models import UserProfile

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name = '用户信息'
    verbose_name_plural = '用户信息'


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


    # # 修改详情页展示字段，移除 last_name
    # fieldsets = (
    #     (None, {'fields': ('username', 'password')}),
    #     ('个人信息', {'fields': ('first_name', 'email')}),
    #     ('权限', {'fields': ('is_active', 'is_staff', 'is_superuser',
    #                          'groups', 'user_permissions')}),
    #     ('重要日期', {'fields': ('last_login', 'date_joined')}),
    # )

    # # 添加用户时移除 last_name 字段
    # add_fieldsets = (
    #     (None, {
    #         'classes': ('wide',),
    #         'fields': ('username', 'first_name', 'password1', 'password2'),
    #     }),
    # )

    # # 搜索时仅包含需要显示的字段
    # search_fields = ('username', 'first_name', 'email')


# 先注销默认的 UserAdmin 再用自定义的重新注册
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
# admin.site.register(UserProfile)
