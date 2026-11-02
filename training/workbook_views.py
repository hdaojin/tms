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
from .plan_workbooks import build_plan_workbook, confirm_import, preview_import, ROUNDTRIP_NOTICE
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
    if not scheduling.can_schedule(request.user, plan) or not request.user.has_perm("training.add_trainingtask"):
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
    if not scheduling.can_schedule(request.user, plan) or not request.user.has_perm("training.add_trainingtask"):
        raise PermissionDenied
    form = PlanWorkbookForm(request.POST or None, request.FILES or None)
    records, token, error, participants = [], "", "", []
    if request.method == "POST":
        try:
            if request.POST.get("token"):
                data = signing.loads(request.POST["token"], salt="training.import", max_age=600)
                if data["user"] != request.user.pk or data["plan"] != plan.pk:
                    raise PermissionDenied
                confirm_import(plan, request.user, data["payload"], data["members"])
                return _success(request, plan, "排班和任务草稿已导入，请分别发布。")
            if form.is_valid():
                file = form.cleaned_data["file"]
                SCORING_WORKBOOK_UPLOAD_SPEC.validate_file(file)
                records, payload = preview_import(plan, request.user, BytesIO(file.read()))
                if payload:
                    participants = list(plan.participants.filter(is_active=True).select_related("user").order_by("user_id"))
                    token = signing.dumps(
                        {
                            "user": request.user.pk,
                            "plan": plan.pk,
                            "payload": payload,
                            "members": [participant.user_id for participant in participants],
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
            "participants": participants,
        },
    )
