from django.contrib import admin

from .models import ArchiveAsset


@admin.register(ArchiveAsset)
class ArchiveAssetAdmin(admin.ModelAdmin):
    list_display = ("title", "asset_type", "skill_project", "business_date", "uploaded_by", "is_locked", "sha256_short")
    list_filter = ("asset_type", "skill_project", "is_locked", "business_date")
    search_fields = ("title", "original_filename", "file_sha256", "source_external_id")
    readonly_fields = ("file_sha256", "uploaded_at", "updated_at")
