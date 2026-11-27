from django import forms

from core.utils.forms import StyledFormMixin

from .models import NoteRepo


class NoteRepoForm(StyledFormMixin, forms.ModelForm):
    confirmation = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = NoteRepo
        fields = (
            "title",
            "slug",
            "relative_path",
            "description",
            "tags",
            "order",
            "is_visible",
            "allowed_groups",
            "allow_anonymous_access",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "allowed_groups": forms.CheckboxSelectMultiple(attrs={"class": "checkbox checkbox-primary"}),
        }
        help_texts = {
            "slug": "用于笔记链接。修改现有仓库的访问标识会使旧链接失效。",
            "allowed_groups": "用于私有访问。留空时，拥有查看笔记权限的用户均可访问。",
        }
