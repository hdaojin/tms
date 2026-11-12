from datetime import timedelta
from urllib.parse import urlsplit

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.vary import vary_on_headers

from ai_models.services import can_manage

from core.documents.content import normalize_document_image
from core.documents.limits import MAX_IMAGE_TOTAL_BYTES
from core.documents.service import render_document_html
from core.documents.types import DocumentError, DocumentRenderError
from core.utils.breadcrumbs import breadcrumb_link, build_breadcrumbs

from . import log_generation
from .checklists import completion_counts
from .completion_forms import DailyCompletionForm, TaskCompletionForm
from .daily_progress import (
    daily_executions,
    day_fingerprint,
    save_day,
    training_day_url,
    training_upload_url,
    validate_training_day,
)
from .log_ai_forms import DraftBodyForm, LogActionForm, LogGenerationForm, LogImageForm, TrainingDayForm
from .log_documents import document_input, draft_document, source_digest, submit_draft
from .log_references import IMAGE_SPEC, image_asset, read_reference
from .log_sources import FIELDS, STUDENT, changed_sources, check_source_access
from .models import TrainingLog, TrainingLogDraft, TrainingLogGeneration, TrainingProgressAttachment
from .scheduling import can_fill, visible_plans
from .selectors import training_logs_visible_to, visible_training_tasks_for

Status = TrainingLogGeneration.Status


def require_permissions(user, *permissions):
    if not user.is_active or not user.has_perms(permissions):
        raise PermissionDenied


def page(request, template, title, **context):
    parents = []
    if request.user.has_perm("training.view_traininglog"):
        parents.append(breadcrumb_link("训练日志", "training:log_list"))
    return render(
        request,
        f"training/{template}.html",
        {
            "title": title,
            "title_icon": "icon-[tabler--file-text]",
            "breadcrumbs": build_breadcrumbs(request, title, parents),
            **context,
        },
    )


def default_day_query(user, request):
    if "training_date" in request.GET or "cycle" in request.GET:
        return request.GET
    member = user.training_cycle_memberships.filter(is_current=True).first()
    if member:
        return {"training_date": timezone.localdate().isoformat(), "cycle": member.training_cycle_id}
    return None


def goal_edit_links(user, entries):
    missing = [entry["id"] for entry in entries if not entry["goal"]]
    if not missing or not user.has_perm("training.change_trainingtask"):
        return {}
    tasks = visible_training_tasks_for(user).filter(pk__in=missing, training_plan__in=visible_plans(user))
    return {
        task.pk: f"{reverse('training:task_edit', args=[task.pk])}?focus=goal#id_requirements"
        for task in tasks.select_related("schedule_slot__day__training_plan").prefetch_related(
            "schedule_slot__coaches", "schedule_slot__domains"
        )
        if can_fill(user, task.schedule_slot)
    }


