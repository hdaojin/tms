from django.conf import settings
from django.db import models

from core.models import AuditedModel


class SambaOperation(AuditedModel):
	class Action(models.TextChoices):
		ENABLE = 'enable', '开通账户'
		CHANGE_PASSWORD = 'change_password', '修改密码'
		DISABLE = 'disable', '停用账户'

	class Status(models.TextChoices):
		QUEUED = 'queued', '待处理'
		RUNNING = 'running', '处理中'
		SUCCEEDED = 'succeeded', '已完成'
		FAILED = 'failed', '失败'

	target_user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='samba_operations',
		verbose_name='目标用户',
	)
	action = models.CharField('操作', max_length=32, choices=Action.choices)
	status = models.CharField(
		'状态',
		max_length=16,
		choices=Status.choices,
		default=Status.QUEUED,
	)
	payload_encrypted = models.TextField('加密载荷', blank=True)
	result_summary = models.CharField('结果摘要', max_length=255, blank=True)
	detail = models.TextField('详细日志', blank=True)
	last_error = models.TextField('错误信息', blank=True)
	started_at = models.DateTimeField('开始时间', null=True, blank=True)
	finished_at = models.DateTimeField('结束时间', null=True, blank=True)

	class Meta:
		ordering = ['-created_at', '-id']
		verbose_name = 'Samba 操作'
		verbose_name_plural = 'Samba 操作'

	def __str__(self):
		return f'{self.target_user.username} - {self.get_action_display()} - {self.get_status_display()}'
