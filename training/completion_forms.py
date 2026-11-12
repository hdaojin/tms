from django import forms

from core.forms import MultipleFileField
from core.utils.forms import StyledFormMixin

from .checklists import checklist_items
from .log_references import IMAGE_SPEC, image_asset


class TaskCompletionForm(StyledFormMixin, forms.Form):
    items = forms.MultipleChoiceField(label="已完成项目", widget=forms.CheckboxSelectMultiple, required=False)

    def __init__(self, *args, execution, record, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["items"].choices = [
            (item["id"], item["title"]) for item in checklist_items(execution.training_task)
        ]
        if record:
            self.initial["items"] = [item["id"] for item in record.checklist or [] if item["done"]]


class DailyCompletionForm(StyledFormMixin, forms.Form):
    problems = forms.CharField(
        label="未完成的部分／存在问题",
        max_length=12000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="如有未完成项，请在这里统一说明。涉及多个任务时可注明任务名称。",
    )
    images = MultipleFileField(label="过程图片", upload_spec=IMAGE_SPEC, required=False)

    def clean_images(self):
        from core.documents.content import normalize_document_image
        from core.documents.types import DocumentError

        files = self.cleaned_data["images"]
        for file in files:
            try:
                normalize_document_image(image_asset(file), "过程图片")
            except DocumentError as exc:
                raise forms.ValidationError(str(exc)) from exc
            finally:
                file.seek(0)
        return files
