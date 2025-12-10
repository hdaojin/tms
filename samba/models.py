# from django.db import models
# from django.contrib.auth.models import Group
# from django.core.validators import RegexValidator


# unix_name_validator = RegexValidator(
#     regex=r'^[a-z][a-z0-9_-]{1,30}$',
#     message='uninx_name 必须以小写字母开头，后续字符可以是小写字母、数字、下划线或连字符，且长度不超过30个字符。'
# )

# class SambaGroupMap(models.Model):
#     """
#     Django 用户组与 Samba 组(Unix 系统组)映射关系。
#     """
#     group = models.OneToOneField(
#         Group,
#         on_delete=models.CASCADE,
#         related_name='samba_group_map',
#         primary_key=True,
#         help_text='关联的 Django 用户组'
#     )
#     unix_name = models.CharField(
#         verbose_name='Unix 组名',
#         max_length=30,
#         unique=True,
#         null=True,
#         blank=True,
#         validators=[unix_name_validator],
#         help_text='对应的 Samba 组名（Unix 系统组名）, 必须是Uninx/Linux系统可用的 ASCII 组名（如 smbusers、netops、dev_team）。'
#     )
#     updated_at = models.DateTimeField(auto_now=True)


#     class Meta:
#         verbose_name = '账号所属组与Samba组的映射'
#         verbose_name_plural = '账号所属组与Samba组的映射'

#     def __str__(self):
#         return f"{self.group.name} -> {self.unix_name}"
