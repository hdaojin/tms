from django.contrib import admin
from django.core.cache import cache

from .models import Menu, MenuItem
from .forms import MenuItemForm


class MenuItemInline(admin.TabularInline):
    model = MenuItem.menus.through
    extra = 0
    fields = ('menuitem', 'menu')

@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'display_locations')
    inlines = [MenuItemInline]
    actions = ['clear_all_caches']
    
    def clear_menu_cache(self, menu):
        """清除指定菜单的缓存"""
        cache_key = f"nav.items.{menu.id}"
        cache.delete(cache_key)
    
    def clear_all_caches(self, request, queryset):
        """批量清除所选菜单的缓存"""
        count = 0
        for menu in queryset:
            self.clear_menu_cache(menu)
            count += 1
        self.message_user(request, f"已清除 {count} 个菜单的缓存。")
    clear_all_caches.short_description = "清除选中菜单的缓存"  # type: ignore
    
    def save_model(self, request, obj, form, change):
        """保存菜单时清除缓存"""
        super().save_model(request, obj, form, change)
        self.clear_menu_cache(obj)
        self.message_user(request, f"菜单 '{obj.name}' 已保存，缓存已清除。")
    
    def save_related(self, request, form, formsets, change):
        """保存相关对象（包括内联编辑的菜单项）时清除缓存"""
        super().save_related(request, form, formsets, change)
        self.clear_menu_cache(form.instance)
    
    def delete_model(self, request, obj):
        """删除菜单时清除缓存"""
        menu_name = obj.name
        self.clear_menu_cache(obj)
        super().delete_model(request, obj)
        self.message_user(request, f"菜单 '{menu_name}' 已删除，缓存已清除。")

    # 显示位置（MultiSelectField 的友好显示）
    def display_locations(self, obj):
        # MultiSelectField 提供 get_FOO_display()，其返回逗号分隔的可读标签
        try:
            return obj.get_locations_display()
        except Exception:  # 回退
            val = obj.locations
            if isinstance(val, (list, tuple)):
                return ", ".join(val)
            return val
    display_locations.short_description = "显示位置"  # type: ignore


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    form = MenuItemForm
    list_display = ('name', 'get_menus', 'parent', 'order', 'is_visible', 'required_perms', 'named_url', 'flatpage', 'external_url', 'target_blank')
    list_filter = ('menus',)
    search_fields = ('name', 'menus__name', 'named_url', 'external_url')
    filter_horizontal = ('menus',)
    actions = ['clear_related_caches', 'refresh_named_url_cache']
    # 分组字段显示
    fieldsets = (
        (None, {
            'fields': ('name',  'menus', 'parent', 'order', 'is_visible')
        }),
        ('链接配置 (优先级: 命名路由 > FlatPage > 外部链接)', {
            'fields': ('icon', 'required_perms', 'named_url', 'url_kwargs', 'url_query', 'flatpage', 'external_url'),
        }),
        ('前端显示', {
            'classes': ('collapse',),
            'fields': ('target_blank', 'css_classes', 'htmx_attrs'),
        }),
        ('存留时间', {
            'classes': ('collapse',),
            'fields': ('start_at', 'end_at'),
            'description': '控制菜单项持续存留时间。'
        }),
    )
    
    def get_menus(self, obj):
        return ", ".join([menu.name for menu in obj.menus.all()])
    get_menus.short_description = '菜单组'  # type: ignore
    
    def clear_related_menu_caches(self, menuitem):
        """清除菜单项相关的所有菜单缓存"""
        for menu in menuitem.menus.all():
            cache_key = f"nav.items.{menu.id}"
            cache.delete(cache_key)
    
    def clear_related_caches(self, request, queryset):
        """批量清除所选菜单项相关的菜单缓存"""
        cache_count = 0
        for menuitem in queryset:
            menu_count = menuitem.menus.count()
            self.clear_related_menu_caches(menuitem)
            cache_count += menu_count
        self.message_user(request, f"已清除 {cache_count} 个相关菜单的缓存。")
    clear_related_caches.short_description = "清除选中菜单项相关的缓存"  # type: ignore
    
    def save_model(self, request, obj, form, change):
        """保存菜单项时清除相关菜单缓存"""
        # 如果是编辑现有对象，先获取原来的菜单关联
        old_menus = set()
        if change and obj.pk:
            old_menus = set(MenuItem.objects.get(pk=obj.pk).menus.all())
        
        super().save_model(request, obj, form, change)
        
        # 清除新的菜单缓存
        self.clear_related_menu_caches(obj)
        
        # 如果是编辑，还需要清除原来菜单的缓存
        if change:
            for menu in old_menus:
                cache_key = f"nav.items.{menu.id}"
                cache.delete(cache_key)
        
        self.message_user(request, f"菜单项 '{obj.name}' 已保存，相关菜单缓存已清除。")
    
    def delete_model(self, request, obj):
        """删除菜单项时清除相关菜单缓存"""
        menuitem_name = obj.name
        self.clear_related_menu_caches(obj)
        super().delete_model(request, obj)
        self.message_user(request, f"菜单项 '{menuitem_name}' 已删除，相关菜单缓存已清除。")

    # 自定义动作：刷新命名路由缓存
    def refresh_named_url_cache(self, request, queryset):  # pylint: disable=unused-argument
        from . import utils as nav_utils
        nav_utils.refresh_named_url_choices()
        total = len(nav_utils.get_named_url_choices())
        self.message_user(request, f"命名路由缓存已刷新，当前可选 URL 数量：{total}")
    refresh_named_url_cache.short_description = "刷新命名路由缓存"  # type: ignore

