from django.contrib import admin

from .models import SkillNode, SkillTree


class SkillNodeInline(admin.TabularInline):
    model = SkillNode
    extra = 0
    fields = ("parent", "code", "name", "node_type", "difficulty", "sort_order", "is_active")
    ordering = ("parent_id", "sort_order", "code")


@admin.register(SkillTree)
class SkillTreeAdmin(admin.ModelAdmin):
    list_display = ("module", "name", "version", "is_current", "created_by", "created_at")
    list_filter = ("is_current", "module__project", "module__module_set")
    search_fields = ("name", "version", "module__code", "module__name", "module__project__name")
    autocomplete_fields = ("module", "created_by")
    inlines = [SkillNodeInline]


@admin.register(SkillNode)
class SkillNodeAdmin(admin.ModelAdmin):
    list_display = ("tree", "parent", "code", "name", "node_type", "difficulty", "sort_order", "is_active")
    list_filter = ("node_type", "is_active", "tree__module__project")
    search_fields = ("code", "name", "description", "tree__name", "tree__module__name")
    autocomplete_fields = ("tree", "parent")
    list_editable = ("sort_order", "is_active")