@never_cache
@require_http_methods(["GET", "POST"])
def daily_progress(request):
    user = request.user
    require_permissions(user, "training.view_taskexecution", "training.view_trainingprogress")
    selection = TrainingDayForm(default_day_query(user, request), user=user)
    if not selection.is_valid():
        if request.method == "POST":
            raise PermissionDenied
        return page(request, "daily_progress", "训练完成情况", error="请从「我的训练」选择可填报的日期。")
    cycle, day = selection.cleaned_data["cycle"], selection.cleaned_data["training_date"]
    if validate_training_day(user, cycle, day).role != STUDENT:
        raise PermissionDenied
    executions = list(daily_executions(user, cycle, day))
    rows = []
    is_post = request.method == "POST"
    shared_execution_id = min((execution.pk for execution in executions), default=None)
    notes = ""
    attachments = []
    for execution in executions:
        record = next(iter(execution.daily_records), None)
        if record:
            if execution.pk == shared_execution_id:
                notes = record.problems
            attachments.extend(record.attachments.all())
        editable = user.has_perm("training.change_trainingprogress" if record else "training.add_trainingprogress")
        form = TaskCompletionForm(
            request.POST if is_post else None,
            execution=execution,
            record=record,
            prefix=f"task-{execution.pk}",
        )
        rows.append(
            {
                "execution": execution,
                "record": record,
                "counts": completion_counts(record),
                "previous_problems": record.problems if record and execution.pk != shared_execution_id else "",
                "form": form,
                "editable": editable,
            }
        )
    editable = bool(rows) and all(row["editable"] for row in rows)
    day_form = DailyCompletionForm(
        request.POST if is_post else None,
        request.FILES if is_post else None,
        initial={"problems": notes},
    )
    fingerprint = day_fingerprint(executions)
    error = ""
    if request.method == "POST":
        if not editable:
            raise PermissionDenied
        valid = [row["form"].is_valid() for row in rows]
        if day_form.is_valid() and all(valid):
            try:
                previous = signing.loads(request.POST.get("version", ""), salt="training.daily_completion")
                save_day(
                    user,
                    cycle,
                    day,
                    previous,
                    {row["execution"].pk: row["form"].cleaned_data["items"] for row in rows},
                    **day_form.cleaned_data,
                )
            except signing.BadSignature:
                error = "页面已失效，请重新打开后填写。"
            except ValidationError as exc:
                error = "；".join(exc.messages)
            else:
                messages.success(request, "已保存当天训练完成情况。")
                return redirect(f"{reverse('training:my_training')}?date={day.isoformat()}")
    return page(
        request,
        "daily_progress",
        f"{day.year}年{day.month}月{day.day}日训练完成情况",
        rows=rows,
        day=day,
        editable=editable,
        day_form=day_form,
        attachments=attachments,
        notes=notes,
        show_plan_names=len({execution.training_task.training_plan_id for execution in executions}) > 1,
        error=error,
        version=request.POST.get("version", "")
        if request.method == "POST"
        else signing.dumps(fingerprint, salt="training.daily_completion"),
    )


@never_cache
@require_http_methods(["GET", "POST"])
def start(request):
    user = request.user
    require_permissions(
        user, "training.add_traininglog", "training.view_taskexecution", "training.view_trainingprogress"
    )
    history = request.GET.get("history") == "1"
    selecting_history = history and "training_date" not in request.GET
    values = (
        (request.POST if request.method == "POST" else None) if selecting_history else default_day_query(user, request)
    )
    form = TrainingDayForm(values, user=user)
    if selecting_history and not form.is_bound:
        form.initial["training_date"] = timezone.localdate() - timedelta(days=1)
    existing = None
    error = ""
    if form.is_valid():
        cycle, day = form.cleaned_data["cycle"], form.cleaned_data["training_date"]
        if history != (day < timezone.localdate()):
            error = "历史训练日请使用补交入口，日常编写仅支持今天。"
        else:
            existing = TrainingLog.objects.filter(author=user, training_cycle=cycle, training_date=day).first()
            if not existing:
                if request.method == "POST" and selecting_history:
                    return redirect(training_day_url("training:log_ai_start", cycle.pk, day))
                lookup = {"author": user, "cycle": cycle, "training_date": day}
                if request.method == "POST":
                    draft, _ = TrainingLogDraft.objects.get_or_create(**lookup)
                    if not request.POST.get("action"):
                        return redirect("training:log_ai_draft", pk=draft.pk)
                    return draft_page(request, draft=draft)
                draft = TrainingLogDraft.objects.filter(**lookup).first()
                if draft:
                    return redirect("training:log_ai_draft", pk=draft.pk)
                return draft_page(request, draft=TrainingLogDraft(**lookup))
    if not history and not error and not existing:
        error = "请确认已设置进行中的当前训练周期。"
    return page(
        request,
        "log_ai_start",
        "补交历史训练日志" if history else "编写训练日志",
        day_form=form if selecting_history else None,
        existing=existing,
        error=error,
    )


def get_draft(user, pk):
    require_permissions(
        user, "training.add_traininglog", "training.view_taskexecution", "training.view_trainingprogress"
    )
    return get_object_or_404(TrainingLogDraft.objects.select_related("cycle__skill_project"), pk=pk, author=user)


def available_progress_images(draft, source):
    files = TrainingProgressAttachment.objects.all()
    if not draft.author.has_perm("training.view_trainingprogressattachment"):
        return files.none()
    executions = [pk for task in source["tasks"] for pk in task["execution_ids"]]
    extensions = Q()
    for extension in IMAGE_SPEC.allowed_extensions:
        extensions |= Q(original_filename__iendswith=f".{extension}")
    return files.filter(
        extensions, progress__execution_id__in=executions, progress__training_date=draft.training_date
    ).order_by("pk")


