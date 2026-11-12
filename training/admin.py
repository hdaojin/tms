from django.contrib import admin
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from accounts.services.users import get_user_display_name
from .log_management import delete_training_logs
from .models import (
    TaskExecution,
    TaskExecutionAttachment,
    TrainingCycle,
    TrainingCycleMember,
    TrainingCycleSkillTreeVersion,
    TrainingLog,
    TrainingLogExecution,
    TrainingLogPrompt,
    TrainingPlan,
    TrainingTask,
    TrainingTaskAttachment,
    TrainingTaskCoach,
    TrainingTaskDomain,
    TrainingTaskSkill,
    TrainingChangeRecord,
    TrainingChangeAttachment,
    TrainingScheduleChange,
    TrainingScheduleDay,
    TrainingScheduleSlot,
)
from .services import save_cycle_member, validate_new_log
from .selectors import training_logs_deletable_by
from .models import TrainingPeriodConfig, TrainingPlanParticipant, TrainingAssignmentCoach, PersonalTrainingTask, TrainingProgress, TrainingProgressRevision, TrainingProgressAttachment, TrainingStateChange, TrainingCoachFeedback

admin.site.register(TrainingLogExecution)


@admin.register(TrainingCycle)
class TrainingCycleAdmin(admin.ModelAdmin):
    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if obj.pk:
            TrainingCycle.objects.select_for_update().get(pk=obj.pk)
        obj.save()


@admin.register(TrainingCycleSkillTreeVersion)
class TrainingCycleSkillTreeVersionAdmin(admin.ModelAdmin):
    # 批量删除会绕过模型的快照锁定和领域引用校验。
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return ("training_cycle", "technical_domain") if obj else ()

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (obj is None or not obj.removal_error())

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        cycle = TrainingCycle.objects.select_for_update().get(pk=obj.training_cycle_id)
        obj.training_cycle = cycle
        obj.save()
        cycle.save(update_fields=["updated_at"])

    @transaction.atomic
    def delete_model(self, request, obj):
        cycle = TrainingCycle.objects.select_for_update().get(pk=obj.training_cycle_id)
        obj.training_cycle = cycle
        obj.delete()
        cycle.save(update_fields=["updated_at"])


class TrainingWorkflowReadOnlyAdmin(admin.ModelAdmin):
    """工作流写入统一从前台事务服务完成，后台仅供查阅。"""
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # 后台没有独立的人员/计划范围写入入口。
        return queryset if request.user.is_active and request.user.is_superuser else queryset.none()


for workflow_model in (
    TrainingPlan, TrainingTask, TrainingTaskDomain, TrainingTaskSkill, TrainingTaskCoach, TaskExecution,
    TrainingScheduleDay, TrainingScheduleSlot, TrainingScheduleChange, TrainingChangeRecord,
    TrainingPlanParticipant, TrainingAssignmentCoach, PersonalTrainingTask, TrainingProgress,
    TrainingProgressRevision, TrainingProgressAttachment, TrainingStateChange, TrainingCoachFeedback,
    TrainingTaskAttachment, TaskExecutionAttachment,
):
    admin.site.register(workflow_model, TrainingWorkflowReadOnlyAdmin)

admin.site.register(TrainingChangeAttachment, TrainingWorkflowReadOnlyAdmin)


class TrainingPeriodConfigAdminForm(forms.ModelForm):
    class Meta:
        model = TrainingPeriodConfig
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_time"), cleaned.get("end_time")
        if start is None or end is None:
            return cleaned
        periods = {obj.period: (obj.start_time, obj.end_time) for obj in TrainingPeriodConfig.objects.all()}
        periods[self.instance.period] = (start, end)
        previous_end = None
        for period in TrainingScheduleSlot.Period.values:
            if period not in periods:
                continue
            period_start, period_end = periods[period]
            if period_start >= period_end or (previous_end and period_start < previous_end):
                raise forms.ValidationError("时段须按早读、上午、下午、晚上顺序排列，且不能重叠或跨午夜。")
            previous_end = period_end
        return cleaned


