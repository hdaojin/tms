from decimal import Decimal
from pathlib import PurePosixPath
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage

from core.constants import (
    ASSESSMENT_UPLOAD_DIR,
    ASSESSMENT_TP_ALLOWED_EXTENSIONS,
    ASSESSMENT_TP_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_MC_ALLOWED_EXTENSIONS,
    ASSESSMENT_MC_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_MT_ALLOWED_EXTENSIONS,
    ASSESSMENT_MT_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_MS_ALLOWED_EXTENSIONS,
    ASSESSMENT_MS_UPLOAD_MAX_SIZE_MB,
    ASSESSMENT_ATTACHMENT_ALLOWED_EXTENSIONS,
    ASSESSMENT_ATTACHMENT_UPLOAD_MAX_SIZE_MB,
)
from core.utils.validators import validate_file_size
from core.utils.signals import register_file_cleanup_signals

assessment_storage = FileSystemStorage(location=str(ASSESSMENT_UPLOAD_DIR))

def validate_assessment_tp_file_size(file):
    validate_file_size(file, ASSESSMENT_TP_UPLOAD_MAX_SIZE_MB)


def validate_assessment_mc_file_size(file):
    validate_file_size(file, ASSESSMENT_MC_UPLOAD_MAX_SIZE_MB)


def validate_assessment_mt_file_size(file):
    validate_file_size(file, ASSESSMENT_MT_UPLOAD_MAX_SIZE_MB)


def validate_assessment_ms_file_size(file):
    validate_file_size(file, ASSESSMENT_MS_UPLOAD_MAX_SIZE_MB)


def validate_assessment_attachment_file_size(file):
    validate_file_size(file, ASSESSMENT_ATTACHMENT_UPLOAD_MAX_SIZE_MB)


def get_assessment_upload_path(instance, filename, file_type):
    """
    生成考核文件上传路径和文件名
    路径: assessment/{start_date}/{考核名称}/{考核模块}/
    文件名: 
        - 试题/评分标准/评分表: {start_date}-{考核名称}-{考核模块}-{文件类型}.{扩展名}
        - 其他: 保持原文件名
    """
    assessment = instance.assessment
    module = instance.module
    start_date = assessment.start_date.strftime('%Y%m%d') if assessment.start_date else '00000000'
    
    # 构建目录路径
    dir_path = f"{start_date}/{assessment.name}/{module.name}"
    
    # 获取原文件扩展名
    ext = PurePosixPath(filename).suffix
    
    # 根据文件类型决定文件名
    if file_type in ['question', 'scoring_standard', 'scoring_sheet']:
        type_name_map = {
            'question': '试题',
            'scoring_standard': '评分标准',
            'scoring_sheet': '评分表',
        }
        new_filename = f"{start_date}-{assessment.name}-{module.name}-{type_name_map[file_type]}{ext}"
    else:
        # 附件、评分脚本、其他文件保持原文件名
        new_filename = filename
    
    return str(PurePosixPath(dir_path) / new_filename)

def question_upload_path(instance, filename):
    return get_assessment_upload_path(instance, filename, 'question')

def scoring_standard_upload_path(instance, filename):
    return get_assessment_upload_path(instance, filename, 'scoring_standard')

def scoring_sheet_upload_path(instance, filename):
    return get_assessment_upload_path(instance, filename, 'scoring_sheet')

def scoring_script_upload_path(instance, filename):
    return get_assessment_upload_path(instance, filename, 'scoring_script')

def other_file_upload_path(instance, filename):
    return get_assessment_upload_path(instance, filename, 'other')

def attachment_upload_path(instance, filename):
    """附件上传路径生成函数"""
    assessment_module = instance.assessment_module
    assessment = assessment_module.assessment
    module = assessment_module.module
    start_date = assessment.start_date.strftime('%Y%m%d') if assessment.start_date else '00000000'
    
    dir_path = f"{start_date}/{assessment.name}/{module.name}"
    # 附件保持原文件名
    return str(PurePosixPath(dir_path) / filename)

# 兼容旧迁移文件的函数（已废弃，保留用于迁移）
def assessment_paper_path(instance, filename):
    """旧版上传路径函数 - 仅用于迁移兼容性"""
    date_path = instance.assessment.start_date.strftime('%Y/%m') if instance.assessment.start_date else '0000/00'
    return f"papers/{date_path}/{filename}"

