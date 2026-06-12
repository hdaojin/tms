from django.contrib import admin

from .models import CountdownEvent


@admin.register(CountdownEvent)
class CountdownEventAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'event_type',
        'project_name',
        'project_english_name',
        'theme',
        'target_at',
        'countdown_prefix',
        'finished_message',
        'location',
        'is_active',
        'display_order',
    )
    list_filter = ('event_type', 'is_active', 'theme')
    search_fields = (
        'name',
        'subtitle',
        'project_name',
        'project_english_name',
        'location',
        'description',
        'countdown_prefix',
        'finished_message',
        'slug',
    )
    ordering = ('display_order', 'target_at')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (
            '基础信息',
            {
                'fields': (
                    'name',
                    'slug',
                    'subtitle',
                    'event_type',
                    'project_name',
                    'project_english_name',
                    'location',
                ),
            },
        ),
        (
            '时间与展示',
            {
                'fields': (
                    'target_at',
                    'countdown_prefix',
                    'finished_message',
                    'theme',
                    'description',
                ),
            },
        ),
        (
            '发布控制',
            {
                'fields': (
                    'is_active',
                    'display_order',
                ),
            },
        ),
        (
            '时间戳',
            {
                'fields': (
                    'created_at',
                    'updated_at',
                ),
            },
        ),
    )