@admin.register(TrainingPeriodConfig)
class TrainingPeriodConfigAdmin(admin.ModelAdmin):
    form = TrainingPeriodConfigAdminForm
    list_display = ("period", "start_time", "end_time", "updated_at")
    readonly_fields = ("period",)

    @transaction.atomic
    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method == "POST":
            list(TrainingPeriodConfig.objects.select_for_update().order_by("pk"))
        return super().changeform_view(request, object_id, form_url, extra_context)

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


class CycleMemberAdminForm(forms.ModelForm):
    class Meta:
        model = TrainingCycleMember
        fields = "__all__"
        help_texts = {"is_current": "勾选将替换该用户原来的当前周期。"}

    def _get_validation_exclusions(self):
        # 切换会在 service 的事务中清除旧标记，表单阶段不提前拒绝条件唯一约束。
        return super()._get_validation_exclusions() | {"is_current"}


@admin.register(TrainingCycleMember)
class TrainingCycleMemberAdmin(admin.ModelAdmin):
    form = CycleMemberAdminForm
    list_display = ("user", "training_cycle", "role", "is_current")
    list_select_related = ("user", "training_cycle")
    list_filter = ("training_cycle", "role", "is_current")
    actions = None

    def get_readonly_fields(self, request, obj=None):
        fields = ("user", "training_cycle", "created_at") if obj else ("created_at",)
        if not request.user.has_perm("training.change_trainingcyclemember"):
            fields += ("is_current",)
        return fields

    def save_model(self, request, obj, form, change):
        save_cycle_member(obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (obj is None or not obj.removal_error())


class TrainingLogAdminForm(forms.ModelForm):
    class Meta:
        model = TrainingLog
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document"].required = not self.instance.pk
        if self.instance.pk:
            self.fields["training_cycle"].disabled = True

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk and all(cleaned.get(key) for key in ("author", "training_cycle", "training_date")):
            validate_new_log(TrainingLog(**{key: cleaned[key] for key in
                                          ("author", "training_cycle", "training_date")}))
        return cleaned


@admin.register(TrainingLog)
class TrainingLogAdmin(admin.ModelAdmin):
    form = TrainingLogAdminForm
    list_display = (
        "training_date", "training_cycle", "author_name", "topic", "has_document", "created_at", "updated_at",
    )
    list_select_related = ("training_cycle", "author")
    list_filter = ("training_cycle", "training_date")
    search_fields = (
        "topic", "summary", "author__first_name", "author__last_name", "author__username",
        "training_cycle__name", "training_cycle__code",
    )
    date_hierarchy = "training_date"
    readonly_fields = ("created_at", "updated_at")
    fields = ("training_cycle", "author", "training_date", "topic", "summary", "document", "created_at", "updated_at")

    def has_change_permission(self, request, obj=None):
        return (obj is None or not obj.online_document) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if not super().has_delete_permission(request, obj):
            return False
        eligible = training_logs_deletable_by(request.user)
        return (eligible.filter(pk=obj.pk) if obj else eligible).exists()

    def delete_model(self, request, obj):
        self._delete_logs(request, [obj.pk])

    def response_action(self, request, queryset, *args, **kwargs):
        # 后台批量动作先写管理日志，确认失败时一并回滚。
        with transaction.atomic(using=queryset.db):
            return super().response_action(request, queryset, *args, **kwargs)

    def delete_queryset(self, request, queryset):
        self._delete_logs(request, list(queryset.values_list("pk", flat=True)))

    def _delete_logs(self, request, ids):
        try:
            delete_training_logs(actor=request.user, ids=ids)
        except ValidationError as exc:
            raise PermissionDenied from exc

    @admin.display(description="作者", ordering="author__last_name")
    def author_name(self, obj):
        return get_user_display_name(obj.author)

    @admin.display(description="有附件", boolean=True)
    def has_document(self, obj):
        return bool(obj.document)


@admin.register(TrainingLogPrompt)
class TrainingLogPromptAdmin(admin.ModelAdmin):
    list_display = ("role", "min_words", "max_words", "updated_at")
    ordering = ("role",)
