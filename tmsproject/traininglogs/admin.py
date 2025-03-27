from django.contrib import admin
from .models import TrainingLog


# Register your models here.
class TrainingLogAdmin(admin.ModelAdmin):
    list_display = ('filename', 'module', 'task', 'training_date', 'uploaded_by', 'uploaded_at')
    search_fields = ('filename', 'module', 'task', 'training_date', 'uploaded_by')
    list_filter = ('module', 'training_date', 'uploaded_by')
    date_hierarchy = 'training_date'
    ordering = ('-training_date',)
    

# 向默认admin站点注册
admin.site.register(TrainingLog, TrainingLogAdmin)
