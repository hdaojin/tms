from django.core.checks import Error, register

from .registry import PermissionBundleCatalogError, validate_declared_permissions
from core.config_loader import ConfigurationError
from core.navigation import validate_navigation_config


@register()
def check_permission_bundle_catalog(app_configs, **kwargs):
    try:
        validate_declared_permissions()
    except PermissionBundleCatalogError as exc:
        return [Error(str(exc), id="core.E001")]
    return []


@register()
def check_navigation_config(app_configs, **kwargs):
    try:
        validate_navigation_config()
    except ConfigurationError as exc:
        return [Error(str(exc), id="core.E002")]
    return []
