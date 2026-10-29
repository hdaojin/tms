from pathlib import Path
import re

from django.core.exceptions import ValidationError
from django.core.files.utils import validate_file_name

from accounts.services.users import get_user_display_name
from core.uploads import PrivateMediaStorage


DUPLICATE_LOG_MESSAGE = "日志文件或当天日志已存在，请先联系管理员删除已有的训练日志及文件。"


class TrainingLogStorage(PrivateMediaStorage):
    """日志文件不覆盖、不自动添加随机后缀。"""

    def deconstruct(self):
        return ("training.log_files.TrainingLogStorage", [self.subdir], {})

    def get_valid_name(self, name):
        return validate_file_name(name)

    def get_alternative_name(self, file_root, file_ext):
        raise ValidationError(DUPLICATE_LOG_MESSAGE)


def build_log_filename(log, original_name):
    if not f"{log.author.last_name}{log.author.first_name}".strip():
        raise ValidationError("请先在用户资料中填写真实姓名，再上传日志文件。")
    member = log.training_cycle.members.filter(user=log.author).first()
    if member is None:
        raise ValidationError("请先加入所选训练周期并设置选手或教练身份，再上传日志文件。")
    filename = (
        f"{log.training_cycle.skill_project.name}{log.training_date:%Y年%m月%d日}"
        f"{member.get_role_display()}日志-{get_user_display_name(log.author)}{Path(original_name).suffix}"
    )
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', filename) or len(filename.encode("utf-8")) > 255:
        raise ValidationError("项目名称或姓名包含文件名不支持的字符，或生成的文件名过长，请先修改资料。")
    return filename
