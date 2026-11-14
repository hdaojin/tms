from datetime import date
from urllib.parse import urlencode, urlsplit, urlunsplit

from django.urls import reverse

from core.utils.breadcrumbs import Breadcrumb


def return_params(params):
    try:
        day = date.fromisoformat(params.get("return_date", ""))
    except ValueError:
        return {}
    query = {"date": day.isoformat()}
    if params.get("return_scope") == "all":
        query["scope"] = "all"
    if params.get("return_plan", "").isascii() and params.get("return_plan", "").isdigit():
        query["plan"] = params["return_plan"]
    return query


def training_return(request):
    query = return_params(request.GET)
    if query and request.user.has_perm("training.view_trainingtask"):
        return Breadcrumb("我的训练", f"{reverse('training:my_training')}?{urlencode(query)}")
    return None


def with_training_return(url, query):
    if not query:
        return url
    suffix = urlencode({f"return_{key}": value for key, value in query.items()})
    parts = urlsplit(url)
    return urlunsplit(parts._replace(query=f"{parts.query}&{suffix}" if parts.query else suffix))
