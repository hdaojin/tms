from django.apps import AppConfig


class AssessmentsConfig(AppConfig):
    name = 'assessments'

    def ready(self):
        from core.utils.signals import register_file_cleanup_signals
        from .models import AssessmentDocument

        register_file_cleanup_signals(AssessmentDocument, file_field="file")
