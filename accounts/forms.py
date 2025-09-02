from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from common.utils.invitation import validate_invitation_code  
from common.forms import StyledFormMixin


class CustomAuthenticationForm(AuthenticationForm):
    """自定义登录表单，用于首页登录"""
    username = forms.CharField(
        max_length=254,
        label="用户名",
        widget=forms.TextInput(attrs={
            'placeholder': '请输入用户名',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        label="密码",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'placeholder': '请输入密码',
            'autocomplete': 'current-password',
        })
    )

    # error_messages = {
    #     'invalid_login': '用户名或密码错误，请重试。',
    #     'inactive': '此账户已被禁用。',
    # }


class CustomUserCreationForm(StyledFormMixin, UserCreationForm):
    full_name = forms.CharField(
        max_length=100, 
        required=True, 
        label="姓名",
        help_text="必填; 必须是中文真实姓名。",
        widget=forms.TextInput(attrs={
            'placeholder': '请输入真实姓名',
        })
    )
    invitation_code = forms.CharField(
        max_length=255, 
        required=True, 
        label="邀请码",
        help_text="请输入邀请码",
        widget=forms.TextInput(attrs={
            'placeholder': '请输入邀请码。',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 为默认字段添加 DaisyUI 样式
        self.fields['username'].widget.attrs.update({
            'placeholder': '请输入用户名',
        })
        self.fields['password1'].widget.attrs.update({
            'placeholder': '请输入密码',
        })
        self.fields['password2'].widget.attrs.update({
            'placeholder': '请再次输入密码',
        })

    def clean_invitation_code(self):
        code_str = self.cleaned_data.get('invitation_code')
        if not validate_invitation_code(code_str):
            raise forms.ValidationError("邀请码无效或已过期")
        return code_str
    
    class Meta:
        model = User
        fields = ("username", "full_name", "invitation_code", "password1", "password2")
