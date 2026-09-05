"""评测资料先暂存，再以不覆盖的方式原子发布到业务目录。"""

import os
import tempfile
from pathlib import Path

from django.core.exceptions import SuspiciousFileOperation
from django.utils.deconstruct import deconstructible

from core.uploads import PrivateMediaStorage


@deconstructible
class AssessmentDocumentStorage(PrivateMediaStorage):
    def __init__(self):
        super().__init__("assessments")

    def get_available_name(self, name, max_length=None):
        # 不调用父类的随机后缀机制；并发下的最后防线是 _save 中的独占链接。
        if max_length is not None and len(name) > max_length:
            raise SuspiciousFileOperation("评测资料存储路径过长。")
        if self.exists(name):
            raise FileExistsError("目标文件已存在。")
        return name

    def _save(self, name, content):
        destination = Path(self.path(name))
        temporary_root = Path(self.location) / ".tmp"
        temporary_root.mkdir(parents=True, exist_ok=True)
        temporary = None
        published = False
        try:
            with tempfile.NamedTemporaryFile(dir=temporary_root, suffix=".upload", delete=False) as stream:
                temporary = Path(stream.name)
                for chunk in content.chunks():
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if self.file_permissions_mode is not None:
                os.chmod(temporary, self.file_permissions_mode)
            destination.parent.mkdir(parents=True, exist_ok=True)
            # 同一存储根目录内建立硬链接：完整文件一次可见，已存在目标绝不覆盖。
            os.link(temporary, destination)
            published = True
            temporary.unlink()
            return str(name).replace("\\", "/")
        except Exception:
            if published:
                destination.unlink(missing_ok=True)
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
