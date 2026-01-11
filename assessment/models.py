from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage

from competitions.models import Module

assessment_storage = FileSystemStorage(location=str(settings.ASSESSMENT_UPLOAD_DIR))

def validate_file_size(value):
    filesize = value.size
    if filesize > settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"文件大小不能超过 {settings.UPLOAD_MAX_SIZE_MB}MB")

def assessment_paper_path(instance, filename):
    date_path = instance.start_date.strftime('%Y/%m') if instance.start_date else '0000/00'
    return f"papers/{date_path}/{filename}"

class Assessment(models.Model):
    name = models.CharField("考核名称", max_length=100, unique=True)
    start_date = models.DateField("开始日期", help_text="考核开始的日期")
    end_date = models.DateField("结束日期", help_text="考核结束的日期")
    description = models.TextField("描述", blank=True)
    paper_file = models.FileField(
        "试卷及评分文件",
        storage=assessment_storage,
        upload_to=assessment_paper_path,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=settings.ASSESSMENT_ALLOWED_EXTENSIONS),
            validate_file_size
        ],
        help_text=f"请上传文件，支持 {', '.join(settings.ASSESSMENT_ALLOWED_EXTENSIONS)}，大小不超过 {settings.UPLOAD_MAX_SIZE_MB}MB"
    )
    modules = models.ManyToManyField(
        Module,
        through='AssessmentModule',
        verbose_name="考核模块",
        related_name="assessments",
        blank=True,
        help_text="本次考核包含的模块"
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="参考人员",
        related_name="assessments",
        blank=True,
        help_text="参加本次考核的人员"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "考核"
        verbose_name_plural = "考核"
        ordering = ["-start_date", "name"]

    def __str__(self):
        return self.name

class AssessmentModule(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        verbose_name="考核"
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        verbose_name="模块"
    )
    max_score = models.DecimalField(
        "模块总分",
        max_digits=5,
        decimal_places=2,
        default=Decimal("25.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="该模块在本次考核中的满分值"
    )

    class Meta:
        verbose_name = "成绩录入"
        verbose_name_plural = "成绩录入"
        unique_together = ['assessment', 'module']

    def __str__(self):
        return f"{self.assessment.name} - {self.module.name}"

class Score(models.Model):
    assessment_module = models.ForeignKey(
        AssessmentModule,
        verbose_name="考核模块",
        on_delete=models.CASCADE,
        related_name="scores"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="选手",
        on_delete=models.CASCADE,
        related_name="assessment_scores"
    )
    score = models.DecimalField(
        "得分",
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))]
    )
    remarks = models.TextField("备注", blank=True)
    
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "成绩"
        verbose_name_plural = "成绩"
        unique_together = ["assessment_module", "user"]
        ordering = ["assessment_module", "user"]

    def clean(self):
        # 验证分数不超过满分
        # 注意：使用 self.assessment_module 可能会触发数据库查询，如果外键未设置会抛出异常
        # 应该先检查是否有 assessment_module_id
        if hasattr(self, 'assessment_module') and self.assessment_module:
             if self.score > self.assessment_module.max_score:
                raise ValidationError({'score': f"分数不能超过该模块的满分 ({self.assessment_module.max_score})"})
        
        # 验证用户是否在参考人员列表中
        if hasattr(self, 'assessment_module') and self.assessment_module and self.user_id: # type: ignore
            if not self.assessment_module.assessment.participants.filter(pk=self.user.pk).exists():
                user_name = self.user.first_name if self.user.first_name else self.user.username
                raise ValidationError({'user': f"用户 {user_name} 不是本次考核的参考人员"})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        user_name = self.user.first_name if self.user.first_name else self.user.username
        return f"{self.assessment_module} - {user_name}: {self.score}"

