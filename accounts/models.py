from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.validators import RegexValidator

# Create your models here.

class UserProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = 'M', '男'
        FEMAILE = 'F', '女'
        SECRET = 'S', '保密'

    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, related_name='profile')
    student_id = models.CharField('学号', max_length=50, null=True, unique=True)
    name_pronunciation = models.CharField('姓名全拼', max_length=100, null=True)
    gender = models.CharField('性别', max_length=1, choices=Gender.choices, default=Gender.SECRET)
    birth_date = models.DateField('出生日期', null=True)
    phone_number = models.CharField('电话号码', max_length=20, null=True)
    emergency_contact = models.CharField('紧急联系人', max_length=100, null=True, blank=True)
    emergency_contact_phone = models.CharField('紧急联系人电话', max_length=20, null=True, blank=True)
    emergency_contact_relation = models.CharField('紧急联系人关系', max_length=50, null=True, blank=True)
    address = models.CharField('家庭住址', max_length=200, null=True, blank=True)
    id_number = models.CharField('身份证号', max_length=50, null=True, blank=True)
    original_class = models.CharField('原班级', max_length=100, null=True, blank=True)
    original_headteacher = models.CharField('原班主任', max_length=100, null=True, blank=True)
    original_headteacher_phone = models.CharField('原班主任电话', max_length=20, null=True, blank=True)
    school_dormitory = models.CharField('学校宿舍', max_length=100, null=True, blank=True)
    join_date = models.DateField('入读精英班日期', null=True, blank=True)
    leave_date = models.DateField('离开精英班日期', null=True, blank=True)
    notes = models.TextField('备注', null=True, blank=True)

    locked = models.BooleanField('信息锁定', default=False, help_text='锁定后用户无法修改个人资料。')

    class Meta:
        verbose_name = '用户信息'
        verbose_name_plural = '用户信息'    

    def __str__(self):
        return f"{self.user.username} 的信息"



# group codename 必须满足 Unix/Linux 系统组名规范

name_validator = RegexValidator(
    regex=r'^[a-zA-Z][a-zA-Z0-9_]{1,30}$',
    message='codename 必须以字母开头, 后续字符可以是字母、数字或下划线, 且长度不超过30个字符。'
)


class GroupProfile(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='profile')
    codename = models.SlugField('英文标识', 
                                max_length=30, 
                                unique=True,
                                blank=True,
                                validators=[name_validator],
                                help_text='用于脚本或系统集成的组codename, 必须以字母开头, 后续字符可以是字母、数字或下划线, 且长度不超过30个字符, 如: coach。'
                                )
    description = models.TextField('描述', null=True, blank=True)

    class Meta:
        verbose_name = '用户组信息'
        verbose_name_plural = '用户组信息'    

    def __str__(self):
        return f"{self.group.name} 的信息"