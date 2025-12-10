# core/management/commands/listperms.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission

class Command(BaseCommand):
    help = "列出指定 app 下的所有权限 codename，格式为 app_label.codename"

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label",
            nargs="?",
            type=str,
            help="App 的标签（例如 traininglogs, meeting, docs）"
        )

    def handle(self, *args, **options):
        app_label = options.get("app_label")
        qs = Permission.objects.all().select_related("content_type")

        if app_label:
            qs = qs.filter(content_type__app_label=app_label)

        if not qs.exists():
            self.stdout.write(self.style.WARNING(f"没有找到权限（app_label={app_label}）"))
            return

        for p in qs.order_by("content_type__app_label", "codename"):
            line = f"{p.content_type.app_label}.{p.codename}"
            self.stdout.write(line)
