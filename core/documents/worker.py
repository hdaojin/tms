"""Child renderer. Standard input and output are private pipes."""

import base64
import json
import logging
import signal
import subprocess
import sys

from .limits import MAX_PDF_BYTES, PDF_ADDRESS_SPACE_BYTES, PDF_TIMEOUT_SECONDS


class RenderErrors(logging.Handler):
    failed = False

    def emit(self, record):
        # Do not retain or print document contents or resource URLs.
        self.failed = True


def render_payload(payload):
    from weasyprint import CSS, HTML
    from weasyprint.text.fonts import FontConfiguration
    from weasyprint.urls import FatalURLFetchingError, URLFetcher, URLFetcherResponse

    images = {url: (base64.b64decode(data), mime) for url, (data, mime) in payload["images"].items()}

    class AssetFetcher(URLFetcher):
        def fetch(self, url, headers=None):
            if url not in images:
                raise FatalURLFetchingError("Resource outside document assets")
            data, mime = images[url]
            return URLFetcherResponse(url, data, {"Content-Type": mime})

    logger = logging.getLogger("weasyprint")
    errors = RenderErrors(level=logging.ERROR)
    logger.addHandler(errors)
    try:
        fetcher = AssetFetcher()
        config = FontConfiguration()
        styles = [CSS(string=css, url_fetcher=fetcher, font_config=config) for css in payload["styles"]]
        pdf = HTML(string=payload["html"], url_fetcher=fetcher).write_pdf(stylesheets=styles, font_config=config)
    except FatalURLFetchingError as exc:
        raise ValueError("Unexpected PDF resource") from exc
    finally:
        logger.removeHandler(errors)
    if errors.failed:
        raise ValueError("PDF renderer reported an error")
    return pdf


def main():
    import resource

    signal.alarm(PDF_TIMEOUT_SECONDS)
    _, address_space = resource.getrlimit(resource.RLIMIT_AS)
    if address_space == resource.RLIM_INFINITY or address_space > PDF_ADDRESS_SPACE_BYTES:
        address_space = PDF_ADDRESS_SPACE_BYTES
    resource.setrlimit(resource.RLIMIT_AS, (address_space, address_space))
    try:
        for font in ("Noto Sans CJK SC", "Noto Serif CJK SC"):
            match = subprocess.run(
                ["fc-match", "--format=%{family}", font],
                capture_output=True,
                text=True,
                check=True,
                timeout=3,
            )
            if font not in match.stdout.split(","):
                return 3
        pdf = render_payload(json.load(sys.stdin.buffer))
        if len(pdf) > MAX_PDF_BYTES:
            return 5
        sys.stdout.buffer.write(pdf)
    except MemoryError:
        return 4
    except (ImportError, OSError, subprocess.SubprocessError):
        return 2
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
