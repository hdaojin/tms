from django.contrib import admin
from django import forms
from accounts.services.users import get_user_display_name
from .models import (
    TaskExecution,
    TaskExecutionAttachment,
    TrainingCycle,
    TrainingCycleMember,
    TrainingCycleSkillTreeVersion,
    TrainingLog,
    TrainingLogExecution,
    TrainingPlan,
    TrainingTask,
    TrainingTaskAttachment,
    TrainingTaskCoach,
    TrainingTaskDomain,
    TrainingTaskSkill,
)
from .services import save_cycle_member, validate_new_log

admin.site.register(
    [
        TrainingCycle,
        TrainingCycleSkillTreeVersion,
        TrainingPlan,
        TrainingTask,
        TrainingTaskDomain,
        TrainingTaskSkill,
        TrainingTaskCoach,
        TrainingTaskAttachment,
        TaskExecution,
        TaskExecutionAttachment,
        TrainingLogExecution,
    ]
)


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

    @admin.display(description="作者", ordering="author__last_name")
    def author_name(self, obj):
        return get_user_display_name(obj.author)

    @admin.display(description="有附件", boolean=True)
    def has_document(self, obj):
        return bool(obj.document)
