# navigation/admin.py
from django.contrib import admin
from .models import Menu, MenuItem
from .forms import MenuItemForm


# Menu 的内联菜单项
class MenuItemInline(admin.TabularInline):
    model = MenuItem.menus.through
    extra = 0
    verbose_name = "菜单项"
    verbose_name_plural = "菜单项"
    autocomplete_fields = ("menuitem",)


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "display_locations")
    list_filter = ("is_active", "locations")
    search_fields = ("name", "slug", "description")
    inlines = [MenuItemInline]

    @admin.display(description="显示位置")
    def display_locations(self, obj):
        if not obj.locations:
            return "(未设置)"
        # multiselectfield 提供 get_FOO_display 但为了显式控制分隔符
        choices_map = dict(obj._meta.get_field("locations").choices)
        labels = [choices_map.get(v, v) for v in obj.locations]
        return ", ".join(labels)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    form = MenuItemForm
    list_display = ("name", "icon", "display_url", "parent", "display_menus", "order", "display_required_perms",  "perm_match_all",  "login_required", "is_visible", "is_group_header", )
    list_filter = ("is_visible", "login_required", "perm_match_all", "is_group_header", "menus")
    search_fields = ("name", "named_url", "external_url")
    filter_horizontal = ("menus",)
    fieldsets = (
        (None, {"fields": ("name", "menus", "order", "parent", "icon", "is_visible", "is_group_header")} ),
        ("指向链接（选择一种方式：命名路由、简单页面或外部链接）", {"fields": ("named_url", "url_kwargs", "url_query", "flatpage", "external_url")} ),
        ("可见与权限", {"fields": ("login_required", "permissions", "perm_match_all")} ),
        ("显示时间窗口", {"fields": ("start_at", "end_at"), "classes": ["collapse"]} ),
        ("前端属性", {"fields": ("target_blank", "css_classes", "htmx_attrs"), "classes": ["collapse"]} ),
    )

    @admin.display(description="URL")
    def display_url(self, obj):
        if obj.is_group_header:
            return "(分组标题)"
        if obj.external_url:
            return obj.external_url
        if obj.named_url:
            desc = obj.named_url
            if obj.url_kwargs:
                desc += f" {obj.url_kwargs}"
            if obj.url_query:
                desc += f"?{obj.url_query}"
            return desc
        if obj.flatpage:
            return f"简单页面: {obj.flatpage.get_absolute_url()}"
        return "(无链接)"

    @admin.display(description="所需权限")
    def display_required_perms(self, obj):
        perms_qs = obj.permissions.all()
        if perms_qs.exists():
            return ", ".join(f"{p.content_type.app_label}.{p.codename}" for p in perms_qs)
        return "不限制"

    @admin.display(description="所属菜单组")
    def display_menus(self, obj):
        names = [m.name for m in obj.menus.all()]
        if not names:
            return "(未关联)"
        return ", ".join(names)

    def get_queryset(self, request):  # 预取减少 N+1
        qs = super().get_queryset(request)
        return qs.prefetch_related('menus')