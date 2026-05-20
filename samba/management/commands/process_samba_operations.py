from django.core.management.base import BaseCommand

from samba.services import process_pending_operations


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
        processed = process_pending_operations(limit=options['limit'])
        self.stdout.write(self.style.SUCCESS(f'已处理 {processed} 条 Samba 操作。'))