@transaction.atomic
def add_images(draft, uploads, progress_ids):
    if not uploads and not progress_ids:
        return
    draft = log_generation.lock_draft(draft)
    current, _, _ = log_generation.source_for(draft)
    progress_images = list(available_progress_images(draft, current).filter(pk__in=progress_ids))
    if len(progress_images) != len(progress_ids):
        raise ValidationError("部分过程图片已不在可用范围。")
    assets = []
    for file in uploads:
        assets.append(image_asset(file))
    for image in progress_images:
        try:
            with image.file.open("rb") as file:
                assets.append(image_asset(file))
        except OSError as exc:
            raise ValidationError("无法读取部分过程图片。") from exc
    images = set(draft.images.values_list("content", flat=True))
    size = sum(map(len, images))
    original_count = count = draft.images.count()
    for asset in assets:
        content, mime, _ = normalize_document_image(asset, "日志插图")
        if content in images:
            continue
        count += 1
        size += len(content)
        if count > 18 or size > MAX_IMAGE_TOTAL_BYTES - 1024 * 1024:
            raise ValidationError("插图已达 18 张或总大小上限。")
        images.add(content)
        draft.images.create(content=content, media_type=mime, caption="")
    if count != original_count:
        draft.revision += 1
        draft.save(update_fields=["revision", "updated_at"])


@never_cache
@vary_on_headers("HX-Request")
@require_http_methods(["GET", "POST"])
def draft_page(request, pk=None, *, draft=None):
    draft = draft if draft is not None else get_draft(request.user, pk)
    action = request.POST.get("action") if request.method == "POST" else None
    inline_edit = action == "edit" and bool(request.htmx)
    if draft.submitted_log_id:
        url = reverse("training:log_detail", args=[draft.submitted_log_id])
        return HttpResponse(headers={"HX-Redirect": url}) if inline_edit else redirect(url)
    try:
        log_generation.check_draft(draft)
        current, _, missing = log_generation.source_for(draft)
    except ValidationError as exc:
        error = "；".join(exc.messages)
        if inline_edit:
            return render(request, "training/log_ai_draft.html#draft_editor", {"editor_error": error})
        return page(request, "log_ai_start", "AI 辅助编写训练日志", error=error)
    role = current["header"]["role"]
    generation_form = LogGenerationForm(
        request.POST if action == "prepare" else None,
        request.FILES if action == "prepare" else None,
        draft=draft,
    )
    image_form = LogImageForm(
        request.POST if action in {"image", "prepare"} else None,
        request.FILES if action in {"image", "prepare"} else None,
        available=available_progress_images(draft, current),
    )
    body_form = DraftBodyForm(request.POST if action == "edit" else None, role=role, draft=draft)
    saved = False
    error = ""
    if action:
        try:
            success_url = handle_action(request, draft, action, generation_form, image_form, body_form)
        except (ValidationError, DocumentError, DocumentRenderError) as exc:
            error = "；".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        else:
            if success_url:
                if not inline_edit:
                    return redirect(f"{success_url}#draft-editor" if action == "edit" else success_url)
                saved = True
                draft.refresh_from_db()
                body_form = DraftBodyForm(role=role, draft=draft)
    job = TrainingLogGeneration.objects.select_related("model").filter(draft=draft).first() if draft.pk else None
    images = list(draft.images.defer("content").order_by("pk")) if draft.pk else []
    can_view_job = False
    host, result = "", []
    if job:
        try:
            check_source_access(job.source, current)
        except ValidationError:
            pass
        else:
            can_view_job = True
            if job.model and job.model.revision == job.model_revision:
                host = urlsplit(job.model.base_url).hostname
            if job.status == Status.READY:
                result = [(label, job.result.get(key, "")) for key, label in FIELDS[role]]
                if job.result.get("task_title"):
                    result.insert(0, ("训练任务概括标题", job.result["task_title"]))
                if job.result.get("suggested_items"):
                    result.append(("补充训练内容", "\n".join(job.result["suggested_items"])))
                suggested_goals = job.result.get("suggested_goals", {})
                result.extend(
                    (f"{task['title']} · 建议训练目标", suggested_goals[str(task["id"])])
                    for task in job.source["tasks"]
                    if str(task["id"]) in suggested_goals
                )
    can_preview, changes = False, []
    if draft.source:
        try:
            check_source_access(draft.source, current)
            can_preview = bool(draft.body)
            changes = changed_sources(draft.source, current)
        except ValidationError as exc:
            error = error or "；".join(exc.messages)
    if inline_edit:
        return render(
            request,
            "training/log_ai_draft.html#draft_editor",
            {
                "draft": draft,
                "body_form": body_form,
                "can_preview": can_preview,
                "editor_error": error,
                "saved": saved,
                "running": bool(job and job.status in log_generation.ACTIVE),
                "changes": changes,
                "source_digest": source_digest(current),
            },
        )
    has_model = generation_form.fields["model"].queryset.exists()
    edit_links = goal_edit_links(request.user, current["tasks"]) if current.get("goal_task_ids") else {}
    return page(
        request,
        "log_ai_draft",
        "AI 辅助编写训练日志",
        draft=draft,
        task_rows=[{**entry, "goal_edit_url": edit_links.get(entry["id"])} for entry in current["tasks"]],
        missing=missing,
        role=role,
        generation_form=generation_form,
        image_form=image_form,
        body_form=body_form,
        job=job,
        host=host,
        result=result,
        error="" if action == "edit" and can_preview else error,
        editor_error=error if action == "edit" and can_preview else "",
        has_model=has_model,
        can_prepare=has_model and not missing and not (job and job.status in (*log_generation.ACTIVE, Status.READY)),
        can_add_model=can_manage(request.user),
        upload_url=training_upload_url(draft.cycle_id, draft.training_date),
        expand_extras=bool(generation_form.errors or image_form.errors or (error and action in {"prepare", "image"})),
        running=bool(job and job.status in log_generation.ACTIVE),
        can_preview=can_preview,
        can_view_job=can_view_job,
        changes=changes,
        source_digest=source_digest(current),
        images=images,
        progress_url=training_day_url("training:daily_progress", draft.cycle_id, draft.training_date)
        if role == STUDENT and current["tasks"]
        else "",
    )


