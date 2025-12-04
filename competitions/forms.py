from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import ExamScore


class ExamScoreForm(forms.ModelForm):
    class Meta:
        model = ExamScore
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        competitor_group = Group.objects.get(name='选手')

        self.fields['user'].queryset =(get_user_model().objects.filter(groups=competitor_group))