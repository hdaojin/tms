from django.contrib import admin
from .models import TrainingLog


# Register your models here.
class TrainingLogAdmin(admin.ModelAdmin):
    list_display = ('task', 'training_cycle', 'module', 'display_filename', 'training_date', 'uploaded_by', 'uploaded_at')
    list_filter = ('training_cycle', 'module', 'training_date', 'uploaded_by')
    search_fields = ('task', 'training_cycle__name', 'module__name', 'training_date', 'uploaded_by__username')
    autocomplete_fields = ('training_cycle', 'module', 'uploaded_by')
    list_select_related = ('training_cycle', 'module', 'uploaded_by')
    date_hierarchy = 'training_date'
    ordering = ('-training_date',)
    readonly_fields = ('uploaded_at', )

    def display_filename(self, obj):
        return obj.filename
    
    display_filename.short_description = '文件名'  # type: ignore[attr-defined]
    

# 向默认admin站点注册
admin.site.register(TrainingLog, TrainingLogAdmin)