def handle_action(request, draft, action, generation_form, image_form, body_form):
    if action in {"prepare", "image"}:
        images_valid = image_form.is_valid()
        generation_valid = action == "image" or generation_form.is_valid()
        if not images_valid or not generation_valid:
            return None
        with transaction.atomic():
            add_images(
                draft,
                image_form.cleaned_data["images"],
                set(image_form.cleaned_data["progress_images"].values_list("pk", flat=True)),
            )
            if action == "prepare":
                values = generation_form.cleaned_data
                file = values["reference"]
                log_generation.prepare_generation(
                    draft,
                    model=values["model"],
                    thinking=values["thinking"],
                    effort=values["effort"],
                    instructions=values["instructions"],
                    references=values["references"],
                    reference_text=read_reference(file) if file else "",
                    image_ids=set(),
                    target_words=values["target_words"],
                )
    elif action == "edit":
        if not body_form.is_valid():
            return None
        data = body_form.cleaned_data
        revision = data.pop("revision")
        log_generation.edit_draft(draft, revision, data)
        if not request.htmx:
            messages.success(request, "已保存草稿正文。")
    else:
        form = LogActionForm(request.POST)
        if not form.is_valid():
            raise ValidationError("操作参数有误，请刷新后重试。")
        data = form.cleaned_data
        if action == "confirm":
            log_generation.confirm_generation(draft, data["generation"])
        elif action in {"apply", "discard"}:
            log_generation.resolve_generation(
                draft,
                data["generation"],
                apply=action == "apply",
                revision=data["revision"],
            )
        elif action == "submit":
            log = submit_draft(draft, data["revision"], data["source_digest"], data["accept_changes"])
            messages.success(request, "已提交训练日志并归档 PDF。")
            return reverse("training:log_detail", args=[log.pk])
        else:
            raise ValidationError("不支持的日志操作。")
    return reverse("training:log_ai_draft", args=[draft.pk])


