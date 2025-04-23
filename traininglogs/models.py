from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from datetime import date

from skills.models import Module


# Create your models here.
# 训练日志上传存储模型
class TrainingLog(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='training_logs', verbose_name='模块')
    task = models.CharField("训练任务", max_length=100)
    training_date = models.DateField("训练日期", default=date.today,
                                     help_text="*特别注意：请填写日志对应的实际训练日期，而非上传日期")
    upload = models.FileField("上传训练日志", upload_to=f"{settings.LOGS_DIR}/%Y/%m", help_text="支持doc、docx、pdf格式, 文件大小不超过10MB")
    filename = models.CharField("文件名", max_length=200)
    uploaded_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='training_logs', verbose_name='上传者')
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)


    class Meta:
        verbose_name = '训练日志'
        verbose_name_plural = '训练日志'
        ordering = ('-training_date',)

    def __str__(self):
        return f"{self.module} - {self.task} - {self.training_date}"