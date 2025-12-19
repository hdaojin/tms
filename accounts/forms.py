from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from core.utils.invitation import validate_invitation_code  
from core.utils.forms import StyledFormMixin
from .models import UserProfile


class CustomAuthenticationForm(AuthenticationForm):
    """自定义登录表单，用于首页登录"""
    username = forms.CharField(
        max_length=254,
        label="用户名",
        widget=forms.TextInput(attrs={
            'placeholder': '输入用户名',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        label="密码",
        strip=False,
        widget=forms.PasswordInput(attrs={
            'placeholder': '输入密码',
            'autocomplete': 'current-password',
        })
    )

    # error_messages = {
    #     'invalid_login': '用户名或密码错误，请重试。',
    #     'inactive': '此账户已被禁用。',
    # }


class CustomUserCreationForm(StyledFormMixin, UserCreationForm):
    """
    自定义用户注册表单，添加姓名和邀请码字段。
    """
    full_name = forms.CharField(
        max_length=100, 
        required=True, 
        label="姓名",
        help_text="必填; 必须是中文真实姓名。",
        widget=forms.TextInput(attrs={
            'placeholder': '请填写真实姓名',
        })
    )
    invitation_code = forms.CharField(
        max_length=255, 
        required=True, 
        label="邀请码",
        help_text="请填写管理员提供的邀请码。",
        widget=forms.TextInput(attrs={
            'placeholder': '输入邀请码',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 为默认字段添加 DaisyUI 样式
        self.fields['username'].widget.attrs.update({
            'placeholder': '用户名',
        })
        self.fields['password1'].widget.attrs.update({
            'placeholder': '密码',
        })
        self.fields['password2'].widget.attrs.update({
            'placeholder': '请再次填写密码',
        })

    def clean_invitation_code(self):
        code_str = self.cleaned_data.get('invitation_code')
        if not validate_invitation_code(code_str):
            raise forms.ValidationError("邀请码无效或已过期")
        return code_str
    
    class Meta:
        model = User
        fields = ("username", "full_name", "invitation_code", "password1", "password2")


class ProfileForm(forms.ModelForm):
    """用户资料表单，用于编辑用户的个人信息。"""
    class Meta:
        model = UserProfile
        # 不包含 user，一般在视图里用 request.user.profile 绑定
        fields = [
            "student_id",
            "name_pronunciation",
            "gender",
            "birth_date",
            "phone_number",
            "id_number",
            "emergency_contact",
            "emergency_contact_phone",
            "emergency_contact_relation",
            "address",
            "original_class",
            "original_headteacher",
            "original_headteacher_phone",
            "school_dormitory",
            "join_date",
            "leave_date",
            "notes",
        ]
        widgets = {
            "student_id": forms.TextInput(attrs={"placeholder": "学号"}),
            "name_pronunciation": forms.TextInput(attrs={"placeholder": "姓名全拼"}),
            "gender": forms.Select(attrs={"class":"select select-sm select-ghost"}),
            "birth_date": forms.DateInput(attrs={"type": "text", "placeholder": "YYYY/MM/DD"}),
            "phone_number": forms.TextInput(attrs={"placeholder": "电话号码"}),
            "id_number": forms.TextInput(attrs={"placeholder": "你的身份证号码"}),
            "emergency_contact": forms.TextInput(attrs={"placeholder": "紧急联系人姓名"}),
            "emergency_contact_phone": forms.TextInput(attrs={"placeholder": "紧急联系人电话"}),
            "emergency_contact_relation": forms.TextInput(attrs={"placeholder": "与紧急联系人的关系"}),
            "address": forms.TextInput(attrs={"placeholder": "详细家庭住址，具体到门牌号"}),
            "original_class": forms.TextInput(attrs={"placeholder": "原班级名称"}),
            "original_headteacher": forms.TextInput(attrs={"placeholder": "原班主任姓名"}),
            "original_headteacher_phone": forms.TextInput(attrs={"placeholder": "原班主任联系电话"}),
            "school_dormitory": forms.TextInput(attrs={"placeholder": "学校宿舍房间号，如走读则填写“走读”"}),
            "join_date": forms.DateInput(attrs={"type": "text", "placeholder": "YYYY/MM/DD"}),
            "leave_date": forms.DateInput(attrs={"type": "text", "placeholder": "YYYY/MM/DD"}),
            "notes": forms.Textarea(attrs={"rows": 4, "placeholder": "其他信息","class":"textarea w-full"}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        # 锁定后，前台一律禁用填写（不区分管理员）。
        if self.instance and self.instance.pk and self.instance.locked:
            for field in self.fields.values():
                field.disabled = True


    def clean_birth_date(self):
        bd = self.cleaned_data.get("birth_date")
        if bd is not None:
            from django.utils import timezone
            if bd > timezone.localdate():
                raise forms.ValidationError("出生日期不能晚于今天。")
        return bd

    def clean(self):
        cleaned = super().clean()
        join_date = cleaned.get("join_date")
        leave_date = cleaned.get("leave_date")
        if join_date and leave_date and leave_date < join_date:
            self.add_error("leave_date", "离开日期不能早于入读日期。")

        # 锁定后，前台不可修改（无论是否管理员）。管理员如需变更，请在后台解锁。
        if self.instance and self.instance.pk and self.instance.locked:
            raise forms.ValidationError("该用户资料已被锁定，无法修改。如需更改，请联系管理员在后台解除锁定后再尝试。")
        
        return cleaned



