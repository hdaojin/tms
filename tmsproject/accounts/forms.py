from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class CustomUserCreationForm(UserCreationForm):
    full_name = forms.CharField(
        max_length=100, 
        required=True, 
        label="姓名",
        help_text="必填; 必须是中文真实姓名。"
        )
    
    class Meta:
        model = User
        fields = ("username", "full_name", "password1", "password2")


