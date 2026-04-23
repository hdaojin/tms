from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.constants import GROUP_COACH

from .forms import AssessmentFileUploadForm, ModuleScoreBatchForm
from .models import Assessment, AssessmentAttachment, AssessmentModule, Score


def _is_coach(user):
    return user.is_authenticated and user.groups.filter(name=GROUP_COACH).exists()


def _is_superuser(user):
    return user.is_authenticated and user.is_superuser


def _get_managed_modules_queryset(user, assessment=None):
    queryset = AssessmentModule.objects.select_related(
        "assessment", "module", "responsible_coach"
    )
    if assessment is not None:
        queryset = queryset.filter(assessment=assessment)
    if not _is_coach(user):
        return queryset.none()
    return queryset.filter(responsible_coach=user).order_by(
        "sort_order", "module__code", "pk"
    )


def _can_access_assessment_detail(user, assessment):
    return (
        user.is_superuser
        or user.has_perm("assessments.view_all_scores")
        or _get_managed_modules_queryset(user, assessment).exists()
    )


def _can_manage_assessment_module(user, assessment_module):
    return _is_coach(user) and assessment_module.responsible_coach_id == user.id


def _can_lock_assessment_module(user, assessment_module):
    return _is_superuser(user) or _can_manage_assessment_module(user, assessment_module)


def _can_unlock_assessment_module(user):
    return _is_superuser(user)


def _set_score_lock_state(assessment_module, *, is_locked, user=None):
    assessment_module.is_locked = is_locked
    assessment_module.locked_at = timezone.now() if is_locked else None
    assessment_module.locked_by = user if is_locked else None
    assessment_module.save(update_fields=["is_locked", "locked_at", "locked_by"])


def _set_material_lock_state(assessment_module, *, is_locked, user=None):
    assessment_module.is_material_locked = is_locked
    assessment_module.material_locked_at = timezone.now() if is_locked else None
    assessment_module.material_locked_by = user if is_locked else None
    assessment_module.save(
        update_fields=[
            "is_material_locked",
            "material_locked_at",
            "material_locked_by",
        ]
    )


def _get_assessment_modules_queryset(assessment):
    return (
        AssessmentModule.objects.select_related("module", "responsible_coach")
        .prefetch_related("attachments")
        .filter(assessment=assessment)
        .order_by("sort_order", "module__code", "pk")
    )


def _build_assessment_score_table_context(assessment, sort_param, user=None):
    sort_param = (sort_param or "-total").strip() or "-total"
    modules = list(_get_assessment_modules_queryset(assessment))

    for assessment_module in modules:
        attachments = list(assessment_module.attachments.all())
        assessment_module.attachment_count = len(attachments)
        assessment_module.has_attachments = bool(attachments)
        assessment_module.has_any_material = bool(
            assessment_module.question_file
            or assessment_module.scoring_standard_file
            or assessment_module.scoring_sheet_file
            or assessment_module.scoring_script_file
            or assessment_module.has_attachments
        )
        can_manage = _can_manage_assessment_module(user, assessment_module) if user else False
        can_lock = _can_lock_assessment_module(user, assessment_module) if user else False
        can_unlock = _can_unlock_assessment_module(user) if user else False
        assessment_module.can_manage = can_manage
        assessment_module.can_manage_scores = can_manage
        assessment_module.can_manage_materials = can_manage
        assessment_module.can_lock_scores = can_lock and not assessment_module.is_locked
        assessment_module.can_unlock_scores = can_unlock and assessment_module.is_locked
        assessment_module.can_lock_materials = (
            can_lock and not assessment_module.is_material_locked
        )
        assessment_module.can_unlock_materials = (
            can_unlock and assessment_module.is_material_locked
        )

    participants = assessment.participants.all().order_by(
        "last_name", "first_name", "username"
    )
    all_scores = Score.objects.filter(assessment_module__assessment=assessment).select_related(
        "user", "assessment_module"
    )
    score_map = {
        (score.user_id, score.assessment_module_id): score for score in all_scores
    }

    table_rows = []
    for participant in participants:
        row = {
            "user": participant,
            "scores": [],
        }
        total_score = 0
        rank_score = 0

        for assessment_module in modules:
            score_obj = score_map.get((participant.pk, assessment_module.pk))
            value = score_obj.score if score_obj else 0
            row["scores"].append(
                {
                    "module_id": assessment_module.pk,
                    "val": value,
                    "obj": score_obj,
                    "can_manage": assessment_module.can_manage,
                }
            )
            if score_obj:
                total_score += value
                if "english" not in assessment_module.module.name.lower():
                    rank_score += value

        row["total"] = total_score
        row["rank_score"] = rank_score
        table_rows.append(row)

    if sort_param.startswith("-"):
        sort_key = sort_param[1:]
        reverse = True
    else:
        sort_key = sort_param
        reverse = False

    def get_sort_value(row):
        if sort_key == "total":
            return row["rank_score"]
        if sort_key == "grand_total":
            return row["total"]
        if sort_key.startswith("module_"):
            try:
                module_id = int(sort_key.split("_")[1])
            except (ValueError, IndexError):
                return 0
            for score in row["scores"]:
                if score["module_id"] == module_id:
                    return score["val"]
        return 0

    table_rows.sort(key=lambda item: item["rank_score"], reverse=True)
    current_rank = 1
    for index, row in enumerate(table_rows):
        if index > 0 and row["rank_score"] < table_rows[index - 1]["rank_score"]:
            current_rank = index + 1
        row["rank"] = current_rank

    if sort_param != "-total":
        table_rows.sort(key=get_sort_value, reverse=reverse)

    max_ranking_score = 0
    max_grand_total_score = 0
    for assessment_module in modules:
        max_grand_total_score += assessment_module.max_score
        if "english" not in assessment_module.module.name.lower():
            max_ranking_score += assessment_module.max_score

    return {
        "assessment": assessment,
        "modules": modules,
        "table_rows": table_rows,
        "current_sort": sort_param,
        "max_ranking_score": max_ranking_score,
        "max_grand_total_score": max_grand_total_score,
    }


