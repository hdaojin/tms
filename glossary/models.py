from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.uploads import PrivateMediaStorage
from core.utils.signals import register_file_cleanup_signals

from .normalization import english_comparison_key, normalize_display_text, unique_normalized


def glossary_import_upload_path(instance, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    now = timezone.localdate()
    return f"imports/{now:%Y/%m/%d}/{uuid4().hex}{suffix}"


class ProfessionalGlossary(models.Model):
    skill_project = models.ForeignKey(
        "standards.SkillProject",
        verbose_name="技能项目",
        on_delete=models.PROTECT,
        related_name="professional_glossaries",
    )
    name = models.CharField("词库名称", max_length=150)
    description = models.TextField("说明", blank=True)
    is_active = models.BooleanField("启用", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_professional_glossaries",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "专业词库"
        verbose_name_plural = "专业词库"
        ordering = ["skill_project", "name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["skill_project", "name"], name="uniq_glossary_project_name"),
        ]

    def save(self, *args, **kwargs):
        self.name = normalize_display_text(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.skill_project.code} / {self.name}"


class GlossaryEntry(models.Model):
    class Source(models.TextChoices):
        IMPORT = "import", "文件导入"
        PROPOSAL = "proposal", "词条提案"
        MANAGER = "manager", "管理者录入"

    glossary = models.ForeignKey(
        ProfessionalGlossary,
        verbose_name="专业词库",
        on_delete=models.PROTECT,
        related_name="entries",
    )
    english_term = models.CharField("英文", max_length=255)
    english_key = models.CharField("英文比较键", max_length=255, editable=False)
    acronym = models.CharField("Acronym", max_length=100, blank=True)
    chinese_translation = models.TextField("中文释义")
    english_aliases = models.JSONField("英文答案别名", default=list, blank=True)
    chinese_aliases = models.JSONField("中文答案别名", default=list, blank=True)
    source = models.CharField("来源", max_length=20, choices=Source.choices, default=Source.MANAGER)
    is_active = models.BooleanField("启用", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_glossary_entries",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="更新人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_glossary_entries",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "词条"
        verbose_name_plural = "词条"
        ordering = ["glossary", "english_key", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["glossary", "english_key"], name="uniq_glossary_english_key"),
        ]

    def clean(self):
        super().clean()
        if not english_comparison_key(self.english_term):
            raise ValidationError({"english_term": "英文不能为空。"})
        if not normalize_display_text(self.chinese_translation):
            raise ValidationError({"chinese_translation": "中文释义不能为空。"})

    def save(self, *args, **kwargs):
        self.english_term = normalize_display_text(self.english_term)
        self.english_key = english_comparison_key(self.english_term)
        self.acronym = normalize_display_text(self.acronym)
        self.chinese_translation = normalize_display_text(self.chinese_translation)
        self.english_aliases = unique_normalized(self.english_aliases or [], english=True)
        self.chinese_aliases = unique_normalized(self.chinese_aliases or [], english=False)
        self.clean()
        super().save(*args, **kwargs)
        ProfessionalGlossary.objects.filter(pk=self.glossary_id).update(updated_at=timezone.now())

    def __str__(self):
        return self.english_term


class GlossaryEntryProposal(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待审核"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"

    glossary = models.ForeignKey(
        ProfessionalGlossary,
        verbose_name="专业词库",
        on_delete=models.PROTECT,
        related_name="entry_proposals",
    )
    english_term = models.CharField("英文", max_length=255)
    english_key = models.CharField("英文比较键", max_length=255, editable=False)
    acronym = models.CharField("Acronym", max_length=100, blank=True)
    chinese_translation = models.TextField("中文释义")
    english_aliases = models.JSONField("英文答案别名", default=list, blank=True)
    chinese_aliases = models.JSONField("中文答案别名", default=list, blank=True)
    status = models.CharField("审核状态", max_length=20, choices=Status.choices, default=Status.PENDING)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="提交人",
        on_delete=models.PROTECT,
        related_name="glossary_entry_proposals",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="审核人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_glossary_entry_proposals",
    )
    reviewed_at = models.DateTimeField("审核时间", null=True, blank=True)
    review_note = models.TextField("审核意见", blank=True)
    resulting_entry = models.OneToOneField(
        GlossaryEntry,
        verbose_name="生成词条",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_proposal",
    )
    created_at = models.DateTimeField("提交时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "词条提案"
        verbose_name_plural = "词条提案"
        ordering = ["-created_at", "-pk"]

    def save(self, *args, **kwargs):
        self.english_term = normalize_display_text(self.english_term)
        self.english_key = english_comparison_key(self.english_term)
        self.acronym = normalize_display_text(self.acronym)
        self.chinese_translation = normalize_display_text(self.chinese_translation)
        self.english_aliases = unique_normalized(self.english_aliases or [], english=True)
        self.chinese_aliases = unique_normalized(self.chinese_aliases or [], english=False)
        if not self.english_key:
            raise ValidationError({"english_term": "英文不能为空。"})
        if not self.chinese_translation:
            raise ValidationError({"chinese_translation": "中文释义不能为空。"})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.english_term} / {self.get_status_display()}"


class GlossaryImport(models.Model):
    class Status(models.TextChoices):
        PREVIEW = "preview", "待确认"
        INVALID = "invalid", "校验未通过"
        CONFIRMED = "confirmed", "已确认"
        STALE = "stale", "已过期"

    glossary = models.ForeignKey(
        ProfessionalGlossary,
        verbose_name="专业词库",
        on_delete=models.PROTECT,
        related_name="imports",
    )
    source_file = models.FileField(
        "源 XLSX",
        storage=PrivateMediaStorage("glossary"),
        upload_to=glossary_import_upload_path,
    )
    original_filename = models.CharField("原始文件名", max_length=255)
    sha256 = models.CharField("SHA256", max_length=64)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.PREVIEW)
    parsed_payload = models.JSONField("解析快照", default=dict)
    decision_payload = models.JSONField("确认决策", default=dict, blank=True)
    result_summary = models.JSONField("导入结果", default=dict, blank=True)
    glossary_version = models.DateTimeField("词库预览版本")
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="导入人",
        on_delete=models.PROTECT,
        related_name="glossary_imports",
    )
    created_at = models.DateTimeField("上传时间", auto_now_add=True)
    confirmed_at = models.DateTimeField("确认时间", null=True, blank=True)

    class Meta:
        verbose_name = "词库导入记录"
        verbose_name_plural = "词库导入记录"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.glossary} / {self.original_filename}"


