from django.contrib import admin
from django import forms
from .models import Assessment, Score, AssessmentModule, AssessmentAttachment


class AssessmentModuleInline(admin.TabularInline):
    model = AssessmentModule
    extra = 0
    autocomplete_fields = ['module']

class AssessmentAttachmentInline(admin.TabularInline):
    """附件内联编辑"""
    model = AssessmentAttachment
    extra = 1
    fields = ['file', 'description', 'uploaded_at']
    readonly_fields = ['uploaded_at']

class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 为 participants 字段设置 label_from_instance
        participants_field = self.fields.get('participants')
        if participants_field:
            participants_field.label_from_instance = lambda obj: obj.first_name if obj.first_name else obj.username # type: ignore

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    form = AssessmentForm
    list_display = ('name', 'start_date', 'end_date', 'created_at', 'updated_at')
    search_fields = ('name',)
    list_filter = ('start_date', 'end_date')
    filter_horizontal = ('participants',)
    inlines = [AssessmentModuleInline]
    date_hierarchy = 'start_date'

class ScoreInline(admin.TabularInline):
    model = Score
    extra = 0
    # autocomplete_fields = ['user'] # 如果用户很多，可以开启这个
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # 尝试限制用户选择范围为本次考核的参与人员
        if db_field.name == "user":
            parent_obj = getattr(request, '_obj_', None)
            if parent_obj and hasattr(parent_obj, 'assessment'): 
                 kwargs["queryset"] = parent_obj.assessment.participants.all()
            
            form_field = super().formfield_for_foreignkey(db_field, request, **kwargs)
            if form_field:
                 form_field.label_from_instance = lambda obj: obj.first_name if obj.first_name else obj.username # type: ignore
            return form_field
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(AssessmentModule)
class AssessmentModuleAdmin(admin.ModelAdmin):
    list_display = ('assessment', 'module', 'max_score')
    list_filter = ('assessment',)
    search_fields = ('assessment__name', 'module__name')
    inlines = [ScoreInline, AssessmentAttachmentInline]
    
    def get_form(self, request, obj=None, **kwargs):   # type: ignore
        # 保存 obj 到 request 中，以便在 Inline 中使用
        request._obj_ = obj
        return super().get_form(request, obj, **kwargs)


@admin.register(AssessmentAttachment)
class AssessmentAttachmentAdmin(admin.ModelAdmin):
    """附件管理"""
    list_display = ('assessment_module', 'file', 'description', 'uploaded_at')
    list_filter = ('assessment_module__assessment', 'uploaded_at')
    search_fields = ('assessment_module__assessment__name', 'assessment_module__module__name', 'description')
    readonly_fields = ['uploaded_at']


