from django.core.management.base import BaseCommand

from samba.services import mark_stale_running_operations, process_pending_operations


class Command(BaseCommand):
    help = '处理已排队的 Samba 操作。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=20,
            help='本次最多处理多少条待执行操作，默认 20。',
        )

    def handle(self, *args, **options):
        stale_count = mark_stale_running_operations()
        processed = process_pending_operations(limit=options['limit'], recover_stale=False)
        if stale_count:
            self.stdout.write(self.style.WARNING(f'已将 {stale_count} 条超时 Samba 操作标记为失败。'))
        self.stdout.write(self.style.SUCCESS(f'已处理 {processed} 条 Samba 操作。'))
