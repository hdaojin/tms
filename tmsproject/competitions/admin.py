from django.contrib import admin

# Register your models here.
from .models import Competition

class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'end_time', 'description')
    search_fields = ('name', 'description')


admin.site.register(Competition)