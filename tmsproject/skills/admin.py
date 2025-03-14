from django.contrib import admin

# Register your models here.

from .models import Module, Skill


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'description')
    search_fields = ('code', 'name')


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('skill_point', 'exam_point', 'detail_content', 'competition', 'module', 'score')
    search_fields = ('skill_point', 'exam_point', 'detail_content')