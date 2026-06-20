from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from django.contrib.contenttypes.models import ContentType

from archives.models import ArchiveAsset


def create_training_log_asset(training_log, uploaded_file, user=None):
    return ArchiveAsset.objects.create(
        target_content_type=ContentType.objects.get_for_model(training_log),
        target_object_id=training_log.pk,
        skill_project=training_log.training_cycle.skill_project,
        asset_type=ArchiveAsset.AssetType.TRAINING_LOG,
        title=f"{training_log.training_date:%Y-%m-%d} {training_log.topic}",
        file=uploaded_file,
        original_filename=getattr(uploaded_file, "name", ""),
        business_date=training_log.training_date,
        uploaded_by=user or training_log.uploaded_by,
    )


def build_training_log_archive(queryset):
    buffer = BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for log in queryset.select_related("training_cycle", "uploaded_by", "capability_domain"):
            asset = log.primary_asset
            if asset is None or not asset.file:
                continue
            user_label = getattr(log.uploaded_by, "display_name", None) or log.uploaded_by.get_username()
            domain = log.capability_domain.code if log.capability_domain_id else "NO-DOMAIN"
            filename = asset.filename or PurePosixPath(asset.file.name).name
            arcname = PurePosixPath(
                f"{log.training_date:%Y-%m}",
                log.training_cycle.code,
                domain,
                f"{log.training_date:%Y%m%d}-{user_label}-{filename}",
            )
            unique_arcname = str(arcname)
            suffix = 1
            while unique_arcname in used_names:
                unique_arcname = str(arcname.with_name(f"{arcname.stem}-{suffix}{arcname.suffix}"))
                suffix += 1
            used_names.add(unique_arcname)
            with asset.file.open("rb") as fh:
                archive.writestr(unique_arcname, fh.read())
    buffer.seek(0)
    return buffer.getvalue()
