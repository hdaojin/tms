from __future__ import annotations

from django import forms

from core.utils.forms import DefaultTodayDateFormMixin, StyledFormMixin

from .models import ARCHIVE_ASSET_UPLOAD_SPEC, ArchiveAsset


class ArchiveAssetForm(DefaultTodayDateFormMixin, StyledFormMixin, forms.ModelForm):
    default_today_date_fields = ("business_date",)

    class Meta:
        model = ArchiveAsset
        fields = ["skill_project", "asset_type", "title", "description", "file", "business_date", "source_system", "source_external_id"]
        widgets = {
            "business_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "file": forms.ClearableFileInput(attrs=ARCHIVE_ASSET_UPLOAD_SPEC.widget_attrs(type="file")),
        }
