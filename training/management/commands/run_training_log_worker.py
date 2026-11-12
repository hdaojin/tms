from time import sleep

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from training.log_generation import run_generation


class Command(BaseCommand):
    help = "处理训练日志 AI 生成队列。"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="检查并处理至多一条待生成任务后退出。")

    def handle(self, *args, **options):
        try:
            while True:
                close_old_connections()
                worked = run_generation()
                if options["once"]:
                    return
                if not worked:
                    sleep(2)
        except KeyboardInterrupt:
            return
