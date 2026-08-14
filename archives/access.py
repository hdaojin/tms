from __future__ import annotations

from .models import ArchiveAsset


SCOPED_TARGETS = {
    ("training", "traininglog"),
    ("scoring", "scoringparticipant"),
    ("scoring", "scoringresult"),
}
SUPPORTED_TARGET_APPS = {
    "archives",
    "events",
    "examcontent",
    "glossary",
    "knowledge",
    "meetings",
    "notices",
    "scoring",
    "standards",
    "training",
    "worldskills_forum",
}


def can_access_archive_asset(user, asset: ArchiveAsset) -> bool:
    if not user.has_perm("archives.view_archiveasset"):
        return False
    if asset.target_content_type_id is None and asset.target_object_id is None:
        return True
    if asset.target_content_type_id is None or asset.target_object_id is None:
        return False
    app_label = asset.target_content_type.app_label
    model_name = asset.target_content_type.model
    if app_label not in SUPPORTED_TARGET_APPS:
        return False
    target = asset.target_object
    if target is None:
        return False
    if (app_label, model_name) == ("training", "traininglog"):
        from training.selectors import training_logs_visible_to

        return training_logs_visible_to(user).filter(pk=target.pk).exists()
    if (app_label, model_name) == ("scoring", "scoringparticipant"):
        from scoring.selectors import scoring_participants_visible_to

        return scoring_participants_visible_to(user).filter(pk=target.pk).exists()
    if (app_label, model_name) == ("scoring", "scoringresult"):
        from scoring.selectors import scoring_results_visible_to

        return scoring_results_visible_to(user).filter(pk=target.pk).exists()
    if (app_label, model_name) in SCOPED_TARGETS:
        return False
    return user.has_perm(f"{app_label}.view_{model_name}")


def archive_assets_visible_to(user, queryset=None):
    queryset = queryset if queryset is not None else ArchiveAsset.objects.all()
    queryset = queryset.select_related("target_content_type")
    allowed_ids = [asset.pk for asset in queryset if can_access_archive_asset(user, asset)]
    return ArchiveAsset.objects.filter(pk__in=allowed_ids)