def html_response(data, images):
    try:
        content = render_document_html(document_input(data, images))
    except (ValidationError, DocumentError) as exc:
        error = "；".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        return HttpResponse(error, status=400, content_type="text/plain; charset=utf-8")
    response = HttpResponse(content)
    response["Content-Security-Policy"] = (
        "sandbox; default-src 'none'; img-src data:; style-src 'self'; base-uri 'none'; frame-ancestors 'self'"
    )
    return response


@never_cache
@xframe_options_sameorigin
@require_GET
def draft_preview(request, pk):
    draft = get_draft(request.user, pk)
    try:
        current, _, _ = log_generation.source_for(draft)
        check_source_access(draft.source, current)
    except ValidationError as exc:
        return HttpResponse("；".join(exc.messages), status=400, content_type="text/plain; charset=utf-8")
    return html_response(draft_document(draft), draft.images.all())


@never_cache
@require_GET
def submitted_preview(request, pk):
    require_permissions(request.user, "training.view_traininglog")
    log = get_object_or_404(training_logs_visible_to(request.user).exclude(online_document={}), pk=pk)
    draft = get_object_or_404(TrainingLogDraft, submitted_log=log)
    return html_response(log.online_document, draft.images.all())


@never_cache
@require_GET
def draft_image(request, pk, image_pk):
    draft = get_draft(request.user, pk)
    if draft.submitted_log_id:
        raise PermissionDenied
    try:
        validate_training_day(request.user, draft.cycle, draft.training_date)
    except ValidationError as exc:
        raise PermissionDenied from exc
    image = get_object_or_404(draft.images, pk=image_pk)
    return HttpResponse(bytes(image.content), content_type=image.media_type)


@never_cache
@require_http_methods(["GET", "POST"])
def log_settings(request):
    from django import forms

    from core.utils.forms import StyledFormMixin
    from .log_ai_forms import LogPromptForm
    from .models import TrainingCycle, TrainingCycleMember, TrainingLogPrompt

    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied

    class CycleForm(StyledFormMixin, forms.ModelForm):
        class Meta:
            model = TrainingCycle
            fields = ("log_edition", "log_class")

        log_edition = forms.IntegerField(label="日志赛事届次", min_value=1, max_value=32767)

    class SelectCycleForm(StyledFormMixin, forms.Form):
        cycle = forms.ModelChoiceField(label="训练周期", queryset=TrainingCycle.objects.all())

    selection = SelectCycleForm(request.GET if "cycle" in request.GET else None)
    cycle = selection.cleaned_data["cycle"] if selection.is_valid() else None
    editing_heading = request.method == "POST" and request.POST.get("action") == "heading"
    heading_form = CycleForm(request.POST if editing_heading else None, instance=cycle) if cycle else None
    if editing_heading:
        if not heading_form:
            return HttpResponse("请先选择训练周期。", status=400)
        if heading_form.is_valid():
            cycle.log_edition = heading_form.cleaned_data["log_edition"]
            cycle.log_class = heading_form.cleaned_data["log_class"]
            cycle.save(update_fields=["log_edition", "log_class", "updated_at"])
            messages.success(request, "已保存训练周期的日志标题设置。")
            return redirect(f"{reverse('training:log_settings')}?cycle={cycle.pk}")

    configs = {item.role: item for item in TrainingLogPrompt.objects.all()}
    prompt_forms = []
    editing_prompt = request.method == "POST" and request.POST.get("action") == "prompts"
    for role, label in TrainingCycleMember.Role.choices:
        prompt = configs.get(role) or TrainingLogPrompt(role=role)
        initial = {"instructions": prompt.instructions or log_generation.default_instructions(role)}
        prompt_forms.append(
            (
                label,
                LogPromptForm(request.POST if editing_prompt else None, instance=prompt, prefix=role, initial=initial),
            )
        )
    if editing_prompt:
        valid = [form.is_valid() for _, form in prompt_forms]
        if all(valid):
            with transaction.atomic():
                for _, form in prompt_forms:
                    TrainingLogPrompt.objects.update_or_create(role=form.instance.role, defaults=form.cleaned_data)
            messages.success(request, "已保存默认提示词。")
            return redirect(request.get_full_path())

    return page(
        request,
        "log_settings",
        "训练日志设置",
        prompt_forms=prompt_forms,
        selection=selection,
        heading_form=heading_form,
    )
