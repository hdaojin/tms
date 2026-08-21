from django.contrib import admin

from .forms import SkillForm, SkillProjectForm
from .models import (
    Skill,
    SkillProject,
    SkillTerm,
    SkillTreeNode,
    SkillTreeVersion,
    SkillWSOSMap,
    TechnicalDomain,
    TechnicalDomainMembership,
    WSOSSection,
    WSOSVersion,
)
from .services import save_skill


@admin.register(SkillProject)
class SkillProjectAdmin(admin.ModelAdmin):
    form = SkillProjectForm
    list_display = ("code", "name", "is_default", "is_active", "order")
    list_filter = ("is_default", "is_active")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    form = SkillForm
    list_display = ("name", "skill_project", "primary_domain", "is_active")
    list_filter = ("skill_project", "primary_domain", "is_active", "is_core", "is_assessable")
    search_fields = ("name", "description", "terms__term")

    def save_model(self, request, obj, form, change):
        save_skill(
            skill=obj,
            aliases=form._split_text(form.cleaned_data.get("aliases_text")),
            related_domains=form.cleaned_data.get("related_domains", ()),
            preserve_old_name=form.cleaned_data.get("preserve_old_name", False),
            old_name=form.old_name,
        )


@admin.register(SkillTerm)
class SkillTermAdmin(admin.ModelAdmin):
    list_display = ("term", "kind", "skill", "skill_project")
    list_filter = ("kind", "skill_project")
    search_fields = ("term", "normalized_term", "skill__name")
    readonly_fields = ("skill_project", "skill", "term", "normalized_term", "kind", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(
    [
        TechnicalDomain,
        TechnicalDomainMembership,
        SkillTreeVersion,
        WSOSVersion,
        WSOSSection,
        SkillWSOSMap,
    ]
)


@admin.register(SkillTreeNode)
class SkillTreeNodeAdmin(admin.ModelAdmin):
    list_display = ("tree_version", "technical_domain", "skill", "parent", "order")
    list_filter = ("tree_version", "technical_domain")
    search_fields = ("skill__name",)
    readonly_fields = (
        "tree_version",
        "technical_domain",
        "skill",
        "parent",
        "order",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
