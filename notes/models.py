from django.core.exceptions import ValidationError
from django.db import models

from .paths import InvalidNotePathError, normalize_note_relative_path


class NoteRepo(models.Model):
	slug = models.SlugField(
		"访问标识",
		max_length=100,
		unique=True,
		help_text="用于 URL、权限和缓存，例如 teaching-notes-Debian；不能包含斜杠",
	)
	relative_path = models.CharField(
		"相对路径",
		max_length=500,
		unique=True,
		help_text="相对于 NOTES_ROOT 的目录路径，例如 teaching-notes-debian/debian-basics",
	)
	title = models.CharField("显示名称", max_length=200)
	description = models.TextField("简介", blank=True)
	is_visible = models.BooleanField("是否在列表中显示", default=True)
	order = models.PositiveIntegerField("排序值", default=0, help_text="列表页按此字段升序排序")
	allowed_groups = models.ManyToManyField(
		"auth.Group",
		blank=True,
		verbose_name="可见用户组",
		help_text="如果为空，表示所有登录用户可见；如果不为空，仅这些组的用户可见",
	)
	tags = models.CharField(
		"标签",
		max_length=200,
		blank=True,
		help_text="简单的标签字符串，用逗号分隔，例如 Linux,基础",
	)
	created_at = models.DateTimeField("创建时间", auto_now_add=True)
	updated_at = models.DateTimeField("最后更新时间", auto_now=True)

	class Meta:
		verbose_name = "笔记仓库"
		verbose_name_plural = "笔记仓库"
		ordering = ["order", "slug"]

	def __str__(self) -> str:  # pragma: no cover - simple display
		return self.title or self.slug

	def clean(self) -> None:
		super().clean()
		try:
			self.relative_path = normalize_note_relative_path(self.relative_path)
		except InvalidNotePathError as exc:
			raise ValidationError({"relative_path": str(exc)}) from exc

	def save(self, *args, **kwargs) -> None:
		try:
			self.relative_path = normalize_note_relative_path(self.relative_path)
		except InvalidNotePathError as exc:
			raise ValidationError({"relative_path": str(exc)}) from exc
		super().save(*args, **kwargs)
