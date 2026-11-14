from datetime import date
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_GET

from core.forms import MultipleFileField
from core.uploads import TRAINING_ATTACHMENT_UPLOAD_SPEC
from core.file_preview import build_download_response
from core.utils.forms import StyledFormMixin
from core.utils.breadcrumbs import Breadcrumb
from core.utils.markdown import render_markdown_text
from django.utils.html import escape
from standards.models import Skill, TechnicalDomain
from . import process
from .models import (
    PersonalTrainingTask,
    TrainingProgress,
    TrainingProgressAttachment,
    TrainingTaskAttachment,
    TaskExecutionAttachment,
)
from .schedule_views import get_plan, render
from .selectors import visible_training_tasks_for


def markdown(text):
    # 复用渲染器；先转义原始 HTML，避免把任务/进度文本作为可执行 HTML。
    from bs4 import BeautifulSoup
    from urllib.parse import urlsplit
    import re

    soup = BeautifulSoup(render_markdown_text(str(escape(text))).html, "html.parser")
    for tag in soup.find_all(["a", "img"]):
        attribute = "href" if tag.name == "a" else "src"
        value = re.sub(r"[\x00-\x20]", "", tag.get(attribute, ""))
        try:
            allowed = urlsplit(value).scheme.lower() in {"", "http", "https", "mailto"}
        except ValueError:
            allowed = False
        if not allowed:
            tag.attrs.pop(attribute, None)
    return str(soup)


