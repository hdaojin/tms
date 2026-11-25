import json
from datetime import timedelta
from urllib.parse import urlsplit

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.cache import never_cache
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_http_methods
from django.views.decorators.vary import vary_on_headers

from ai.services import can_manage
from bs4 import BeautifulSoup

from core.documents.content import CLEANER, MARKDOWN_EXTRAS, normalize_document_image
from core.documents.limits import MAX_IMAGE_TOTAL_BYTES
from core.documents.service import render_document_html
from core.documents.types import DocumentError, DocumentRenderError
from core.utils.breadcrumbs import breadcrumb_link, build_breadcrumbs
from core.utils.markdown import render_markdown_text

from . import log_generation
from .checklists import completion_counts
from .completion_forms import CompletionIssues, DailyCompletionForm, TaskCompletionForm
from .daily_progress import (
    LOG_COMPLETION_REQUIRED,
    completion_groups,
    daily_executions,
    day_fingerprint,
    expand_completion,
    log_completion_pending,
    save_day,
    training_day_url,
    training_upload_url,
    validate_training_day,
)
from .log_ai_forms import DraftBodyForm, LogActionForm, LogGenerationForm, LogImageForm, TrainingDayForm
from .log_documents import document_input, draft_document, source_digest, submit_draft
from .log_references import IMAGE_SPEC, image_asset
from .log_sources import (
    COACH, FIELDS, STUDENT, changed_sources, check_source_access, collect_sources,
    editor_fields, validate_editor_body,
)
from .log_web_references import fetch_reference_pages
from .models import TrainingLog, TrainingLogDraft, TrainingLogGeneration, TrainingProgressAttachment, TrainingTask
from .note_log_drafts import NOTE_SECTIONS, import_note_draft
from .note_log_sources import build_note_draft, can_refresh_note_images
from .scheduling import can_fill, visible_plans
from .selectors import training_logs_visible_to, visible_training_tasks_for
from .teaching_notes import task_note_route
from .training_return import return_params, training_return, with_training_return

Status = TrainingLogGeneration.Status


def require_permissions(user, *permissions):
    if not user.is_active or not user.has_perms(permissions):
        raise PermissionDenied


