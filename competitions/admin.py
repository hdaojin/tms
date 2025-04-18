from django.contrib import admin

# Register your models here.
from .models import Competition, CompetitionDetail, CompetitionTeam, CompetionResult, CompetitionTeamRelation


class CompetitionDetailInline(admin.StackedInline):
    model = CompetitionDetail
    can_delete = False
    verbose_name = '竞赛详情'
    verbose_name_plural = '竞赛详情'


class CompetitionTeamInline(admin.TabularInline):
    model = CompetitionTeam
    extra = 1
    verbose_name = '参赛队'
    verbose_name_plural = '参赛队'


class CompetitionResultInline(admin.StackedInline):
    model = CompetionResult
    can_delete = False
    verbose_name = '竞赛结果'
    verbose_name_plural = '竞赛结果'


class CompetitionTeamRelationInline(admin.TabularInline):
    model = CompetitionTeamRelation
    extra = 1
    verbose_name = '参赛队'
    verbose_name_plural = '参赛队'


class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'level')
    inlines = [CompetitionDetailInline, CompetitionTeamRelationInline, CompetitionResultInline]
    search_fields = ('name', 'level')

class CompetitionTeamRelationAdmin(admin.ModelAdmin):
    list_display = ('competition', 'team')


admin.site.register(Competition, CompetitionAdmin)
admin.site.register(CompetitionTeam)
admin.site.register(CompetitionTeamRelation, CompetitionTeamRelationAdmin)