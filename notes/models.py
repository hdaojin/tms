from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, router

from .paths import InvalidNotePathError, normalize_note_relative_path, resolve_note_repo_root


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
	allow_anonymous_access = models.BooleanField(
		"允许匿名访问",
		default=False,
		help_text=(
			"开启后，任何人都可以通过直接链接访问该笔记仓库及其 Markdown、"
			"图片和附件。仅对“在笔记列表中显示”的仓库生效。"
		),
	)
	order = models.PositiveIntegerField("排序值", default=0, help_text="列表页按此字段升序排序")
	allowed_groups = models.ManyToManyField(
		"auth.Group",
		blank=True,
		verbose_name="可见用户组",
		help_text="访问仍需“查看笔记”权限；为空时不额外限制仓库受众，否则仅指定组可见",
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
		self._validate_path_and_anonymous_access(router.db_for_write(type(self), instance=self))

	def _other_repo_paths(self, using=None):
		paths = (
			type(self)._base_manager.using(using).exclude(pk=self.pk).order_by().values_list("relative_path", flat=True)
		)
		for path in paths:
			try:
				yield PurePosixPath(normalize_note_relative_path(path))
			except InvalidNotePathError:
				continue

	def anonymous_access_block_reason(self, *, using=None, relative_path=None) -> str:
		"""检查登记路径及实际目录，防止公开入口绕过其它仓库的边界。"""
		try:
			path = PurePosixPath(
				normalize_note_relative_path(relative_path if relative_path is not None else self.relative_path)
			)
			root = resolve_note_repo_root(path.as_posix(), require_exists=False)
			if root == Path(settings.NOTES_ROOT).resolve():
				return "公开目录不能指向笔记根目录，请调整目录结构。"
			for other in self._other_repo_paths(using or self._state.db):
				if path == other or path in other.parents:
					return "目录包含其他已登记仓库或与其重叠，请先调整目录结构。"
				try:
					other_root = resolve_note_repo_root(other.as_posix(), require_exists=False)
				except InvalidNotePathError:
					continue
				# Windows 路径别名只差大小写时，已登记的子仓库仍可独立公开。
				if other_root.is_relative_to(root) or (
					root.is_relative_to(other_root) and Path(other) not in Path(path).parents
				):
					return "目录包含其他已登记仓库或与其重叠，请先调整目录结构。"
		except (InvalidNotePathError, OSError, RuntimeError):
			return "无法确认公开目录的访问边界，请检查目录结构。"
		return ""

	def _validate_path_and_anonymous_access(self, using, update_fields=None) -> None:
		write_path = update_fields is None or "relative_path" in update_fields
		write_access = update_fields is None or "allow_anonymous_access" in update_fields
		if not (write_path or write_access):
			return
		try:
			if write_path:
				self.relative_path = normalize_note_relative_path(self.relative_path)
		except InvalidNotePathError as exc:
			raise ValidationError({"relative_path": str(exc)}) from exc
		previous = None
		if not self._state.adding:
			previous = (
				type(self)
				._base_manager.using(using)
				.filter(pk=self.pk)
				.values_list(
					"relative_path",
					"allow_anonymous_access",
				)
				.first()
			)
		path = PurePosixPath(self.relative_path if write_path or previous is None else previous[0])
		path_changed = write_path and (previous is None or self.relative_path != previous[0])
		if path_changed:
			native_path = Path(path)
			for other in self._other_repo_paths(using):
				other_path = Path(other)
				if native_path in other_path.parents or other_path in native_path.parents:
					raise ValidationError({"relative_path": "不能与其他已登记仓库形成父子目录关系。"})
		was_public = previous is not None and previous[1]
		is_public = self.allow_anonymous_access if write_access else was_public
		if is_public and (path_changed or not was_public):
			if reason := self.anonymous_access_block_reason(using=using, relative_path=path.as_posix()):
				raise ValidationError({"relative_path": reason})

	def save(self, *, force_insert=False, force_update=False, using=None, update_fields=None) -> None:
		using = using or router.db_for_write(type(self), instance=self)
		if update_fields is not None:
			update_fields = frozenset(update_fields)
		self._validate_path_and_anonymous_access(using, update_fields)
		super().save(force_insert=force_insert, force_update=force_update, using=using, update_fields=update_fields)
