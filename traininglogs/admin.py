from django.contrib import admin
from .models import TrainingLog


# Register your models here.
class TrainingLogAdmin(admin.ModelAdmin):
    list_display = ('module', 'task', 'display_filename', 'training_date', 'uploaded_by', 'uploaded_at')
    list_filter = ('module', 'training_date', 'uploaded_by')
    search_fields = ('module__name', 'task', 'training_date', 'uploaded_by__username')
    date_hierarchy = 'training_date'
    ordering = ('-training_date',)
    readonly_fields = ('uploaded_at', )

    def display_filename(self, obj):
        return obj.filename
    
    display_filename.short_description = '文件名'  # type: ignore[attr-defined]
    

# 向默认admin站点注册
admin.site.register(TrainingLog, TrainingLogAdmin)
