from django.contrib import admin
from .models import (
    CompetitionType, Competition, Project, CompetitionProject,
    Module, CompetitionModule, Member, Competitor, 
    CompetitionResult, ModuleResult, CompetitorUser,
    Expert, SkillPosition)


class CompetitionTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'level', 'weight', 'created_at')
    list_filter = ('level',)
    search_fields = ('name', 'code')
    ordering = ('level', 'name')

class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'competition_type', 'start_date', 'location')
    list_filter = ('competition_type', 'start_date')
    search_fields = ('name', 'code')
    autocomplete_fields = ['competition_type']
    ordering = ('-start_date',)

class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'competition_type', 'created_at')
    list_filter = ('competition_type',)
    search_fields = ('name', 'code', 'competition_type__name')
    autocomplete_fields = ['competition_type']
    ordering = ('name',)

class ModuleInline(admin.TabularInline):
    model = Module
    extra = 1

class ProjectAdminWithModules(ProjectAdmin):
    inlines = [ModuleInline]

class CompetitionModuleInline(admin.TabularInline):
    model = CompetitionModule
    extra = 1
    autocomplete_fields = ['module']

class CompetitionProjectAdmin(admin.ModelAdmin):
    list_display = ('competition', 'project', 'description')
    list_filter = ('competition', 'project')
    search_fields = ('competition__name', 'project__name')
    autocomplete_fields = ['competition', 'project']
    inlines = [CompetitionModuleInline]

class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'flag')
    search_fields = ('name', 'code')

class CompetitorAdmin(admin.ModelAdmin):
    list_display = ('name', 'gender', 'member', 'organization', 'get_competition', 'user', 'created_at')
    list_filter = ('member', 'gender', 'competition_project__competition')
    search_fields = ('name', 'member__name', 'user__username', 'competition_project__project__name', 'organization')
    autocomplete_fields = ['member', 'user', 'competition_project']
    
    @admin.display(description='所属赛事', ordering='competition_project__competition')
    def get_competition(self, obj):
        if obj.competition_project:
            return obj.competition_project.competition.name
        return None

class ModuleResultInline(admin.TabularInline):
    model = ModuleResult
    extra = 1
    autocomplete_fields = ['competition_module']

class CompetitionResultAdmin(admin.ModelAdmin):
    list_display = ('competitor', 'get_competition', 'get_project', 'get_total_score', 'rank', 'medal')
    list_filter = ('medal', 'competitor__competition_project__competition', 'competitor__competition_project__project')
    search_fields = ('competitor__name', 'competitor__user__username')
    autocomplete_fields = ['competitor']
    inlines = [ModuleResultInline]

    @admin.display(description='具体赛事', ordering='competitor__competition_project__competition')
    def get_competition(self, obj):
        return obj.competitor.competition_project.competition.name if obj.competitor.competition_project else ''

    @admin.display(description='700分制成绩', ordering='score_700')
    def get_total_score(self, obj):
        return obj.score_700
        
    @admin.display(description='项目', ordering='competitor__competition_project__project')
    def get_project(self, obj):
        return obj.competitor.competition_project.project.name if obj.competitor.competition_project else ''

# Registering models
admin.site.register(CompetitionType, CompetitionTypeAdmin)
admin.site.register(Competition, CompetitionAdmin)
admin.site.register(Project, ProjectAdminWithModules) # 使用带Inline的Admin
admin.site.register(CompetitionProject, CompetitionProjectAdmin)
admin.site.register(Member, MemberAdmin)
admin.site.register(Competitor, CompetitorAdmin)
admin.site.register(CompetitionResult, CompetitionResultAdmin)
# Module 和 CompetitionModule 通常在 Inline 中管理，但也可以单独注册方便调试，视需求而定
class ModuleAdmin(admin.ModelAdmin):
    search_fields = ('name', 'code', 'project__name')
    list_display = ('name', 'code', 'project')
admin.site.register(Module, ModuleAdmin)

class CompetitionModuleAdmin(admin.ModelAdmin):
    search_fields = ('module__name', 'name')
    list_display = ('__str__', 'competition_project')
admin.site.register(CompetitionModule, CompetitionModuleAdmin)

class CompetitorUserAdmin(admin.ModelAdmin):
    search_fields = ('username', 'first_name')
    list_display = ('username', 'first_name', 'email')

    def get_model_perms(self, request):
        """隐藏该模型，不在 Admin 首页显示，但保留搜索功能供 autocomplete 使用"""
        return {}

admin.site.register(CompetitorUser, CompetitorUserAdmin)

class SkillPositionAdmin(admin.ModelAdmin):
    list_display = ('name', 'position_name', 'competition_project', 'organization', 'user')
    list_filter = ('competition_project', 'position_name')
    search_fields = ('name', 'position_name', 'user__username', 'organization')
    autocomplete_fields = ['user', 'competition_project']

class ExpertAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'member', 'competition_project', 'organization')
    list_filter = ('member', 'competition_project')
    search_fields = ('name', 'user__username', 'member__name', 'organization')
    autocomplete_fields = ['user', 'member', 'competition_project']

admin.site.register(SkillPosition, SkillPositionAdmin)
admin.site.register(Expert, ExpertAdmin)