@login_required
def assessment_list(request):
    """
    显示考核列表
    - 普通用户：显示参与的考核及自己的成绩（当前+历史）
    - 有权限用户：显示所有考核列表，点击进入详情查看所有人成绩
    - 负责教练：显示自己负责模块所属的考核，点击进入详情录入成绩/管理资料
    """
    today = timezone.now().date()
    can_view_all = request.user.is_superuser or request.user.has_perm(
        "assessments.view_all_scores"
    )
    managed_assessments = Assessment.objects.none()
    if _is_coach(request.user):
        managed_assessments = (
            Assessment.objects.filter(assessmentmodule__responsible_coach=request.user)
            .prefetch_related("assessmentmodule_set__module")
            .distinct()
            .order_by("-start_date")
        )
    show_management_actions = can_view_all or managed_assessments.exists()

    if can_view_all:
        assessments = Assessment.objects.prefetch_related("assessmentmodule_set__module").order_by(
            "-start_date"
        )
    elif show_management_actions:
        assessments = managed_assessments
    else:
        user_scores_prefetch = Prefetch(
            "scores",
            queryset=Score.objects.filter(user=request.user),
            to_attr="user_score",
        )
        modules_prefetch = Prefetch(
            "assessmentmodule_set",
            queryset=AssessmentModule.objects.select_related("module").prefetch_related(
                user_scores_prefetch
            ).order_by("sort_order", "module__code", "pk"),
            to_attr="user_modules_info",
        )
        assessments = (
            Assessment.objects.filter(participants=request.user)
            .prefetch_related(modules_prefetch)
            .order_by("-start_date")
        )

    current_assessments = []
    past_assessments = []
    upcoming_assessments = []

    for assessment in assessments:
        if assessment.end_date < today:
            past_assessments.append(assessment)
        elif assessment.start_date > today:
            upcoming_assessments.append(assessment)
        else:
            current_assessments.append(assessment)

    if not show_management_actions:
        for assessment in past_assessments:
            my_total = 0
            my_grand_total = 0
            assessment.max_ranking_score = 0
            assessment.max_grand_total_score = 0

            if hasattr(assessment, "user_modules_info"):
                for assessment_module in assessment.user_modules_info:
                    score_val = 0
                    if assessment_module.user_score:
                        score_val = assessment_module.user_score[0].score

                    my_grand_total += score_val
                    assessment.max_grand_total_score += assessment_module.max_score

                    if "english" not in assessment_module.module.name.lower():
                        my_total += score_val
                        assessment.max_ranking_score += assessment_module.max_score

            assessment.my_total_score = my_total
            assessment.my_grand_total_score = my_grand_total

            valid_am_ids = assessment.assessmentmodule_set.exclude(
                module__name__icontains="english"
            ).values_list("id", flat=True)
            rank_data = (
                Score.objects.filter(assessment_module_id__in=valid_am_ids)
                .values("user")
                .annotate(total=Sum("score"))
                .order_by("-total")
            )

            my_rank = "-"
            scores_list = [data["total"] for data in rank_data]
            if my_total in scores_list:
                my_rank = scores_list.index(my_total) + 1

            assessment.my_rank = my_rank

    context = {
        "can_view_all": can_view_all,
        "show_management_actions": show_management_actions,
        "current_assessments": current_assessments,
        "past_assessments": past_assessments,
        "upcoming_assessments": upcoming_assessments,
        "title": "考核列表",
    }
    return render(request, "assessments/assessment_list.html", context)


