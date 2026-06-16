from __future__ import annotations

from django import forms

from core.uploads import UploadSpec


class MultipleFileInput(forms.ClearableFileInput):
    """支持多文件上传的文件控件。"""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """统一返回 list[UploadedFile] 的多文件字段。"""

    def __init__(
        self,
        *args,
        upload_spec: UploadSpec | None = None,
        **kwargs,
    ):
        self.upload_spec = upload_spec

        validators = list(kwargs.pop("validators", []))
        if upload_spec:
            validators.extend(upload_spec.validators())
            kwargs.setdefault("help_text", upload_spec.help_text("可上传多个文件"))
        kwargs["validators"] = validators

        widget = kwargs.pop("widget", None)
        if widget is None:
            attrs = upload_spec.widget_attrs(type="file") if upload_spec else {"type": "file"}
            widget = MultipleFileInput(attrs=attrs)
        elif upload_spec:
            widget.attrs.setdefault("accept", upload_spec.accept)
        kwargs["widget"] = widget

        super().__init__(*args, **kwargs)

    def _run_upload_spec_validation(self, files):
        if self.upload_spec:
            for file in files:
                self.upload_spec.validate_file(file)
        return files

    def clean(self, data, initial=None):
        single_file_clean = super().clean

        if isinstance(data, (list, tuple)):
            files = [file for file in data if file]
            if not files:
                if self.required:
                    single_file_clean(None, initial)
                return []
            return self._run_upload_spec_validation(
                [single_file_clean(file, initial) for file in files]
            )

        if not data:
            if self.required:
                single_file_clean(data, initial)
            return []

        return self._run_upload_spec_validation([single_file_clean(data, initial)])
