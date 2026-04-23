import subprocess
import sys

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


CUTOVER_COMMANDS = [
    "cutover_assessment_to_assessments",
    "cutover_conduct_to_behaviors",
    "cutover_meeting_to_meetings",
]


class Command(BaseCommand):
    help = "统一预检查或执行 assessments、behaviors、meetings 的内部标识切换收尾，并在执行模式下自动运行 migrate。"

    def _run_migrate_in_fresh_process(self, database):
        command = [
            sys.executable,
            "manage.py",
            "migrate",
            f"--database={database}",
        ]
        result = subprocess.run(
            command,
            cwd=settings.BASE_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            self.stdout.write(result.stdout, ending="")
        if result.stderr:
            self.stderr.write(result.stderr, ending="")
        if result.returncode != 0:
            raise CommandError("统一执行 migrate 失败，请检查上面的输出。")

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="default",
            help="要操作的数据库别名，默认 default。",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="实际执行收尾；默认仅输出预检查结果。",
        )
        parser.add_argument(
            "--skip-migrate",
            action="store_true",
            help="执行收尾后跳过自动 migrate。",
        )

    def handle(self, *args, **options):
        database = options["database"]
        execute = options["execute"]
        skip_migrate = options["skip_migrate"]

        for command_name in CUTOVER_COMMANDS:
            self.stdout.write(f"==> {command_name}")
            command_options = {
                "database": database,
                "stdout": self.stdout,
            }
            if execute:
                command_options["execute"] = True
            call_command(command_name, **command_options)

        if execute and not skip_migrate:
            self.stdout.write("==> migrate")
            self._run_migrate_in_fresh_process(database)

        if execute:
            if skip_migrate:
                self.stdout.write(self.style.SUCCESS("内部切换收尾已执行完成。接下来请手动运行 manage.py migrate。"))
            else:
                self.stdout.write(self.style.SUCCESS("内部切换收尾与 migrate 已执行完成。"))
        else:
            self.stdout.write(self.style.WARNING("以上为统一预检查结果。确认无误后，请追加 --execute 执行实际收尾。"))