def page(request, template, title, **context):
    parents = []
    origin = training_return(request)
    if origin:
        parents.append(origin)
        context["training_return_url"] = origin.url
    elif request.user.has_perm("training.view_traininglog"):
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
    issues = []
    attachments = []
    for execution in executions:
        record = next(iter(execution.daily_records), None)
        if record:
            if execution.pk == shared_execution_id:
                notes = record.problems
                issues = record.issues
            attachments.extend(record.attachments.all())
    for group in completion_groups(executions):
        execution = group[0]
        record = next(iter(execution.daily_records), None)
        editable = all(user.has_perm(
            "training.change_trainingprogress" if member.daily_records else "training.add_trainingprogress"
        ) for member in group)
        masks = [tuple(item["done"] for item in (member.daily_records[0].checklist or ()))
                 if member.daily_records else () for member in group]
        previous_counts = [
            (member.training_task.schedule_slot.get_period_display(),
             member.daily_records[0].checklist if member.daily_records else None)
            for member in group
        ]
        form = TaskCompletionForm(
            request.POST if is_post else None,
            execution=execution,
            record=record,
            prefix=f"task-{execution.pk}",
        )
        rows.append(
            {
                "execution": execution,
                "group": group,
                "inconsistent": len(set(masks)) > 1,
                "previous_counts": previous_counts,
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
    issue_forms = CompletionIssues(
        request.POST if is_post and "issues-TOTAL_FORMS" in request.POST else None,
        prefix="issues", initial=issues or ([{"description": notes}] if notes else []),
        form_kwargs={"cycle": cycle, "day": day},
    )
    fingerprint = day_fingerprint(executions)
    error = ""
    if request.method == "POST":
        if not editable:
            raise PermissionDenied
        valid = [row["form"].is_valid() for row in rows]
        if day_form.is_valid() and all(valid) and (not issue_forms.is_bound or issue_forms.is_valid()):
            try:
                if any(row["inconsistent"] for row in rows) and request.POST.get("confirm_merge") != "on":
                    raise ValidationError("请确认按本次勾选统一各时段的完成情况。")
                previous = signing.loads(request.POST.get("version", ""), salt="training.daily_completion")
                structured = [
                    {"description": item["description"], "domain": item["domain"].pk if item["domain"] else None,
                     "skills": [skill.pk for skill in item["skills"]]}
                     for item in issue_forms.cleaned_data if item and not item.get("DELETE")
                ] if issue_forms.is_bound else None
                save_day(
                    user,
                    cycle,
                    day,
                    previous,
                    {key: value for row in rows for key, value in
                     expand_completion(row["group"], row["form"].cleaned_data["items"]).items()},
                    **day_form.cleaned_data,
                    issues=structured,
                )
            except signing.BadSignature:
                error = "页面已失效，请重新打开后填写。"
            except ValidationError as exc:
                error = "；".join(exc.messages)
            else:
                messages.success(request, "已保存当天训练完成情况。")
                origin = training_return(request)
                return redirect(origin.url if origin else f"{reverse('training:my_training')}?date={day.isoformat()}")
    return page(
        request,
        "daily_progress",
        f"{day.year}年{day.month}月{day.day}日训练完成情况",
        rows=rows,
        day=day,
        editable=editable,
        day_form=day_form,
        issue_forms=issue_forms,
        needs_merge_confirmation=any(row["inconsistent"] for row in rows),
        attachments=attachments,
        notes=notes,
        show_plan_names=len({execution.training_task.training_plan_id for execution in executions}) > 1,
        error=error,
        version=request.POST.get("version", "")
        if request.method == "POST"
        else signing.dumps(fingerprint, salt="training.daily_completion"),
    )


@require_GET
def completion_skill_search(request, cycle_id, day):
    from standards.models import Skill

    require_permissions(request.user, "training.view_taskexecution", "training.view_trainingprogress")
    selection = TrainingDayForm({"cycle": cycle_id, "training_date": day}, user=request.user)
    if not selection.is_valid():
        raise PermissionDenied
    cycle, date = selection.cleaned_data["cycle"], selection.cleaned_data["training_date"]
    if validate_training_day(request.user, cycle, date).role != STUDENT:
        raise PermissionDenied
    query = request.GET.get("q", "").strip()[:100]
    skills = Skill.objects.filter(skill_project=cycle.skill_project, name__icontains=query) if query else Skill.objects.none()
    domain = request.GET.get("domain", "")
    if domain.isascii() and domain.isdigit():
        skills = skills.filter(Q(primary_domain_id=domain) | Q(related_domains=domain)).distinct()
    page_number = request.GET.get("page", "")
    index = min(int(page_number), 1000) if page_number.isascii() and page_number.isdigit() and len(page_number) < 6 else 1
    offset = max(index - 1, 0) * 20
    rows = list(skills.order_by("name", "pk").values("id", "name")[offset:offset + 21])
    return JsonResponse({"results": [{"id": row["id"], "label": row["name"]} for row in rows[:20]], "has_more": len(rows) > 20})


def report_log_form_errors(request, *forms):
    for form in forms:
        for error in form.non_field_errors():
            messages.error(request, error)
        if any(field.errors for field in form.hidden_fields()):
            messages.error(request, "草稿版本无效，请重新加载后再试。")


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
            if not existing and log_completion_pending(user, cycle.pk, day):
                error = LOG_COMPLETION_REQUIRED
            elif not existing:
                if request.method == "POST" and selecting_history:
                    return redirect(with_training_return(training_day_url("training:log_ai_start", cycle.pk, day), return_params(request.GET)))
                lookup = {"author": user, "cycle": cycle, "training_date": day}
                if request.method == "POST" and request.POST.get("action") != "preview":
                    draft, _ = TrainingLogDraft.objects.get_or_create(**lookup)
                    if not (request.POST.get("action") or request.POST.get("generate_section")):
                        return redirect(with_training_return(reverse("training:log_ai_draft", args=[draft.pk]), return_params(request.GET)))
                    return draft_page(request, draft=draft)
                draft = TrainingLogDraft.objects.filter(**lookup).first()
                if draft:
                    if request.method == "POST" or request.GET.get("note_candidates") == "1":
                        return draft_page(request, draft=draft)
                    return redirect(with_training_return(reverse("training:log_ai_draft", args=[draft.pk]), return_params(request.GET)))
                return draft_page(request, draft=TrainingLogDraft(**lookup))
    if not history and not error and not existing:
        error = "请确认已设置进行中的当前训练周期。"
    if error:
        messages.error(request, error)
    if selecting_history:
        report_log_form_errors(request, form)
    return page(
        request,
        "log_ai_start",
        "补交历史训练日志" if history else "编写训练日志",
        day_form=form if selecting_history else None,
        history_upload_url=reverse("training:log_backfill") if selecting_history else "",
        existing=existing,
        existing_url=with_training_return(
            reverse("training:log_detail", args=[existing.pk]), return_params(request.GET),
        ) if existing else "",
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
    if TrainingLogGeneration.objects.filter(
        draft=draft, status__in=(*log_generation.ACTIVE, Status.READY)
    ).exists():
        raise ValidationError("请先完成本次生成并处理结果，再修改插图。")
    current, _, _ = log_generation.source_for(draft, note_assets=False)
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


def candidate_sections(job, role, images):
    image_urls = {
        f"tms-asset:image-{image.pk}": reverse("training:log_ai_image", args=[job.draft_id, image.pk])
        for image in images
        if image.pk in job.image_ids
    }
    used = set()
    sections = []
    scoped = job.source.get("generated_sections")
    for key, label in editor_fields(role) if scoped else FIELDS[role]:
        if key not in job.result and (scoped or job.source.get("summary_only")):
            continue
        html = render_markdown_text(job.result.get(key, ""), extensions=MARKDOWN_EXTRAS).html
        soup = BeautifulSoup(CLEANER.clean(html), "html.parser")
        for node in soup.find_all(id=True):
            del node["id"]
        for link in soup.find_all("a", href=True):
            del link["href"]
        for image in soup.find_all("img"):
            src = image.get("src")
            if src in image_urls:
                used.add(src)
                image["src"] = image_urls[src]
            else:
                image.decompose()
        sections.append((key, label, mark_safe(str(soup))))
    if job.result.get("task_title"):
        sections.insert(0, ("task_title", "训练任务概括标题", job.result["task_title"]))
    if job.result.get("suggested_items"):
        sections.append(("outline_md", "补充训练内容", "\n".join(job.result["suggested_items"])))
    if role != STUDENT and not scoped and not job.source.get("summary_only"):
        goals = job.result.get("suggested_goals", {})
        combined = "\n".join(
            goal for task in job.source["tasks"] if (goal := task["goal"] or goals.get(str(task.get("id"))))
        )
        if combined:
            sections.insert(0, ("goals_md", "训练目标", combined))
    omitted = [
        image for image in images
        if image.pk in job.image_ids and f"tms-asset:image-{image.pk}" not in used
    ]
    return sections, omitted


@never_cache
@vary_on_headers("HX-Request")
@require_http_methods(["GET", "POST"])
def draft_page(request, pk=None, *, draft=None):
    draft = draft if draft is not None else get_draft(request.user, pk)
    action = request.POST.get("action") if request.method == "POST" else None
    editor = request.POST.get("editor") == "1"
    section = request.POST.get("generate_section")
    if editor and section is not None:
        action = "prepare"
    inline_edit = action == "edit" and bool(request.htmx)
    status_poll = request.method == "GET" and request.htmx and request.GET.get("generation_status") == "1"
    if draft.submitted_log_id:
        url = with_training_return(reverse("training:log_detail", args=[draft.submitted_log_id]), return_params(request.GET))
        return HttpResponse(headers={"HX-Redirect": url}) if inline_edit or status_poll else redirect(url)
    if status_poll and TrainingLogGeneration.objects.filter(
        draft=draft, status__in=log_generation.ACTIVE, status=request.GET.get("seen_status")
    ).exists():
        return HttpResponse(status=204)
    try:
        log_generation.check_draft(draft)
        current, _, _ = log_generation.source_for(draft, note_assets=action != "preview")
    except ValidationError as exc:
        error = "；".join(exc.messages)
        if action == "preview":
            return HttpResponse(error, status=400, content_type="text/plain; charset=utf-8")
        if status_poll:
            return HttpResponse(headers={"HX-Redirect": with_training_return(request.path, return_params(request.GET))})
        messages.error(request, error)
        if inline_edit:
            return render(request, "training/log_ai_draft.html#draft_editor", {"messages_oob": True})
        return page(request, "log_ai_start", "编写训练日志")
    role = current["header"]["role"]
    if action == "preview":
        return editor_preview(request, draft, current)
    note_mode = bool(draft.source.get("teaching_notes"))
    note_available = role == COACH and (
        note_mode or request.user.has_perm("notes.view_noterepo") and any(
            task_note_route(link)
            for link in TrainingTask.objects.filter(pk__in=[row["id"] for row in current["tasks"]])
            .values_list("coach_link", flat=True)
        )
    )
    if request.GET.get("note_candidates") == "1":
        return note_candidates(request, draft, current, note_available)
    generation_values = {}
    if action == "image":
        generation_values = {key: request.POST[key] for key in LogGenerationForm.base_fields if key in request.POST}
    generation_form = LogGenerationForm(
        request.POST if action == "prepare" else None,
        draft=draft,
        role=role,
        initial=generation_values,
    )
    image_form = LogImageForm(
        request.POST if action in {"image", "prepare"} else None,
        request.FILES if action in {"image", "prepare"} else None,
        available=available_progress_images(draft, current),
    )
    body_form = DraftBodyForm(
        request.POST if action and (editor or action == "edit") else None,
        role=role, draft=draft, source=current if editor or action != "edit" else None,
    )
    saved = False
    error = ""
    if action:
        try:
            if editor:
                success_url = handle_editor_action(request, draft, action, generation_form, image_form, body_form, section)
            elif action in {"note_manual", "note_summary", "note_rebuild"}:
                success_url = note_action(request, draft)
            else:
                success_url = handle_action(request, draft, action, generation_form, image_form, body_form)
        except (ValidationError, DocumentError, DocumentRenderError) as exc:
            field_errors = getattr(exc, "error_dict", {})
            if field_errors and field_errors.keys() <= body_form.fields.keys():
                for field, errors in field_errors.items():
                    body_form.add_error(field, ValidationError(errors))
            else:
                error = "；".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        else:
            if success_url:
                success_url = with_training_return(success_url, return_params(request.GET))
                if action == "image" and generation_values:
                    draft.refresh_from_db()
                    image_form = LogImageForm(available=available_progress_images(draft, current))
                    body_form = DraftBodyForm(role=role, draft=draft, source=current)
                elif not inline_edit:
                    return redirect(f"{success_url}#draft-editor" if action == "edit" else success_url)
                else:
                    saved = True
                    draft.refresh_from_db()
                    body_form = DraftBodyForm(role=role, draft=draft, source=current if editor else None)
    job = TrainingLogGeneration.objects.select_related("model").filter(draft=draft).first() if draft.pk else None
    images = list(draft.images.defer("content").order_by("pk")) if draft.pk else []
    can_view_job = False
    host, result, preview_message = "", [], ""
    review_images, omitted_images = [], []
    if job:
        try:
            check_source_access(job.source, current)
        except ValidationError:
            pass
        else:
            can_view_job = not changed_sources(job.source, current)
            if job.model and job.model.revision == job.model_revision:
                host = urlsplit(job.model.base_url).hostname
            if can_view_job and job.status == Status.REVIEW:
                payload = json.loads(job.message)
                if not job.source.get("generated_sections"):
                    payload.pop("教练日志技术参考", None)
                preview_message = json.dumps(payload, ensure_ascii=False, indent=2)
                review_images = [image for image in images if image.pk in job.image_ids]
            if can_view_job and job.status == Status.READY:
                result, omitted_images = candidate_sections(job, role, images)
    if status_poll:
        if not job or job.status == Status.REVIEW:
            return HttpResponse(headers={"HX-Redirect": with_training_return(request.path, return_params(request.GET))})
        return render(
            request,
            "training/log_ai_draft.html#generation_status",
            {
                "draft": draft,
                "job": job,
                "can_view_job": can_view_job,
                "result": result,
                "running": job.status in log_generation.ACTIVE,
                "omitted_images": omitted_images,
            },
        )
    can_preview, changes = True, []
    reset_note = False
    upgrade_note_images = note_mode and can_refresh_note_images(draft.source, current)
    if draft.source:
        try:
            check_source_access(draft.source, current)
            changes = changed_sources(draft.source, current)
        except ValidationError as exc:
            error = error or "；".join(exc.messages)
            can_preview = False
            reset_note = note_available and note_mode
    if error:
        messages.error(request, error)
    report_log_form_errors(request, body_form, generation_form, image_form)
    if inline_edit:
        return render(
            request,
            "training/log_ai_draft.html#draft_editor",
            {
                "draft": draft,
                "body_form": body_form,
                "can_preview": can_preview,
                "can_prepare": False,
                "messages_oob": True,
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
        "补交历史训练日志" if draft.training_date < timezone.localdate() else "编写训练日志",
        note_available=note_available,
        reset_note=reset_note or upgrade_note_images,
        upgrade_note_images=upgrade_note_images and not reset_note,
        draft=draft,
        task_rows=[{**entry, "goal_edit_url": edit_links.get(entry["id"])} for entry in current["tasks"]],
        coach_reference_count=len(current.get("coach_logs", [])),
        coach_reference_tasks=[
            task["title"]
            for task in current["tasks"]
            if any(task["id"] in log["task_ids"] for log in current.get("coach_logs", []))
        ],
        has_personal_progress=any(task["filled"] for task in current["tasks"]),
        preview_message=preview_message,
        role=role,
        generation_form=generation_form,
        image_form=image_form,
        body_form=body_form,
        job=job,
        host=host,
        result=result,
        review_images=review_images,
        omitted_images=omitted_images,
        has_model=has_model,
        can_prepare=has_model and not (job and job.status in (*log_generation.ACTIVE, Status.READY, Status.REVIEW)),
        can_add_model=can_manage(request.user),
        upload_url=training_upload_url(draft.cycle_id, draft.training_date),
        expand_extras=bool(
            generation_form.errors or image_form.errors or action == "image" or (error and action == "prepare")
        ),
        running=bool(job and job.status in log_generation.ACTIVE),
        can_preview=can_preview,
        can_view_job=can_view_job,
        changes=changes,
        source_digest=source_digest(current),
        images=[image for image in images if str(image.pk) not in draft.source.get("note_image_rows", {})],
        progress_url=training_day_url("training:daily_progress", draft.cycle_id, draft.training_date)
        if role == STUDENT and current["tasks"]
        else "",
    )


def note_action(request, draft):
    form = LogActionForm(request.POST)
    if not form.is_valid():
        raise ValidationError("操作参数有误，请刷新后重试。")
    rebuild = request.POST["action"] == "note_rebuild"
    if rebuild and not form.cleaned_data["accept_changes"]:
        raise ValidationError("请确认按当前可用素材重新建立草稿。")
    draft = import_note_draft(
        draft, form.cleaned_data["revision"], form.cleaned_data["source_digest"], rebuild=rebuild
    )
    if request.POST["action"] == "note_summary":
        try:
            pk, revision = signing.loads(request.POST.get("model", ""), salt="note-summary-model")
            model = log_generation.selected_model(draft.author, pk, revision)
            log_generation.queue_note_summary(
                draft, model, request.POST.get("summary_digest", ""), revision=draft.revision
            )
        except (ValidationError, signing.BadSignature) as exc:
            detail = "；".join(exc.messages) if isinstance(exc, ValidationError) else "请选择有效模型。"
            messages.error(request, f"教学笔记正文已保存。{detail}")
    return reverse("training:log_ai_draft", args=[draft.pk])


def note_candidates(request, draft, current, available):
    if not available:
        raise Http404
    try:
        if draft.source:
            check_source_access(draft.source, current)
        if current.get("teaching_notes"):
            current, _, _ = collect_sources(draft.author, draft.cycle, draft.training_date)
        snapshot, body, warnings = build_note_draft(draft.author, current)
    except ValidationError as exc:
        return render(request, "training/log_ai_draft.html#note_candidates", {"warnings": exc.messages})
    notes = [row for row in snapshot["tasks"] if row["note_ref"]]
    return render(
        request, "training/log_ai_draft.html#note_candidates", {
            "notes": notes,
            "warnings": warnings,
            "note_digest": source_digest(snapshot),
            "candidates": [
                (key, label, body[key]) for key, label in editor_fields(COACH)
                if key in NOTE_SECTIONS and body[key].strip()
            ],
        },
    )


def handle_editor_action(request, draft, action, generation_form, image_form, body_form, section):
    if not body_form.is_valid():
        return None
    data = body_form.cleaned_data.copy()
    revision = data.pop("revision")
    reference_text = ""
    if action in {"prepare", "image"}:
        if action == "prepare" and (request.FILES.getlist("images") or request.POST.getlist("progress_images")):
            raise ValidationError("有尚未保存的日志插图，请先点击「保存插图」再预览。")
        if not image_form.is_valid() or (action == "prepare" and not generation_form.is_valid()):
            return None
        if action == "prepare":
            reference_text = fetch_reference_pages(generation_form.cleaned_data["references"])
    with transaction.atomic():
        locked = log_generation.lock_draft(draft)
        if locked.revision != revision:
            raise ValidationError("草稿已更新，请重新加载后编辑。")
        current, _, _ = log_generation.source_for(locked, note_assets=False)
        role = current["header"]["role"]
        source = locked.source or current
        if action == "submit":
            try:
                validate_editor_body(role, data, source)
            except ValidationError as exc:
                if hasattr(exc, "error_dict"):
                    for key, errors in exc.error_dict.items():
                        body_form.add_error(key, ValidationError(errors))
                    return None
                raise
        if action == "edit" or not locked.source.get("editor") or data != {
            key: locked.body.get(key, "") for key, _ in editor_fields(role)
        }:
            log_generation.edit_draft(locked, revision, data, editor=True)
            locked.refresh_from_db()
        if action == "edit":
            messages.success(request, "已保存草稿正文。")
        elif action == "prepare":
            log_generation.prepare_generation(
                locked, **generation_form.cleaned_data, section=section or "all", reference_text=reference_text,
            )
        elif action == "note_apply":
            import_note_draft(
                locked, locked.revision, request.POST.get("note_digest", ""),
                sections=request.POST.getlist("note_sections"),
            )
            messages.success(request, "已采用所选教学笔记区块。")
        elif action == "apply":
            form = LogActionForm(request.POST)
            if not form.is_valid() or not form.cleaned_data["generation"]:
                raise ValidationError("生成结果已失效，请刷新后重试。")
            log_generation.resolve_generation(
                locked, form.cleaned_data["generation"], apply=True, revision=locked.revision,
                sections=request.POST.getlist("candidate_sections"),
            )
        elif action == "submit":
            log = submit_draft(
                locked, locked.revision, request.POST.get("source_digest", ""), request.POST.get("accept_changes") == "on",
                origin=request.build_absolute_uri("/"),
            )
            messages.success(request, "已提交训练日志并归档 PDF。")
            return reverse("training:log_detail", args=[log.pk])
        else:
            return handle_action(request, locked, action, generation_form, image_form, body_form)
    return reverse("training:log_ai_draft", args=[draft.pk])


def handle_action(request, draft, action, generation_form, image_form, body_form):
    if action in {"prepare", "image"}:
        if action == "prepare" and (request.FILES.getlist("images") or request.POST.getlist("progress_images")):
            raise ValidationError("有尚未保存的日志插图，请先点击「保存插图」再预览。")
        images_valid = image_form.is_valid()
        generation_valid = action == "image" or generation_form.is_valid()
        if not images_valid or not generation_valid:
            return None
        if action == "image":
            add_images(
                draft,
                image_form.cleaned_data["images"],
                set(image_form.cleaned_data["progress_images"].values_list("pk", flat=True)),
            )
            messages.success(request, "已保存日志插图。")
        else:
            values = generation_form.cleaned_data
            log_generation.prepare_generation(
                draft,
                **values,
                reference_text=fetch_reference_pages(values["references"]),
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
        elif action == "cancel":
            log_generation.cancel_generation(draft, data["generation"])
        elif action in {"apply", "discard"}:
            log_generation.resolve_generation(
                draft,
                data["generation"],
                apply=action == "apply",
                revision=data["revision"],
            )
        elif action == "submit":
            log = submit_draft(
                draft, data["revision"], data["source_digest"], data["accept_changes"],
                origin=request.build_absolute_uri("/"),
            )
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


@xframe_options_sameorigin
def editor_preview(request, draft, current):
    role = current["header"]["role"]
    form = DraftBodyForm(request.POST, role=role, draft=draft, source=current)
    try:
        source = {**(draft.source or current), "editor": True}
        if draft.source:
            check_source_access(draft.source, current)
        if not form.is_valid():
            raise ValidationError("请检查正文栏目和长度限制。")
        body = form.cleaned_data.copy()
        revision = body.pop("revision")
        if revision != draft.revision:
            raise ValidationError("草稿已更新，请重新加载后预览。")
        if "task_title" in draft.body:
            body["task_title"] = draft.body["task_title"]
        draft.body = validate_editor_body(role, body, source, partial=True)
        draft.source = source
    except ValidationError as exc:
        return HttpResponse("；".join(exc.messages), status=400, content_type="text/plain; charset=utf-8")
    return html_response(
        draft_document(draft, origin=request.build_absolute_uri("/")),
        draft.images.all() if draft.pk else [],
    )


@never_cache
@xframe_options_sameorigin
@require_GET
def draft_preview(request, pk):
    draft = get_draft(request.user, pk)
    try:
        current, _, _ = log_generation.source_for(draft, note_assets=False)
        check_source_access(draft.source, current)
    except ValidationError as exc:
        return HttpResponse("；".join(exc.messages), status=400, content_type="text/plain; charset=utf-8")
    return html_response(draft_document(draft, origin=request.build_absolute_uri("/")), draft.images.all())


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
        if draft.source.get("teaching_notes"):
            current, _, _ = log_generation.source_for(draft, note_assets=False)
            check_source_access(draft.source, current)
    except ValidationError as exc:
        raise PermissionDenied from exc
    image = get_object_or_404(draft.images, pk=image_pk)
    if image.media_type == "image/svg+xml":
        raise Http404
    return HttpResponse(bytes(image.content), content_type=image.media_type)


@never_cache
@require_http_methods(["GET", "POST"])
def log_settings(request):
    from .log_ai_forms import LogPromptForm
    from .models import TrainingCycleMember, TrainingLogPrompt

    if not request.user.is_active or not request.user.is_superuser:
        raise PermissionDenied

    configs = {item.role: item for item in TrainingLogPrompt.objects.all()}
    prompt_forms = []
    editing_prompt = request.method == "POST" and request.POST.get("action") == "prompts"
    for role in (TrainingCycleMember.Role.COACH, TrainingCycleMember.Role.COMPETITOR):
        prompt = configs.get(role) or TrainingLogPrompt(role=role)
        initial = {"instructions": prompt.instructions or log_generation.default_instructions(role)}
        prompt_forms.append(
            (
                role.label,
                LogPromptForm(request.POST if editing_prompt else None, instance=prompt, prefix=role, initial=initial),
                log_generation.generation_constraints(role),
            )
        )
    if editing_prompt:
        valid = [form.is_valid() for _, form, _ in prompt_forms]
        if all(valid):
            with transaction.atomic():
                for _, form, _ in prompt_forms:
                    TrainingLogPrompt.objects.update_or_create(role=form.instance.role, defaults=form.cleaned_data)
            messages.success(request, "已保存写作提示词。")
            return redirect(request.get_full_path())

    return page(
        request,
        "log_settings",
        "训练日志设置",
        prompt_forms=prompt_forms,
    )
