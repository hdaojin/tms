from django.contrib import admin

from .models import NoteRepo


@admin.register(NoteRepo)
class NoteRepoAdmin(admin.ModelAdmin):
	list_display = (
		"slug",
		"relative_path",
		"title",
		"is_visible",
		"order",
		"allowed_groups_display",
		"tags",
	)
	list_filter = ("is_visible",)
	search_fields = ("slug", "relative_path", "title", "description", "tags")
	filter_horizontal = ("allowed_groups",)

	@admin.display(description="允许访问的用户组")
	def allowed_groups_display(self, obj):
		return ", ".join(group.name for group in obj.allowed_groups.all())
