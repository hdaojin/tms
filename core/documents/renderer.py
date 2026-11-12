import base64
import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings

from .limits import MAX_PDF_BYTES, PDF_TIMEOUT_SECONDS
from .types import DocumentBusy, DocumentRenderError


@contextmanager
def render_slot():
    if sys.platform != "linux":
        raise DocumentRenderError("PDF 渲染需要 Linux 环境。当前仍可使用 HTML 预览。")
    import fcntl

    instance = hashlib.sha256(os.fsencode(Path(settings.PRIVATE_MEDIA_ROOT).resolve())).hexdigest()[:16]
    lock_path = Path(tempfile.gettempdir()) / f"tms-pdf-{os.getuid()}-{instance}.lock"
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError as exc:
        raise DocumentRenderError("无法打开 PDF 渲染锁，请检查临时目录权限。") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise DocumentRenderError("PDF 渲染锁的文件类型或所有者无效。")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DocumentBusy("已有文档正在转换，请稍后重试。") from exc
        # The child inherits the lock. A terminated Web worker cannot leave an unlocked renderer behind.
        yield descriptor
    finally:
        os.close(descriptor)


def render_pdf(html: str, styles: list[str], images: dict[str, tuple[bytes, str]], *, lock: int) -> bytes:
    payload = json.dumps(
        {
            "html": html,
            "styles": styles,
            "images": {
                src: (base64.b64encode(content).decode("ascii"), mime) for src, (content, mime) in images.items()
            },
        },
        ensure_ascii=False,
    ).encode()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "core.documents.worker"],
            cwd=settings.BASE_DIR,
            input=payload,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            pass_fds=(lock,),
            timeout=PDF_TIMEOUT_SECONDS + 2,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DocumentRenderError("PDF 转换超时，请缩短正文或减少图片后重试。") from exc
    except OSError as exc:
        raise DocumentRenderError("无法启动 PDF 渲染进程。") from exc

    error_messages = {
        2: "PDF 渲染依赖不可用，请检查 WeasyPrint、Pango 和 Fontconfig。",
        3: "缺少 Noto CJK 中文字体，请安装 fonts-noto-cjk。",
        4: "PDF 转换超出内存限制，请减少图片或简化正文。",
        5: "生成的 PDF 超过大小限制。",
        -signal.SIGALRM: "PDF 转换超时，请缩短正文或减少图片后重试。",
        -signal.SIGXCPU: "PDF 转换超时，请简化正文后重试。",
    }
    if result.returncode != 0 or not result.stdout.startswith(b"%PDF-") or len(result.stdout) > MAX_PDF_BYTES:
        raise DocumentRenderError(error_messages.get(result.returncode, "PDF 转换失败，请检查正文或运行 PDF 自检。"))
    return result.stdout
