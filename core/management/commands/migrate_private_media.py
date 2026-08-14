from dataclasses import dataclass
from hashlib import sha256

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from behaviors.models import ConductRecord
from core.uploads import PrivateMediaStorage
from meetings.models import Meeting
from notices.models import NoticeAttachment


@dataclass
class Move:
    instance: object
    field_name: str
    source_name: str
    target_name: str
    target_storage: PrivateMediaStorage


def _storage_digest(storage, name: str) -> bytes:
    digest = sha256()
    with storage.open(name, "rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.digest()


class Command(BaseCommand):
    help = "把会议、通知和奖惩附件从公共 MEDIA_ROOT 迁入私有存储；默认 dry-run。"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="执行文件复制、字段更新和公共副本删除。")

    def handle(self, *args, **options):
        moves = []
        already_private = 0
        missing = 0
        conflicts = 0
        specs = (
            (Meeting, "file", "meetings", PrivateMediaStorage("meetings")),
            (NoticeAttachment, "file", "notices", PrivateMediaStorage("notices")),
            (ConductRecord, "attachment", "behaviors", PrivateMediaStorage("behaviors")),
        )
        for model, field_name, prefix, target_storage in specs:
            for instance in model.objects.exclude(**{field_name: ""}).iterator():
                field = getattr(instance, field_name)
                source_name = field.name
                if not source_name:
                    continue
                target_name = source_name.replace("\\", "/")
                expected_prefix = f"{prefix}/"
                if target_name.startswith(expected_prefix):
                    target_name = target_name[len(expected_prefix):]
                if not default_storage.exists(source_name):
                    if target_storage.exists(target_name):
                        already_private += 1
                    else:
                        missing += 1
                    continue
                if target_storage.exists(target_name) and _storage_digest(
                    default_storage, source_name
                ) != _storage_digest(target_storage, target_name):
                    conflicts += 1
                    continue
                moves.append(Move(instance, field_name, source_name, target_name, target_storage))

        self.stdout.write(
            f"检测完成：待迁移 {len(moves)} 个，已在私有存储 {already_private} 个，"
            f"源文件缺失 {missing} 个，目标冲突 {conflicts} 个。"
        )
        if not options["apply"]:
            self.stdout.write("当前为 dry-run；备份并确认后使用 --apply 执行。")
            return
        if missing or conflicts:
            raise CommandError(
                "存在源文件缺失或私有目标冲突，未执行任何迁移。请先从备份恢复或核对记录。"
            )

        copied = []
        try:
            for move in moves:
                if not move.target_storage.exists(move.target_name):
                    with default_storage.open(move.source_name, "rb") as source:
                        saved_name = move.target_storage.save(move.target_name, source)
                    if saved_name != move.target_name:
                        raise CommandError(f"私有目标文件名冲突：{move.target_name}")
                    copied.append(move)
            with transaction.atomic():
                for move in moves:
                    type(move.instance).objects.filter(pk=move.instance.pk).update(
                        **{move.field_name: move.target_name}
                    )
        except Exception as exc:
            for move in copied:
                move.target_storage.delete(move.target_name)
            raise CommandError(f"迁移失败，数据库未切换：{exc}") from exc

        for move in moves:
            default_storage.delete(move.source_name)
        self.stdout.write(self.style.SUCCESS(f"已迁移 {len(moves)} 个文件并删除公共副本。"))
