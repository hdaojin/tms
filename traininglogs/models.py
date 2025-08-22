from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone

from skills.models import Module


# Create your models here.
# 训练日志上传存储模型
class TrainingLog(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='training_logs', verbose_name='训练模块')
    task = models.CharField("训练任务", max_length=20)
    training_date = models.DateField("训练日期", default=timezone.now,
                                     help_text="*特别注意：请填写日志对应的实际训练日期，而非上传日期")
    upload = models.FileField("日志文件", upload_to=f"{settings.LOGS_DIR}/%Y/%m", help_text="支持doc、docx、pdf格式, 文件大小不超过10MB")
    filename = models.CharField("文件名", max_length=200)
    uploaded_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, related_name='training_logs', verbose_name='上传者', null=True, blank=True)
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)


    class Meta:
        verbose_name = '训练日志'
        verbose_name_plural = '训练日志'
        ordering = ('-training_date',)

    def __str__(self):
        return f"{self.module} - {self.task} - {self.training_date}"



# 删除信号处理器
@receiver(pre_delete, sender=TrainingLog)
def delete_traininglog_file(sender, instance, **kwargs):
    """
    删除训练日志时，同时删除对应的文件
    """
    if instance.upload:
        try:
            # 删除物理文件
            if instance.upload.storage.exists(instance.upload.name):
                instance.upload.storage.delete(instance.upload.name)
        except Exception:
            # 如果文件删除失败，记录错误但不阻止删除
            pass