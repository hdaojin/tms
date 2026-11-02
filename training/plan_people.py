"""计划职责人员复用会议选人交互，候选搜索独立校验计划权限。"""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db.models.functions import Concat
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_GET

from accounts.services.users import get_user_full_info
from meetings.widgets import RecipientSelect
from .scheduling import plan_manager, visible_plans


def eligible_staff(role):
    codename = {
        "schedulers": "schedule_trainingplan",
        "approvers": "approve_trainingplan",
    }[role]
    return get_user_model().objects.filter(is_active=True).filter(
        Q(is_superuser=True)
        | Q(user_permissions__content_type__app_label="training", user_permissions__codename=codename)
        | Q(groups__permissions__content_type__app_label="training", groups__permissions__codename=codename)
    ).distinct()


class PlanStaffSelect(RecipientSelect):
    template_name = "training/widgets/plan_people.html"
    plan_id = None

    class Media:
        extend = False
        js = ()

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        url = reverse("training:plan_staff_search")
        if self.plan_id:
            url += f"?plan={self.plan_id}"
        url += ("&" if "?" in url else "?") + f"role={name}"
        context["widget"].update(search_url=url, picker_title={"schedulers": "排班人员", "approvers": "审批人员"}.get(name, "人员"))
        return context


@require_GET
def plan_staff_search(request):
    plan_id = request.GET.get("plan", "")
    if plan_id:
        if not plan_id.isdecimal():
            return JsonResponse({"error": "计划编号无效。"}, status=400)
        plan = get_object_or_404(visible_plans(request.user), pk=plan_id)
        if not plan_manager(request.user, plan):
            raise PermissionDenied
    elif not request.user.has_perm("training.add_trainingplan"):
        raise PermissionDenied
    query = request.GET.get("q", "").strip()
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 0
    if len(query) > 100 or not 1 <= page <= 10000:
        return JsonResponse({"error": "搜索条件无效，请重新输入。"}, status=400)
    users = (
        get_user_model()
        .objects.annotate(_plan_staff_name=Concat("last_name", "first_name"))
        .filter(Q(username__icontains=query) | Q(_plan_staff_name__icontains=query))
        .order_by("last_name", "first_name", "username", "pk")
    )
    if request.GET.get("role") in {"schedulers", "approvers"}:
        users = users.filter(pk__in=eligible_staff(request.GET["role"]).values("pk"))
    else:
        return JsonResponse({"error": "人员职责无效。"}, status=400)
    rows = list(users[(page - 1) * 20 : page * 20 + 1]) if query else []
    response = JsonResponse(
        {
            "results": [{"id": user.pk, "label": get_user_full_info(user)} for user in rows[:20]],
            "has_more": len(rows) > 20,
        }
    )
    response["Cache-Control"] = "private, no-store"
    return response
