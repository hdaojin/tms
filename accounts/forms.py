from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .utils import validate_invitation_code  


class CustomUserCreationForm(UserCreationForm):
    full_name = forms.CharField(
        max_length=100, 
        required=True, 
        label="姓名",
        help_text="必填; 必须是中文真实姓名。"
        )
    invitation_code = forms.CharField(
        max_length=255, required=True, label="邀请码",
        help_text="请输入邀请码"
    )

    def clean_invitation_code(self):
        code_str = self.cleaned_data.get('invitation_code')
        if not validate_invitation_code(code_str):
            raise forms.ValidationError("邀请码无效或已过期")
        return code_str
    
    class Meta:
        model = User
        fields = ("username", "full_name", "invitation_code", "password1", "password2")
