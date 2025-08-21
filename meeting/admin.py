from django.contrib import admin
from .models import Meeting

# Register your models here.

class MeetingAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'filename', 'uploaded_by', 'uploaded_at')
    search_fields = ('title', 'filename', 'uploaded_by__username')
    list_filter = ('date', 'uploaded_by')
    date_hierarchy = 'date'
    ordering = ('-date',)

# 向默认admin站点注册
admin.site.register(Meeting, MeetingAdmin)