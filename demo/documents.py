from dataclasses import replace

from django import forms
from django.core.exceptions import SuspiciousFileOperation
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.http import content_disposition_header
from django.utils.text import get_valid_filename

from core.documents import (
    DocumentBusy,
    DocumentError,
    DocumentRenderError,
    generate_document_pdf,
    list_document_templates,
    render_document_html,
)
from core.documents.limits import MAX_CONTENT_BYTES, MAX_METADATA_LENGTH
from core.documents.sample import sample_document
from core.utils.breadcrumbs import breadcrumb_link
from core.utils.forms import StyledFormMixin

from .views import DemoBaseView


class DocumentDemoForm(StyledFormMixin, forms.Form):
    title = forms.CharField(label="文档标题", max_length=MAX_METADATA_LENGTH)
    subtitle = forms.CharField(label="副标题", required=False, max_length=MAX_METADATA_LENGTH)
    organization = forms.CharField(label="单位", required=False, max_length=MAX_METADATA_LENGTH)
    author = forms.CharField(label="作者", required=False, max_length=MAX_METADATA_LENGTH)
    document_date = forms.DateField(
        label="文档日期", required=False, widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
    )
    content_format = forms.ChoiceField(
        label="正文格式", choices=(("markdown", "Markdown"), ("html_fragment", "HTML 片段"))
    )
    template_id = forms.ChoiceField(
        label="文档模板", choices=tuple((item.id, item.name) for item in list_document_templates())
    )
    content = forms.CharField(
        label="正文",
        strip=False,
        max_length=MAX_CONTENT_BYTES,
        widget=forms.Textarea(attrs={"rows": 12}),
        help_text="示例图片使用 tms-asset:topology，可在 Markdown 或 HTML 正文中引用。",
    )


class DocumentDemoView(DemoBaseView):
    template_name = "demo/documents.html"
    title = "文档转换实验"
    title_icon = "icon-[tabler--file-description]"

    def get_breadcrumb_parents(self):
        return (breadcrumb_link("UI 验收中心", "demo:index"),)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if "form" not in context:
            sample = sample_document()
            context["form"] = DocumentDemoForm(
                initial={name: getattr(sample, name) for name in DocumentDemoForm.base_fields}
            )
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response

    def post(self, request, *args, **kwargs):
        form = DocumentDemoForm(request.POST)
        action = request.POST.get("action")
        if not form.is_valid():
            return self._error(form, "请检查文档表单。", status=400)
        document = replace(sample_document(), **form.cleaned_data)
        try:
            if action == "html":
                return HttpResponse(render_document_html(document))
            if action in {"preview", "download"}:
                response = HttpResponse(generate_document_pdf(document), content_type="application/pdf")
                try:
                    filename = get_valid_filename(document.title[:80]) + ".pdf"
                except SuspiciousFileOperation:
                    filename = "文档.pdf"
                response["Content-Disposition"] = content_disposition_header(action == "download", filename)
                return response
            return self._error(form, "未知的文档操作。", status=400)
        except DocumentBusy as exc:
            return self._error(form, str(exc), status=429)
        except DocumentError as exc:
            return self._error(form, str(exc), status=400)
        except DocumentRenderError as exc:
            return self._error(form, str(exc), status=503)

    def _error(self, form, message, *, status):
        if self.request.headers.get("Accept") == "application/json":
            return JsonResponse({"error": message, "fields": form.errors.get_json_data()}, status=status)
        form.add_error(None, message)
        return render(self.request, self.template_name, self.get_context_data(form=form), status=status)
