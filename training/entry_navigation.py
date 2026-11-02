"""编辑器沿用列表筛选，并从未分页的匹配结果查找下一日期。"""
from types import SimpleNamespace
from django.http import QueryDict
from django.urls import reverse

FILTER_KEYS = ("q", "date", "date_from", "date_to", "weekday", "period", "domain", "coach", "state", "mine", "tab")


def filters_for(request):
    source = request.POST if getattr(request, "method", "GET") == "POST" else request.GET
    params = QueryDict(source.get("entry_filters", "")) if "entry_filters" in source else request.GET
    result = QueryDict(mutable=True)
    for key in FILTER_KEYS:
        if key in params:
            result.setlist(key, params.getlist(key))
    return result


def editor_suffix(params):
    if not params:
        return ""
    query = QueryDict(mutable=True)
    query["entry_filters"] = params.urlencode()
    return "&" + query.urlencode()


def next_entry(request, plan, day, *, period=None, task=False):
    from .schedule_entries import entry_context
    params = filters_for(request)
    view = SimpleNamespace(request=SimpleNamespace(user=request.user, GET=params), object=plan)
    for candidate in entry_context(view, None, matching_only=True):
        if candidate.date <= day.date:
            continue
        if period is None:
            from .scheduling import can_schedule
            if not plan.published_at or not can_schedule(request.user, plan):
                return None
            query = f"days={candidate.pk}&day_only=1"
            url = reverse("training:schedule_edit", args=[plan.pk])
        else:
            slot = next((slot for slot in candidate.matching_slots if slot.period == period and slot.is_configured and (slot.can_fill if task else slot.can_schedule)), None)
            if slot is None:
                continue
            if task:
                url = reverse("training:slot_task_create", args=[slot.pk])
                query = ""
            else:
                url = reverse("training:schedule_edit", args=[plan.pk])
                query = f"days={candidate.pk}&slot={slot.pk}"
        suffix = editor_suffix(params)
        return {"day": candidate, "query": query + suffix, "url": url + ("?" + (query + suffix).lstrip("&") if query or suffix else "")}
    return None