class ProgressForm(StyledFormMixin, forms.Form):
    completed = forms.CharField(
        label="已完成的部分／已掌握知识", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )
    problems = forms.CharField(label="未完成的部分／存在问题", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    attachments = MultipleFileField(label="进度图片和附件", required=False, upload_spec=TRAINING_ATTACHMENT_UPLOAD_SPEC)


class PersonalTaskForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PersonalTrainingTask
        fields = ["date", "title", "domain", "description", "skills"]
        labels = {"description": "任务描述（Markdown）"}
        widgets = {"date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def __init__(self, *args, plan, fixed_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.training_plan = plan
        if fixed_date is not None:
            self.initial["date"] = fixed_date
            self.fields["date"].disabled = True
        self.fields["domain"].queryset = TechnicalDomain.objects.filter(skill_project=plan.training_cycle.skill_project)
        self.fields["skills"].queryset = Skill.objects.filter(skill_project=plan.training_cycle.skill_project)


@require_http_methods(["GET", "POST"])
def personal_edit(request, plan_pk=None, pk=None):
    task = get_object_or_404(process.personal_tasks_for(request.user), pk=pk) if pk else None
    plan = task.training_plan if task else get_plan(request.user, plan_pk)
    permission = "training.change_personaltrainingtask" if task else "training.add_personaltrainingtask"
    if not request.user.has_perm(permission) or (
        task and task.user_id != request.user.pk and not request.user.is_superuser
    ):
        raise PermissionDenied
    if not task and not plan.participants.filter(user=request.user, is_active=True).exists():
        raise PermissionDenied
    fixed_date = None
    breadcrumb_parents = None
    page_title = "编辑自主训练任务" if task else "添加自主训练任务"
    form_action = request.path
    raw_date = request.GET.get("date")
    if task is None and raw_date is not None:
        try:
            fixed_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise Http404("无效的训练日期。") from exc
        if not plan.start_date <= fixed_date <= plan.end_date:
            raise Http404("自主任务日期必须位于计划周期内。")
        query = {"date": fixed_date.isoformat()}
        if request.GET.get("scope") == "all":
            query["scope"] = "all"
        if request.GET.get("plan") == str(plan.pk):
            query["plan"] = plan.pk
        query_string = urlencode(query)
        form_action = f"{request.path}?{query_string}"
        return_url = f"{reverse('training:my_training')}?{query_string}"
        if request.user.has_perm("training.view_trainingtask"):
            breadcrumb_parents = [Breadcrumb("我的训练", return_url)]
    form = PersonalTaskForm(
        request.POST if request.method == "POST" else None, instance=task, plan=plan, fixed_date=fixed_date,
    )
    if request.method == "POST" and form.is_valid():
        try:
            task = process.save_personal_task(plan, request.user, form.cleaned_data, task=task)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if fixed_date is not None:
                return redirect(return_url)
            return redirect("training:personal_detail", pk=task.pk)
    return render(
        request, "training/personal_form.html", {"form": form, "plan": plan, "form_action": form_action},
        page_title=page_title, breadcrumb_parents=breadcrumb_parents,
    )


@require_http_methods(["GET", "POST"])
def personal_detail(request, pk):
    from .training_return import training_return

    user = request.user
    target = get_object_or_404(process.personal_tasks_for(user), pk=pk)
    if not process.visible_target(user, target):
        raise PermissionDenied
    plan = target.training_plan
    from .scheduling import visible_plans
    can_view_plan = visible_plans(user).filter(pk=plan.pk).exists()
    own = target.user_id == user.pk
    form = ProgressForm()
    error = ""
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "status":
                target = process.change_state(target, user, request.POST.get("status"))
            elif action == "progress":
                form = ProgressForm(request.POST, request.FILES)
                if form.is_valid():
                    previous = (
                        get_object_or_404(
                            TrainingProgress, pk=request.POST["progress"], **process.target_fields(target)
                        )
                        if request.POST.get("progress")
                        else None
                    )
                    process.save_progress(
                        target,
                        user,
                        completed=form.cleaned_data["completed"],
                        problems=form.cleaned_data["problems"],
                        files=form.cleaned_data["attachments"],
                        progress=previous,
                    )
                    form = ProgressForm()
            elif action == "feedback":
                process.add_feedback(target, user, request.POST.get("content", ""))
            elif action == "delete":
                process.delete_personal_task(target, user)
                url = reverse("training:plan_detail", args=[plan.pk])
                return HttpResponse(headers={"HX-Redirect": url}) if request.htmx else redirect(url)
            else:
                raise ValidationError("不支持的训练操作。")
        except ValidationError as exc:
            error = "；".join(exc.messages)
    records = (
        list(target.progress_records.select_related("author").prefetch_related("attachments", "revisions"))
        if user.has_perm("training.view_trainingprogress")
        else []
    )
    for record in records:
        record.completed_html, record.problems_html = markdown(record.completed), markdown(record.problems)
    feedbacks = (
        target.feedback_records.select_related("author") if user.has_perm("training.view_trainingcoachfeedback") else []
    )
    origin = training_return(request)
    return render(
        request,
        "training/process_detail.html",
        {
            "target": target,
            "personal": True,
            "plan": plan,
            "can_view_plan": can_view_plan,
            "own": own,
            "can_change_state": own and user.has_perm("training.change_personaltrainingtask"),
            "can_edit_personal": user.has_perm("training.change_personaltrainingtask")
            and (own or user.is_superuser),
            "can_delete_personal": user.has_perm("training.delete_personaltrainingtask")
            and (own or user.is_superuser),
            "form": form,
            "error": error,
            "states": process.STATES,
            "progress_records": records,
            "feedbacks": feedbacks,
            "can_feedback": process.is_coach(user, target) and user.has_perm("training.add_trainingcoachfeedback"),
            "is_fragment": bool(request.htmx),
            "state_changes": target.state_changes.select_related("actor"),
            "description_html": markdown(target.description),
        },
        breadcrumb_parents=[origin] if origin else None,
    )


@require_GET
def attachment_download(request, kind, pk):
    if kind == "change":
        from .models import TrainingChangeAttachment
        from .change_workflow import can_review
        from .scheduling import can_approve
        attachment = get_object_or_404(TrainingChangeAttachment.objects.select_related("change__training_plan"), pk=pk)
        if not (request.user == attachment.change.requested_by or can_review(request.user, attachment.change) or can_approve(request.user, attachment.change.training_plan) or attachment.change.confirmation_users.filter(pk=request.user.pk).exists()):
            raise PermissionDenied
        return build_download_response(attachment.file, attachment.original_filename)
    mapping = {
        "task": (TrainingTaskAttachment, "training.view_trainingtaskattachment"),
        "progress": (TrainingProgressAttachment, "training.view_trainingprogressattachment"),
        "legacy": (TaskExecutionAttachment, "training.view_taskexecutionattachment"),
    }
    if kind not in mapping:
        raise PermissionDenied
    model, permission = mapping[kind]
    if not request.user.has_perm(permission):
        raise PermissionDenied
    attachment = get_object_or_404(model, pk=pk)
    if kind == "task":
        from .scheduling import matching_day_tasks

        task = attachment.training_task
        allowed = visible_training_tasks_for(request.user)
        if allowed.filter(pk=task.pk).exists():
            return build_download_response(attachment.file, attachment.original_filename)
        if not task.schedule_slot_id or task.status != "published":
            raise PermissionDenied
        peers = matching_day_tasks(task.schedule_slot, task.title)
        if peers.first() != task or not allowed.filter(pk__in=peers.values("pk")).exists():
            raise PermissionDenied
    else:
        target = (
            attachment.task_execution
            if kind == "legacy"
            else attachment.progress.execution or attachment.progress.personal_task
        )
        if not process.visible_target(request.user, target):
            raise PermissionDenied
    return build_download_response(attachment.file, attachment.original_filename)
