from django.apps import AppConfig


class TrainingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = 'training'

    def ready(self):
        from django.db.models.signals import post_delete
        from .log_templates import delete_template_file
        from .models import TrainingLogTemplate

        post_delete.connect(delete_template_file, sender=TrainingLogTemplate,
                            dispatch_uid="training_log_template_cleanup", weak=False)
        from core.utils.signals import register_file_cleanup_signals
        from .models import TaskExecutionAttachment, TrainingLog, TrainingPlan, TrainingTaskAttachment

        register_file_cleanup_signals(TrainingPlan, file_field="source_file")
        register_file_cleanup_signals(TrainingTaskAttachment, file_field="file")
        register_file_cleanup_signals(TaskExecutionAttachment, file_field="file")
        register_file_cleanup_signals(TrainingLog, file_field="document", delete_on_commit=True)

    verbose_name = "训练管理"
