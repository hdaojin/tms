from django.contrib import admin

# Register your models here.
from .models import Competition, Examination, ExamScore
from .forms import ExamScoreForm


class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'weight', 'start_date', 'end_date', 'location', 'organizer', 'is_team_event')
    list_filter = ('level', 'is_team_event', 'start_date')
    search_fields = ('name', 'level', 'organizer', 'location')
    ordering = ('-start_date', 'name', 'level')

class ExaminationAdmin(admin.ModelAdmin):
    form = ExamScoreForm
    list_display = ('name', 'start_date', 'end_date', 'location', 'organizer', 'is_team_event')
    list_filter = ('is_team_event', 'start_date')
    search_fields = ('name', 'organizer', 'location')
    ordering = ('-start_date', 'name')

class ExamScoreAdmin(admin.ModelAdmin):
    list_display = ('examination', 'model', 'user', 'score', 'created_at')
    list_filter = ('examination', 'model')
    search_fields = ('user__username', 'user__first_name', 'model__code', 'examination__name')
    ordering = ('-examination__start_date', 'user__username', 'model__code')

admin.site.register(Competition, CompetitionAdmin)
admin.site.register(Examination, ExaminationAdmin)
admin.site.register(ExamScore, ExamScoreAdmin)
