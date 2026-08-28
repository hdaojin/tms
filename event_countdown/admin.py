from django import forms
from django.contrib import admin
from django.db import models

from .models import CountdownEvent, CountdownEventType


class CountdownEventAdminForm(forms.ModelForm):
    class Meta:
        model = CountdownEvent
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = CountdownEventType.objects.filter(is_active=True)
        if self.instance.pk and self.instance.event_type_id:
            queryset = CountdownEventType.objects.filter(
                models.Q(is_active=True) | models.Q(pk=self.instance.event_type_id)
            )
        self.fields['event_type'].queryset = queryset.order_by('order', 'code')


@admin.register(CountdownEventType)
class CountdownEventTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('code', 'name')

    def get_readonly_fields(self, request, obj=None):
        return ('code',) if obj else ()


@admin.register(CountdownEvent)
class CountdownEventAdmin(admin.ModelAdmin):
    form = CountdownEventAdminForm
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

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        other_type = CountdownEventType.objects.filter(code='other', is_active=True).first()
        if other_type is not None:
            initial.setdefault('event_type', other_type.pk)
        return initial