@login_required
def assessment_detail(request, pk):
    """
    查看某次考核的所有人成绩
    - 管理员/有权限用户：可查看全部并按现有逻辑排序
    - 负责教练：可查看详情，并录入自己负责模块的成绩
    """
    assessment = get_object_or_404(Assessment, pk=pk)
    if not _can_access_assessment_detail(request.user, assessment):
        raise PermissionDenied("你没有权限查看该考核详情")

    sort_param = request.GET.get("sort", "-total")
    table_context = _build_assessment_score_table_context(
        assessment, sort_param, user=request.user
    )

    context = {
        **table_context,
        "title": f"考核详情 - {assessment.name}",
    }
    return render(request, "assessments/assessment_detail.html", context)


@login_required
def module_score_entry(request, module_id):
    """
    独立的模块分数录入页面
    - 负责教练可以批量录入 / 修改所有参考人员的成绩
    - 成绩锁定与解锁统一在考核详情页操作
    """
    assessment_module = get_object_or_404(
        AssessmentModule.objects.select_related(
            "assessment", "module", "responsible_coach",
        ),
        pk=module_id,
    )
    if not _can_manage_assessment_module(request.user, assessment_module):
        raise PermissionDenied("只有负责该模块的教练可以录入成绩")

    if request.method == "POST":
        if assessment_module.is_locked:
            raise PermissionDenied("该模块成绩已锁定，无法修改")

        form = ModuleScoreBatchForm(request.POST, assessment_module=assessment_module)
        if form.is_valid():
            saved = form.save()
            messages.success(request, f"已保存 {len(saved)} 条成绩。")
            return redirect("assessments:module_score_entry", module_id=module_id)
    else:
        form = ModuleScoreBatchForm(assessment_module=assessment_module)

    context = {
        "assessment_module": assessment_module,
        "assessment": assessment_module.assessment,
        "form": form,
        "title": f"{assessment_module.module.code} - {assessment_module.module.name} 成绩录入",
        "title_icon": "icon-[tabler--edit-circle]",
    }
    return render(request, "assessments/module_score_entry.html", context)


@login_required
@require_POST
def module_score_lock(request, module_id):
    assessment_module = get_object_or_404(
        AssessmentModule.objects.select_related("assessment", "module", "responsible_coach"),
        pk=module_id,
    )
    action = request.POST.get("action")

    if action == "lock":
        if not _can_lock_assessment_module(request.user, assessment_module):
            raise PermissionDenied("只有负责该模块的教练或管理员可以锁定成绩")
        if assessment_module.is_locked:
            messages.info(request, "该模块成绩已经锁定。")
        else:
            _set_score_lock_state(assessment_module, is_locked=True, user=request.user)
            messages.success(request, f"{assessment_module.module.name} 成绩已锁定。")
    elif action == "unlock":
        if not _can_unlock_assessment_module(request.user):
            raise PermissionDenied("只有管理员可以解锁成绩")
        if not assessment_module.is_locked:
            messages.info(request, "该模块成绩当前未锁定。")
        else:
            _set_score_lock_state(assessment_module, is_locked=False)
            messages.success(request, f"{assessment_module.module.name} 成绩已解锁。")
    else:
        raise PermissionDenied("无效的成绩锁定操作")

    return redirect("assessments:detail", pk=assessment_module.assessment.pk)


@login_required
@require_POST
def module_material_lock(request, module_id):
    assessment_module = get_object_or_404(
        AssessmentModule.objects.select_related("assessment", "module", "responsible_coach"),
        pk=module_id,
    )
    action = request.POST.get("action")

    if action == "lock":
        if not _can_lock_assessment_module(request.user, assessment_module):
            raise PermissionDenied("只有负责该模块的教练或管理员可以锁定资料")
        if assessment_module.is_material_locked:
            messages.info(request, "该模块资料已经锁定。")
        else:
            _set_material_lock_state(assessment_module, is_locked=True, user=request.user)
            messages.success(request, f"{assessment_module.module.name} 资料已锁定。")
    elif action == "unlock":
        if not _can_unlock_assessment_module(request.user):
            raise PermissionDenied("只有管理员可以解锁资料")
        if not assessment_module.is_material_locked:
            messages.info(request, "该模块资料当前未锁定。")
        else:
            _set_material_lock_state(assessment_module, is_locked=False)
            messages.success(request, f"{assessment_module.module.name} 资料已解锁。")
    else:
        raise PermissionDenied("无效的资料锁定操作")

    return redirect("assessments:detail", pk=assessment_module.assessment.pk)


