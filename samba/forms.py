from django import forms
from django.contrib.auth.password_validation import validate_password

from common.forms import StyledFormMixin


class SambaPasswordForm(StyledFormMixin, forms.Form):
    password1 = forms.CharField(
        label="密码",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
        help_text="设置Samba密码, 需满足本站密码策略: 至少8位, 不能全部是数字。"
    )

    password2 = forms.CharField(
        label="确认密码",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user  # 便于基于用户上下文做密码策略校验（常见做法）

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("两次输入的密码不一致。")
        if p1:
            # 复用 Django 的密码验证器策略
            validate_password(p1, self.user)
        return cleaned

    @property
    def password(self):
        return self.cleaned_data["password1"]