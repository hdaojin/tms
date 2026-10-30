"""训练日志列表筛选与固定名单删除。"""

import hashlib
import json
from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import CharField, OuterRef, Q, Subquery
from django.db.models.functions import Concat
from django.http import QueryDict
from django.urls import reverse

from accounts.services.user_management import normalize_ids
from accounts.services.users import get_user_display_name
from core.utils.forms import StyledFormMixin

from .models import TrainingCycle, TrainingCycleMember
from .selectors import training_logs_deletable_by, training_logs_visible_to

SALT = "training.log-deletion"
RETURN_PARAMS = {"q", "cycle", "date_from", "date_to", "member_role", "sort", "page"}


class LogFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(label="搜索日志", required=False, widget=forms.TextInput(attrs={
        "type": "search", "placeholder": "姓名、账号、学号、主题、摘要或文件名",
    }))
    cycle = forms.ModelChoiceField(label="训练周期", required=False, queryset=TrainingCycle.objects.none(),
                                   empty_label="全部训练周期")
    date_from = forms.DateField(label="训练日期从", required=False,
                                widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    date_to = forms.DateField(label="训练日期至", required=False,
                              widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    member_role = forms.ChoiceField(label="周期身份", required=False,
                                    choices=[("", "全部周期身份"), *TrainingCycleMember.Role.choices])

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        visible = training_logs_visible_to(user)
        if not user.is_active or not user.has_perm("training.view_traininglog"):
            visible = visible.none()
        self.fields["cycle"].queryset = TrainingCycle.objects.filter(training_logs__in=visible).distinct().order_by("-start_date", "pk")

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


def filter_training_logs(actor, data):
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
    if values["q"]:
        queryset = queryset.alias(author_full_name=Concat("author__last_name", "author__first_name", output_field=CharField()))
        query = values["q"]
        queryset = queryset.filter(
            Q(author_full_name__icontains=query) | Q(author__username__icontains=query)
            | Q(author__profile__student_id__icontains=query) | Q(topic__icontains=query)
            | Q(summary__icontains=query) | Q(document__icontains=query)
        )
    if values["cycle"]:
        queryset = queryset.filter(training_cycle=values["cycle"])
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
    queryset = training_logs_deletable_by(actor).filter(pk__in=ids)
    # 读取权限与删除范围分别收窄，不能由删除权限扩张可见名单。
    queryset = queryset.filter(pk__in=training_logs_visible_to(actor))
    if lock:
        queryset = queryset.select_for_update()
    logs = list(queryset.select_related("author", "training_cycle").order_by("pk"))
    if len(logs) != len(ids):
        raise ValidationError("部分日志已删除或无权访问，请返回列表重新选择。")
    return logs


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
            "rows": [{"author": get_user_display_name(log.author), "username": log.author.username,
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
