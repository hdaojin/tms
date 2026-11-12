"""训练日志列表筛选与固定名单删除。"""

import hashlib
import json
from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, Subquery
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone

from accounts.services.user_management import normalize_ids
from accounts.services.users import get_user_display_name
from core.utils.forms import StyledFormMixin

from .models import TrainingCycleMember, TrainingLog, TrainingPlan
from .selectors import (
    log_plan_choices, log_plan_is_ongoing, training_log_list_plans_for,
    training_logs_deletable_by, training_logs_visible_to,
)

SALT = "training.log-deletion"
RETURN_PARAMS = {"q", "plan", "date_from", "date_to", "member_role", "sort", "page"}


class LogFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(label="搜索日志", required=False, widget=forms.TextInput(attrs={
        "type": "search", "placeholder": "姓名、拼音、学号、主题、摘要或文件名",
    }))
    plan = forms.ChoiceField(label="训练计划", required=False)
    date_from = forms.DateField(label="训练日期从", required=False,
                                widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    date_to = forms.DateField(label="训练日期至", required=False,
                              widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    member_role = forms.ChoiceField(label="周期身份", required=False,
                                    choices=[("", "全部周期身份"), *TrainingCycleMember.Role.choices])

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.plans = {str(plan.pk): plan for plan in training_log_list_plans_for(user, today).order_by("-start_date", "-pk")}
        self.default_plan = next((plan for plan in self.plans.values() if log_plan_is_ongoing(plan, today)), None)
        self.fields["plan"].choices = [
            ("", "自动选择进行中的计划"), *log_plan_choices(self.plans.values(), today), ("all", "全部日志"),
        ]

    def clean(self):
        data = super().clean()
        if data.get("date_from") and data.get("date_to") and data["date_from"] > data["date_to"]:
            self.add_error("date_to", "结束日期不能早于开始日期。")
        return data


class LogDeleteActionForm(StyledFormMixin, forms.Form):
    operation = forms.ChoiceField(label="操作", choices=[("", "请选择操作"), ("delete", "删除所选日志")],
                                   widget=forms.Select(attrs={"data-bulk-operation": ""}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["operation"].widget.attrs["class"] = "select select-sm w-auto"


def filter_training_logs(actor, data, *, form=None):
    if form is None:
        form = LogFilterForm(data, user=actor)
    if not form.is_valid():
        raise ValidationError([error for errors in form.errors.values() for error in errors])
    queryset = training_logs_visible_to(actor)
    if not actor.is_active or not actor.has_perm("training.view_traininglog"):
        queryset = queryset.none()
    membership = TrainingCycleMember.objects.filter(
        user_id=OuterRef("author_id"), training_cycle_id=OuterRef("training_cycle_id"),
    )
    queryset = queryset.annotate(member_role=Subquery(membership.values("role")[:1]))
    values = form.cleaned_data
    if values["plan"] != "all":
        plan = form.plans[values["plan"]] if values["plan"] else form.default_plan
        if plan is None:
            return queryset.none()
        queryset = queryset.filter(training_cycle_id=plan.training_cycle_id, training_date__range=(plan.start_date, plan.end_date))
    if values["q"]:
        from accounts.services.users import user_name_search_ids
        from django.contrib.auth import get_user_model

        query = values["q"]
        authors = get_user_model().objects.filter(pk__in=queryset.values("author_id"))
        queryset = queryset.filter(
            Q(author_id__in=user_name_search_ids(authors, query))
            | Q(author__profile__student_id__icontains=query) | Q(topic__icontains=query)
            | Q(summary__icontains=query) | Q(document__icontains=query)
        )
    if values["date_from"]:
        queryset = queryset.filter(training_date__gte=values["date_from"])
    if values["date_to"]:
        queryset = queryset.filter(training_date__lte=values["date_to"])
    if values["member_role"]:
        queryset = queryset.filter(member_role=values["member_role"])
    return queryset


def can_manage_log_deletions(actor):
    return actor.is_active and actor.has_perms([
        "training.view_traininglog", "training.delete_traininglog", "training.delete_all_traininglog",
    ])


def _require_manager(actor):
    actor = get_user_model().objects.get(pk=actor.pk)
    if not can_manage_log_deletions(actor):
        raise PermissionDenied
    return actor


def log_list_return_url(query):
    params = QueryDict(query).copy()
    for key in list(params):
        if key not in RETURN_PARAMS:
            del params[key]
    url = reverse("training:log_list")
    return url + ("?" + params.urlencode() if params else "")


def _logs(actor, ids, *, lock=False):
    targets = TrainingLog.objects.filter(pk__in=ids)
    if lock:
        list(targets.order_by("pk").select_for_update().values_list("pk", flat=True))
        matching_logs = targets.filter(
            training_cycle_id=OuterRef("training_cycle_id"),
            training_date__range=(OuterRef("start_date"), OuterRef("end_date")),
        )
        # 与计划发布、撤回等写操作串行，再重新判断日志能否删除。
        list(TrainingPlan.objects.filter(Exists(matching_logs)).order_by("pk").select_for_update().values_list("pk", flat=True))
    logs = list(training_logs_deletable_by(actor, targets).select_related("author", "training_cycle").order_by("pk"))
    if len(logs) != len(ids):
        raise ValidationError("部分日志已删除或无权访问，请返回列表重新选择。")
    return logs


@transaction.atomic
def delete_training_logs(*, actor, ids):
    actor = get_user_model().objects.get(pk=actor.pk)
    for log in _logs(actor, ids, lock=True):
        log.delete()


def _digest(logs):
    state = [[log.pk, log.author_id, get_user_display_name(log.author), log.author.username,
              log.training_cycle_id, log.training_cycle.name, str(log.training_date),
              log.topic, log.summary, log.document.name, log.updated_at.isoformat()]
             for log in logs]
    return hashlib.sha256(json.dumps(state, ensure_ascii=False).encode()).hexdigest()


def preview_log_deletion(*, actor, ids, return_query=""):
    actor = _require_manager(actor)
    ids = normalize_ids(ids)
    logs = _logs(actor, ids)
    token = signing.dumps({"actor": actor.pk, "ids": ids, "digest": _digest(logs),
                           "return_query": return_query}, salt=SALT, compress=True)
    return {"token": token, "count": len(logs), "return_query": return_query,
            "rows": [{"author": get_user_display_name(log.author),
                      "date": log.training_date, "cycle": log.training_cycle.name,
                      "filename": Path(log.document.name).name if log.document else "未附文件"}
                     for log in logs]}


@transaction.atomic
def confirm_log_deletion(*, actor, token):
    actor = _require_manager(actor)
    try:
        data = signing.loads(token, salt=SALT, max_age=1800)
    except signing.BadSignature as exc:
        raise ValidationError("删除预览已失效，请返回列表重新选择。") from exc
    if data["actor"] != actor.pk:
        raise ValidationError("操作所属用户已变化，请重新预览。")
    logs = _logs(actor, data["ids"], lock=True)
    if _digest(logs) != data["digest"]:
        raise ValidationError("所选日志已变化，请重新预览后确认删除。")
    for log in logs:
        log.delete()
    return data["return_query"]
