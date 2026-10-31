from django import forms
from django.urls import reverse


class RecipientSelect(forms.Widget):
    """只渲染已选人员；候选通过有权限检查的搜索接口分批读取。"""

    template_name = "meetings/widgets/recipients.html"
    allow_multiple_selected = True

    class Media:
        js = ("meetings/recipients.js",)

    def value_from_datadict(self, data, files, name):
        return data.getlist(name) if hasattr(data, "getlist") else data.get(name, [])

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        attributes = context["widget"]["attrs"]
        context["widget"].update(
            selected=getattr(self, "selected", []),
            search_url=reverse("meetings:recipient_search"),
            meeting_id=getattr(self, "meeting_id", ""),
            aria_invalid=attributes.get("aria-invalid", "false"),
            aria_describedby=" ".join(
                filter(None, [attributes.get("aria-describedby", ""), attributes.get("id", "") + "_status"])
            ),
        )
        return context
