from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.urls import reverse
from django.utils.html import format_html

from .models import NoteRepo


@admin.register(NoteRepo)
class NoteRepoAdmin(admin.ModelAdmin):
	list_display = (
		"slug",
		"relative_path",
		"title",
		"is_visible",
		"allow_anonymous_access",
		"public_access_url",
		"order",
		"allowed_groups_display",
		"tags",
	)
	list_filter = ("is_visible", "allow_anonymous_access")
	search_fields = ("slug", "relative_path", "title", "description", "tags")
	filter_horizontal = ("allowed_groups",)
	readonly_fields = ("public_access_url",)

	def get_readonly_fields(self, request, obj=None):
		fields = super().get_readonly_fields(request, obj)
		return fields if request.user.is_superuser else (*fields, "allow_anonymous_access")

	def save_model(self, request, obj, form, change):
		if request.user.is_superuser:
			return super().save_model(request, obj, form, change)

		using = router.db_for_write(self.model, instance=obj)
		with transaction.atomic(using=using):
			previous = False
			if change:
				previous = (
					self.model.objects.using(using)
					.select_for_update()
					.values_list(
						"allow_anonymous_access",
						flat=True,
					)
					.get(pk=obj.pk)
				)
			if obj.allow_anonymous_access != previous:
				raise PermissionDenied("只有超级管理员可以修改笔记仓库的匿名访问开关。")
			super().save_model(request, obj, form, change)

	@admin.display(description="匿名访问链接")
	def public_access_url(self, obj):
		if obj is None or obj.pk is None or not obj.allow_anonymous_access:
			return "未公开"
		if reason := obj.anonymous_access_block_reason():
			return f"公开配置因目录问题暂未生效。{reason}"
		if not obj.is_visible:
			return "公开配置已开启，仓库当前不可见。"
		url = reverse("notes:note_repo_index", kwargs={"repo": obj.slug})
		return format_html('<a href="{}">{}</a>', url, url)

	@admin.display(description="允许访问的用户组")
	def allowed_groups_display(self, obj):
		return ", ".join(group.name for group in obj.allowed_groups.all())
