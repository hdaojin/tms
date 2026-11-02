from io import BytesIO

from django import forms
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_GET, require_http_methods

from core.uploads import SCORING_WORKBOOK_UPLOAD_SPEC
from core.utils.forms import StyledFormMixin
from . import scheduling
from .plan_workbooks import build_plan_workbook, preview_import, ROUNDTRIP_NOTICE
from .schedule_views import get_plan, render, _success


class PlanWorkbookForm(StyledFormMixin, forms.Form):
    file = forms.FileField(
        label="训练计划 Excel",
        validators=SCORING_WORKBOOK_UPLOAD_SPEC.validators(),
        widget=forms.ClearableFileInput(attrs=SCORING_WORKBOOK_UPLOAD_SPEC.widget_attrs()),
    )


@require_GET
def import_template(request, pk):
    plan = get_plan(request.user, pk)
    if not scheduling.can_schedule(request.user, plan):
        raise PermissionDenied
    response = HttpResponse(
        build_plan_workbook(plan, request.user, import_template=True),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = content_disposition_header(True, f"{plan.title}-导入模板.xlsx")
    return response


@require_http_methods(["GET", "POST"])
def import_plan(request, pk):
    plan = get_plan(request.user, pk)
    if not scheduling.can_schedule(request.user, plan):
        raise PermissionDenied
    form = PlanWorkbookForm(request.POST or None, request.FILES or None)
    records, token, error = [], "", ""
    if request.method == "POST":
        try:
            if request.POST.get("token"):
                data = signing.loads(request.POST["token"], salt="training.import", max_age=600)
                if data["user"] != request.user.pk or data["plan"] != plan.pk:
                    raise PermissionDenied
                current_members = list(
                    plan.participants.filter(was_initial=True).order_by("user_id").values_list("user_id", flat=True)
                )
                if data["members"] != current_members or data["published"] != bool(plan.schedule_published_at):
                    raise ValidationError("计划选手范围或排班阶段已经变化，请重新预览。")
                result = scheduling.save_schedule(plan, request.user, data["payload"], request.POST.get("reason", ""))
                return _success(
                    request, plan, "有效内容已提交审批。" if result else "有效内容已导入，任务草稿须另行发布。"
                )
            if form.is_valid():
                file = form.cleaned_data["file"]
                SCORING_WORKBOOK_UPLOAD_SPEC.validate_file(file)
                records, payload = preview_import(plan, request.user, BytesIO(file.read()))
                if payload:
                    token = signing.dumps(
                        {
                            "user": request.user.pk,
                            "plan": plan.pk,
                            "payload": payload,
                            "members": list(
                                plan.participants.filter(was_initial=True)
                                .order_by("user_id")
                                .values_list("user_id", flat=True)
                            ),
                            "published": bool(plan.schedule_published_at),
                        },
                        salt="training.import",
                        compress=True,
                    )
        except (signing.BadSignature, ValidationError) as exc:
            error = (
                "；".join(exc.messages) if isinstance(exc, ValidationError) else "导入预览已过期或被修改，请重新上传。"
            )
    return render(
        request,
        "training/workbook_import.html",
        {
            "plan": plan,
            "form": form,
            "records": records,
            "token": token,
            "error": error,
            "notice": ROUNDTRIP_NOTICE,
            "is_fragment": bool(request.htmx),
        },
    )