@login_required
def assessment_file_upload(request, module_id):
    """
    考核资料上传页面
    针对特定的考核模块上传各种资料
    只有负责该模块的教练可以访问，资料锁定后仅可只读查看
    """
    assessment_module = get_object_or_404(
        AssessmentModule.objects.select_related(
            "assessment", "module", "responsible_coach"
        ),
        pk=module_id,
    )
    if not _can_manage_assessment_module(request.user, assessment_module):
        raise PermissionDenied("只有负责该模块的教练可以上传考核资料")

    if request.method == "POST":
        if assessment_module.is_material_locked:
            raise PermissionDenied("该模块资料已锁定，无法修改")

        form = AssessmentFileUploadForm(
            request.POST,
            request.FILES,
            instance=assessment_module,
        )

        if form.is_valid():
            form.save()

            attachment_files = request.FILES.getlist("attachments")
            if attachment_files:
                for file in attachment_files:
                    AssessmentAttachment.objects.create(
                        assessment_module=assessment_module,
                        file=file,
                    )

            messages.success(request, f"已成功保存 {assessment_module.module.name} 的考核资料")
            return redirect("assessments:detail", pk=assessment_module.assessment.pk)
    else:
        form = AssessmentFileUploadForm(instance=assessment_module)

    context = {
        "assessment_module": assessment_module,
        "form": form,
        "can_edit_materials": not assessment_module.is_material_locked,
        "existing_attachments": assessment_module.attachments.all(),
        "title": f"{assessment_module.assessment.name} - {assessment_module.module.name} 资料上传",
        "title_icon": "icon-[tabler--file-upload]",
    }
    return render(request, "assessments/file_upload.html", context)


@login_required
def delete_module_file(request, module_id, field_name):
    """
    删除考核模块的单个文件（试题、评分标准、评分表、评分脚本）
    """
    assessment_module = get_object_or_404(
        AssessmentModule.objects.select_related("assessment", "responsible_coach"),
        pk=module_id,
    )
    if not _can_manage_assessment_module(request.user, assessment_module):
        raise PermissionDenied("只有负责该模块的教练可以删除考核资料")
    if assessment_module.is_material_locked:
        raise PermissionDenied("该模块资料已锁定，无法删除")

    field_config = {
        "question_file": {
            "label": "试题文件",
            "accept": ".pdf,.doc,.docx,.xls,.xlsx,.zip",
            "required": False,
            "help_text": "上传试题文件",
        },
        "scoring_standard_file": {
            "label": "评分标准文件",
            "accept": ".pdf,.doc,.docx,.xls,.xlsx",
            "required": False,
            "help_text": "上传评分标准文件",
        },
        "scoring_sheet_file": {
            "label": "评分表文件",
            "accept": ".pdf,.xls,.xlsx",
            "required": False,
            "help_text": "上传评分表文件（非必须）",
        },
        "scoring_script_file": {
            "label": "评分脚本文件",
            "accept": ".py,.sh,.zip",
            "required": False,
            "help_text": "上传评分脚本文件（非必须）",
        },
    }

    if field_name not in field_config:
        messages.error(request, "无效的文件字段")
        return redirect("assessments:file_upload", module_id=module_id)

    file_field = getattr(assessment_module, field_name)
    if file_field:
        file_field.delete(save=True)
        messages.success(request, "文件已删除")

    if request.headers.get("HX-Request"):
        config = field_config[field_name]
        html = render_to_string(
            "assessments/partials/file_uploader_wrapper.html",
            {
                "name": field_name,
                "accept": config["accept"],
                "required": config["required"],
                "label": config["label"],
                "help_text": config["help_text"],
                "field_name": field_name,
            },
            request=request,
        )
        return HttpResponse(html)

    return redirect("assessments:file_upload", module_id=module_id)


@login_required
def delete_attachment(request, attachment_id):
    """
    删除考核模块附件
    """
    attachment = get_object_or_404(
        AssessmentAttachment.objects.select_related(
            "assessment_module__assessment",
            "assessment_module__responsible_coach",
        ),
        pk=attachment_id,
    )
    if not _can_manage_assessment_module(request.user, attachment.assessment_module):
        raise PermissionDenied("只有负责该模块的教练可以删除附件")
    if attachment.assessment_module.is_material_locked:
        raise PermissionDenied("该模块资料已锁定，无法删除附件")

    module_id = attachment.assessment_module_id
    attachment.delete()
    messages.success(request, "附件已删除")

    if request.headers.get("HX-Request"):
        return HttpResponse("")

    return redirect("assessments:file_upload", module_id=module_id)
