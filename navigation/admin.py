from django.contrib import admin
from django.core.cache import cache

from .models import Menu, MenuItem


class MenuItemInline(admin.TabularInline):
    model = MenuItem.menus.through
    extra = 0
    fields = ('menuitem', 'menu')

@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'locations')
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


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_menus', 'parent', 'order', 'is_visible')
    list_filter = ('menus',)
    search_fields = ('name', 'menus__name', 'named_url', 'external_url')
    filter_horizontal = ('menus',)
    actions = ['clear_related_caches']
    
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