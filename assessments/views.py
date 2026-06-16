from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from .forms import AssessmentFileUploadForm
from .models import Assessment, AssessmentAttachment, AssessmentModule
from .permissions import (
    can_access_assessment_detail,
    can_lock_assessment_module,
    can_manage_assessment_module,
    can_unlock_assessment_module,
)
from .selectors import build_assessment_list_context, build_assessment_score_table_context
from .services import set_material_lock_state, set_score_lock_state


@login_required
def assessment_list(request):
    """
    显示考核列表
    - 普通用户：显示参与的考核及自己的成绩（当前+历史）
    - 有权限用户：显示所有考核列表，点击进入详情查看所有人成绩
    - 负责教练：显示自己负责模块所属的考核，点击进入详情管理资料/评分归档
    """
    context = {
        **build_assessment_list_context(request.user),
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
@require_POST
def module_score_lock(request, module_id):
    assessment_module = get_object_or_404(
        AssessmentModule.objects.select_related("assessment", "module", "responsible_coach"),
        pk=module_id,
    )
    action = request.POST.get("action")

    if action == "lock":
        if not can_lock_assessment_module(request.user, assessment_module):
            raise PermissionDenied("只有负责该模块的教练或管理员可以锁定评分归档")
        if assessment_module.is_locked:
            messages.info(request, "该模块成绩已经锁定。")
        else:
            set_score_lock_state(assessment_module, is_locked=True, user=request.user)
            messages.success(request, f"{assessment_module.module.name} 评分归档已锁定。")
    elif action == "unlock":
        if not can_unlock_assessment_module(request.user):
            raise PermissionDenied("只有管理员可以解锁成绩")
        if not assessment_module.is_locked:
            messages.info(request, "该模块成绩当前未锁定。")
        else:
            set_score_lock_state(assessment_module, is_locked=False)
            messages.success(request, f"{assessment_module.module.name} 评分归档已解锁。")
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

    form = AssessmentFileUploadForm(instance=assessment_module)
    if field_name not in form.fields:
        messages.error(request, "无效的文件字段")
        return redirect("assessments:file_upload", module_id=module_id)

    file_field = getattr(assessment_module, field_name)
    if file_field:
        file_field.delete(save=True)
        messages.success(request, "文件已删除")

    if request.headers.get("HX-Request"):
        html = render_to_string(
            "assessments/partials/file_uploader_wrapper.html",
            {
                "field": form[field_name],
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
