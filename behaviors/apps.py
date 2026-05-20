from django.apps import AppConfig


class BehaviorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'behaviors'
    label = 'behaviors'
    verbose_name = '学生奖惩管理'

    def ready(self):
        from core.utils.admin_deletion import register_delete_permission_exemptions

        register_delete_permission_exemptions(
            'auth.User',
            ['behaviors.ConductSummary'],
        )
