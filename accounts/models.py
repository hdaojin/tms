from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.

class UserProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = 'M', '男'
        FEMAILE = 'F', '女'
        SECRET = 'S', '保密'

    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='profile')
    submission_training_log = models.BooleanField('是否提交训练日志', default=True)
    gender = models.CharField('性别', max_length=1, choices=Gender.choices, default=Gender.SECRET)
    birth_date = models.DateField('出生日期', null=True, blank=True)
    phone_number = models.CharField('电话号码', max_length=20, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} 的信息"
