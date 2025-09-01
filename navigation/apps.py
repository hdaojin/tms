from django.apps import AppConfig


class NavigationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'navigation'

    verbose_name = "菜单管理"
    verbose_name_plural = "菜单管理"