class Assessment(models.Model):
    name = models.CharField("考核名称", max_length=100, unique=True)
    start_date = models.DateField("开始日期", help_text="考核开始的日期")
    end_date = models.DateField("结束日期", help_text="考核结束的日期")
    description = models.TextField("描述", blank=True)
    modules = models.ManyToManyField(
        'competitions.Module',
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
        permissions = [
            ("view_all_scores", "可以查看所有人的考核成绩"),
        ]

    def __str__(self):
        return self.name

class AssessmentModule(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        verbose_name="考核"
    )
    module = models.ForeignKey(
        'competitions.Module',
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
    duration = models.DecimalField(
        "考核时长(小时)",
        max_digits=4,
        decimal_places=1,
        default=Decimal("0.0"),
        validators=[MinValueValidator(Decimal("0.0"))],
        help_text="该模块的考核时长，单位为小时"
    )
    
    # 考核资料文件字段
    question_file = models.FileField(
        "试题文件",
        storage=assessment_storage,
        upload_to=question_upload_path,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=ASSESSMENT_TP_ALLOWED_EXTENSIONS),
            validate_assessment_tp_file_size,
        ],
        help_text=f"上传试题文件，支持 {', '.join(ASSESSMENT_TP_ALLOWED_EXTENSIONS)}，大小不超过 {ASSESSMENT_TP_UPLOAD_MAX_SIZE_MB}MB"
    )
    
    scoring_standard_file = models.FileField(
        "评分标准文件",
        storage=assessment_storage,
        upload_to=scoring_standard_upload_path,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=ASSESSMENT_MC_ALLOWED_EXTENSIONS),
            validate_assessment_mc_file_size,
        ],
        help_text=f"上传评分标准文件，支持 {', '.join(ASSESSMENT_MC_ALLOWED_EXTENSIONS)}，大小不超过 {ASSESSMENT_MC_UPLOAD_MAX_SIZE_MB}MB"
    )
    
    scoring_sheet_file = models.FileField(
        "评分表文件",
        storage=assessment_storage,
        upload_to=scoring_sheet_upload_path,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=ASSESSMENT_MT_ALLOWED_EXTENSIONS),
            validate_assessment_mt_file_size,
        ],
        help_text=f"上传评分表文件，支持 {', '.join(ASSESSMENT_MT_ALLOWED_EXTENSIONS)}，大小不超过 {ASSESSMENT_MT_UPLOAD_MAX_SIZE_MB}MB"
    )
    
    scoring_script_file = models.FileField(
        "评分脚本文件",
        storage=assessment_storage,
        upload_to=scoring_script_upload_path,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=ASSESSMENT_MS_ALLOWED_EXTENSIONS),
            validate_assessment_ms_file_size,
        ],
        help_text=f"上传评分脚本文件，支持 {', '.join(ASSESSMENT_MS_ALLOWED_EXTENSIONS)}，大小不超过 {ASSESSMENT_MS_UPLOAD_MAX_SIZE_MB}MB"
    )
    
    # 移除旧的 paper_file 字段，数据迁移时需要处理

    class Meta:
        verbose_name = "考核模块"
        verbose_name_plural = "考核模块"
        unique_together = ['assessment', 'module']

    def __str__(self):
        return f"{self.assessment.name} - {self.module.name}"

class AssessmentAttachment(models.Model):
    """考核模块附件模型 - 支持上传多个附件文件"""
    assessment_module = models.ForeignKey(
        AssessmentModule,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="考核模块"
    )
    file = models.FileField(
        "附件文件",
        storage=assessment_storage,
        upload_to=attachment_upload_path,
        validators=[
            FileExtensionValidator(allowed_extensions=ASSESSMENT_ATTACHMENT_ALLOWED_EXTENSIONS),
            validate_assessment_attachment_file_size,
        ],
        help_text=f"上传附件文件，支持 {', '.join(ASSESSMENT_ATTACHMENT_ALLOWED_EXTENSIONS)}，大小不超过 {ASSESSMENT_ATTACHMENT_UPLOAD_MAX_SIZE_MB}MB"
    )
    description = models.CharField("文件说明", max_length=200, blank=True)
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)
    
    class Meta:
        verbose_name = "考核附件"
        verbose_name_plural = "考核附件"
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"{self.assessment_module} - {PurePosixPath(self.file.name).name}"

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


# 注册文件清理信号 - 删除/更新模型时自动清理旧文件
register_file_cleanup_signals(AssessmentModule, file_field="question_file")
register_file_cleanup_signals(AssessmentModule, file_field="scoring_standard_file")
register_file_cleanup_signals(AssessmentModule, file_field="scoring_sheet_file")
register_file_cleanup_signals(AssessmentModule, file_field="scoring_script_file")
register_file_cleanup_signals(AssessmentAttachment, file_field="file")

