from django.contrib import admin

# Register your modules here.
from .models import Competition, Project, Module


class CometionAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'weight', 'created_at', 'updated_at')
    list_filter = ('level',)
    search_fields = ('name', 'level')
    ordering = ('level', 'name', )


class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'competition', 'created_at', 'updated_at')
    list_filter = ('competition',)
    search_fields = ('name', 'competition__name')
    ordering = ('name',)


class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'code', 'created_at', 'updated_at')
    list_filter = ('project',)
    search_fields = ('name', 'project__name', 'code')
    ordering = ('code',)

admin.site.register(Competition, CometionAdmin)
admin.site.register(Project, ProjectAdmin)
admin.site.register(Module, ModuleAdmin)


# from .models import Competition, Examination, ExamScore


# class CompetitionAdmin(admin.ModelAdmin):
#     list_display = ('name', 'level', 'weight', 'start_date', 'end_date', 'location', 'organizer', 'is_team_event')
#     list_filter = ('level', 'is_team_event', 'start_date')
#     search_fields = ('name', 'level', 'organizer', 'location')
#     ordering = ('-start_date', 'name', 'level')

# class ExaminationAdmin(admin.ModelAdmin):
#     list_display = ('name', 'start_date', 'end_date', 'location', 'organizer', 'is_team_event')
#     list_filter = ('is_team_event', 'start_date')
#     search_fields = ('name', 'organizer', 'location')
#     ordering = ('-start_date', 'name')

# class ExamScoreAdmin(admin.ModelAdmin):
#     list_display = ('examination', 'module', 'user', 'score', 'created_at')
#     list_filter = ('examination', 'module')
#     search_fields = ('user__username', 'user__first_name', 'module__code', 'examination__name')
#     ordering = ('-examination__start_date', 'user__username', 'module__code')

# admin.site.register(Competition, CompetitionAdmin)
# admin.site.register(Examination, ExaminationAdmin)
# admin.site.register(ExamScore, ExamScoreAdmin)
