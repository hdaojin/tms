from __future__ import annotations

from django.core.exceptions import ValidationError


def validate_competition_module_mapping_target(
    *,
    competition_module,
    target,
    field_name: str,
    error_message: str,
) -> None:
    if competition_module is None or target is None:
        return

    competition_project = getattr(competition_module, 'competition_project', None)
    if competition_project is None:
        return

    if competition_project.project_id != target.project_id:
        raise ValidationError({field_name: error_message})


def validate_single_primary_mapping(*, instance, error_message: str) -> None:
    if not getattr(instance, 'is_primary', False) or not getattr(instance, 'competition_module_id', None):
        return

    existing_primary = type(instance).objects.filter(
        competition_module_id=instance.competition_module_id,
        is_primary=True,
    ).exclude(pk=instance.pk)
    if existing_primary.exists():
        raise ValidationError({'is_primary': error_message})


def validate_primary_inline_forms(forms, *, duplicate_message: str, missing_message: str) -> None:
    active_forms = [
        form
        for form in forms
        if getattr(form, 'cleaned_data', None) and not form.cleaned_data.get('DELETE', False)
    ]
    if not active_forms:
        return

    primary_forms = [form for form in active_forms if form.cleaned_data.get('is_primary')]
    if len(primary_forms) > 1:
        raise ValidationError(duplicate_message)
    if len(primary_forms) == 0:
        raise ValidationError(missing_message)