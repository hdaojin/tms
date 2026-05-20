from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import AssessmentFileUploadForm, ModuleScoreBatchForm
from .models import Assessment, AssessmentAttachment, AssessmentModule, Score
from .permissions import (
    can_access_assessment_detail,
    can_lock_assessment_module,
    can_manage_assessment_module,
    can_unlock_assessment_module,
    is_coach,
)
from .selectors import build_assessment_score_table_context
from .services import set_material_lock_state, set_score_lock_state


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
    if is_coach(request.user):
        managed_assessments = (
            Assessment.objects.filter(assessmentmodule__responsible_coach=request.user)
            .select_related("training_cycle")
            .prefetch_related("assessmentmodule_set__module")
            .distinct()
            .order_by("-start_date")
        )
    show_management_actions = can_view_all or managed_assessments.exists()

    if can_view_all:
        assessments = Assessment.objects.select_related("training_cycle").prefetch_related("assessmentmodule_set__module").order_by(
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
            .select_related("training_cycle")
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
    if not can_access_assessment_detail(request.user, assessment):
        raise PermissionDenied("你没有权限查看该考核详情")

    sort_param = request.GET.get("sort", "-total")
    table_context = build_assessment_score_table_context(
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
    if not can_manage_assessment_module(request.user, assessment_module):
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
        if not can_lock_assessment_module(request.user, assessment_module):
            raise PermissionDenied("只有负责该模块的教练或管理员可以锁定成绩")
        if assessment_module.is_locked:
            messages.info(request, "该模块成绩已经锁定。")
        else:
            set_score_lock_state(assessment_module, is_locked=True, user=request.user)
            messages.success(request, f"{assessment_module.module.name} 成绩已锁定。")
    elif action == "unlock":
        if not can_unlock_assessment_module(request.user):
            raise PermissionDenied("只有管理员可以解锁成绩")
        if not assessment_module.is_locked:
            messages.info(request, "该模块成绩当前未锁定。")
        else:
            set_score_lock_state(assessment_module, is_locked=False)
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
        if not can_lock_assessment_module(request.user, assessment_module):
            raise PermissionDenied("只有负责该模块的教练或管理员可以锁定资料")
        if assessment_module.is_material_locked:
            messages.info(request, "该模块资料已经锁定。")
        else:
            set_material_lock_state(assessment_module, is_locked=True, user=request.user)
            messages.success(request, f"{assessment_module.module.name} 资料已锁定。")
    elif action == "unlock":
        if not can_unlock_assessment_module(request.user):
            raise PermissionDenied("只有管理员可以解锁资料")
        if not assessment_module.is_material_locked:
            messages.info(request, "该模块资料当前未锁定。")
        else:
            set_material_lock_state(assessment_module, is_locked=False)
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
    if not can_manage_assessment_module(request.user, assessment_module):
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
    if not can_manage_assessment_module(request.user, assessment_module):
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
    if not can_manage_assessment_module(request.user, attachment.assessment_module):
        raise PermissionDenied("只有负责该模块的教练可以删除附件")
    if attachment.assessment_module.is_material_locked:
        raise PermissionDenied("该模块资料已锁定，无法删除附件")

    module_id = attachment.assessment_module_id
    attachment.delete()
    messages.success(request, "附件已删除")

    if request.headers.get("HX-Request"):
        return HttpResponse("")

    return redirect("assessments:file_upload", module_id=module_id)
