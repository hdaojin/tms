from django.apps import AppConfig


class TrainingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = 'training'

    def ready(self):
        from core.utils.signals import register_file_cleanup_signals
        from .models import TaskExecutionAttachment, TrainingLog, TrainingPlan, TrainingTaskAttachment

        register_file_cleanup_signals(TrainingPlan, file_field="source_file")
        register_file_cleanup_signals(TrainingTaskAttachment, file_field="file")
        register_file_cleanup_signals(TaskExecutionAttachment, file_field="file")
        register_file_cleanup_signals(TrainingLog, file_field="document")

    verbose_name = "训练管理"
