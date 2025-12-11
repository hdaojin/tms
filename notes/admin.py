from django.contrib import admin

from .models import NoteRepo


@admin.register(NoteRepo)
class NoteRepoAdmin(admin.ModelAdmin):
	list_display = ("slug", "title", "is_visible", "order")
	list_filter = ("is_visible",)
	search_fields = ("slug", "title", "description", "tags")
	filter_horizontal = ("allowed_groups",)
