from django import forms

from .models import MenuItem
from .utils import get_named_url_choices


class MenuItemForm(forms.ModelForm):
    named_url = forms.ChoiceField(
        label="命名路由",
        required=False,
        choices=[],  # 运行时在 __init__ 中填充
        help_text="从已发现的命名URL中选择（自动排除admin）"
    )

    class Meta:
        model = MenuItem
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['named_url'].choices = [('', '--- 空 ---')] + get_named_url_choices()
