from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from django.apps import apps
from django.db.models import Model


ModelKey = tuple[str, str]

_delete_permission_exemptions: dict[ModelKey, set[ModelKey]] = defaultdict(set)


def _normalize_model_key(model_or_label: type[Model] | str) -> ModelKey:
    if isinstance(model_or_label, str):
        app_label, model_name = model_or_label.split(".", 1)
        return app_label, model_name.lower()

    return model_or_label._meta.app_label, model_or_label._meta.model_name


def register_delete_permission_exemptions(
    source_model: type[Model] | str,
    exempt_models: Iterable[type[Model] | str],
) -> None:
    source_key = _normalize_model_key(source_model)
    _delete_permission_exemptions[source_key].update(
        _normalize_model_key(model) for model in exempt_models
    )


def discard_registered_delete_permissions(objs, perms_needed):
    source_keys = {
        (obj._meta.app_label, obj._meta.model_name)
        for obj in objs
        if getattr(obj, "_meta", None) is not None
    }

    for source_key in source_keys:
        for model_key in _delete_permission_exemptions.get(source_key, set()):
            try:
                model = apps.get_model(*model_key)
            except LookupError:
                continue
            perms_needed.discard(str(model._meta.verbose_name))

    return perms_needed