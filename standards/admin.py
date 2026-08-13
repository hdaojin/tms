from django.contrib import admin
from django.db import transaction

from .models import CapabilityDomain, SkillNode, SkillProject, SkillTreeVersion
from .services import set_current_skill_tree_version


@admin.register(SkillProject)
class SkillProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "short_name", "is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "short_name")


@admin.register(CapabilityDomain)
class CapabilityDomainAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "skill_project", "is_active", "order")
    list_filter = ("skill_project", "is_active")
    search_fields = ("code", "name", "skill_project__name")


@admin.register(SkillTreeVersion)
class SkillTreeVersionAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "skill_project", "is_current", "created_at")
    list_filter = ("skill_project", "is_current")
    search_fields = ("name", "version", "skill_project__name")

    def save_model(self, request, obj, form, change):
        requested_current = obj.is_current
        if requested_current:
            obj.is_current = False
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if requested_current:
                set_current_skill_tree_version(obj)


@admin.register(SkillNode)
class SkillNodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "node_type", "capability_domain", "tree_version", "parent", "is_active")
    list_filter = ("node_type", "tree_version", "capability_domain", "is_active")
    search_fields = ("code", "name", "description")