class StudySession(models.Model):
    class Mode(models.TextChoices):
        EN_TO_ZH = "en_to_zh", "英文答中文"
        ZH_TO_EN = "zh_to_en", "中文答英文"
        MIXED = "mixed", "均衡随机"

    class Status(models.TextChoices):
        ACTIVE = "active", "进行中"
        COMPLETED = "completed", "已完成"
        STOPPED = "stopped", "已停止"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="学习者",
        on_delete=models.PROTECT,
        related_name="glossary_study_sessions",
    )
    glossary = models.ForeignKey(
        ProfessionalGlossary,
        verbose_name="专业词库",
        on_delete=models.PROTECT,
        related_name="study_sessions",
    )
    mode = models.CharField("学习模式", max_length=20, choices=Mode.choices)
    target_count = models.PositiveSmallIntegerField("目标题量", null=True, blank=True)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField("开始时间", auto_now_add=True)
    ended_at = models.DateTimeField("结束时间", null=True, blank=True)

    class Meta:
        verbose_name = "学习会话"
        verbose_name_plural = "学习会话"
        ordering = ["-started_at", "-pk"]
        permissions = [("view_all_study_statistics", "能查看全部专业词汇学习统计")]

    @property
    def answered_count(self):
        return self.attempts.filter(answered_at__isnull=False).count()

    def __str__(self):
        return f"{self.user} / {self.glossary} / {self.started_at:%Y-%m-%d %H:%M}"


class StudyAttempt(models.Model):
    class Direction(models.TextChoices):
        EN_TO_ZH = "en_to_zh", "英文答中文"
        ZH_TO_EN = "zh_to_en", "中文答英文"

    session = models.ForeignKey(
        StudySession,
        verbose_name="学习会话",
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    entry = models.ForeignKey(
        GlossaryEntry,
        verbose_name="词条",
        on_delete=models.PROTECT,
        related_name="study_attempts",
    )
    sequence = models.PositiveIntegerField("题号")
    direction = models.CharField("题目方向", max_length=20, choices=Direction.choices)
    prompt_snapshot = models.TextField("题面快照")
    expected_answers_snapshot = models.JSONField("标准答案快照", default=list)
    submitted_answer = models.TextField("提交答案", blank=True)
    normalized_submitted_answer = models.TextField("规范化答案", blank=True)
    is_correct = models.BooleanField("正确", null=True, blank=True)
    presented_at = models.DateTimeField("出题时间", auto_now_add=True)
    answered_at = models.DateTimeField("作答时间", null=True, blank=True)

    class Meta:
        verbose_name = "作答记录"
        verbose_name_plural = "作答记录"
        ordering = ["session", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["session", "sequence"], name="uniq_study_attempt_sequence"),
        ]

    def __str__(self):
        return f"{self.session_id} / {self.sequence}"


register_file_cleanup_signals(GlossaryImport, file_field="source_file")
