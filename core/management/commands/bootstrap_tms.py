from django.core.management.base import BaseCommand
from django.db import transaction

from assessments.bootstrap import bootstrap_defaults as bootstrap_assessments
from behaviors.bootstrap import bootstrap_defaults as bootstrap_behaviors
from core.bootstrap import bootstrap_defaults as bootstrap_core
from event_countdown.bootstrap import bootstrap_defaults as bootstrap_event_countdown
from feedback.bootstrap import bootstrap_defaults as bootstrap_feedback
from scoring.bootstrap import bootstrap_defaults as bootstrap_scoring
from worldskills_forum.bootstrap import bootstrap_defaults as bootstrap_worldskills_forum


BOOTSTRAP_STEPS = (
    ('core', bootstrap_core),
    ('assessments', bootstrap_assessments),
    ('feedback', bootstrap_feedback),
    ('worldskills_forum', bootstrap_worldskills_forum),
    ('behaviors', bootstrap_behaviors),
    ('event_countdown', bootstrap_event_countdown),
    ('scoring', bootstrap_scoring),
)


class Command(BaseCommand):
    help = '显式初始化 TMS 的默认业务目录和 Registry 配置。'
    requires_migrations_checks = True

    def handle(self, *args, **options):
        results = []
        with transaction.atomic():
            for app_label, bootstrap_function in BOOTSTRAP_STEPS:
                results.append((app_label, bootstrap_function()))

        for app_label, stats in results:
            self.stdout.write(
                f'{app_label}: created={stats["created"]}, existing={stats["existing"]}'
            )
        self.stdout.write(self.style.SUCCESS('TMS 默认业务目录初始化完成。'))
