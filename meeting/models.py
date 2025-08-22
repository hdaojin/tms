from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import pre_delete
from django.dispatch import receiver

# Create your models here.

class Meeting(models.Model):
    title = models.CharField(max_length=200, verbose_name="会议名称")
    date = models.DateField(verbose_name="会议日期", default=timezone.now, help_text="*特别注意：请填写会议的实际日期, 而非上传日期")
    upload = models.FileField("会议记录文件", upload_to=f"{settings.MEETING_FILE_DIR}/%Y", help_text="支持pdf格式, 文件大小不超过10MB")
    filename = models.CharField("文件名", max_length=200)
    uploaded_by = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, related_name='meetings', verbose_name='上传者', null=True, blank=True)
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)

    class Meta:
        verbose_name = '会议记录'
        verbose_name_plural = '会议记录'
        ordering = ('-date',)
    
    def __str__(self):
        return f"{self.title} - {self.date}"


# 删除信号处理器
@receiver(pre_delete, sender=Meeting)
def delete_meeting_file(sender, instance, **kwargs):
    """
    删除会议记录时，同时删除对应的文件
    """
    if instance.upload:
        try:
            # 删除物理文件
            if instance.upload.storage.exists(instance.upload.name):
                instance.upload.storage.delete(instance.upload.name)
        except Exception:
            # 如果文件删除失败，记录错误但不阻止删除
            pass
