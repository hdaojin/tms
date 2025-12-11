from django.db import models


class NoteRepo(models.Model):
	slug = models.SlugField(
		"目录名",
		max_length=100,
		unique=True,
		help_text="与 NOTES_ROOT 下的目录名一一对应，例如 teaching-notes-Debian",
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
