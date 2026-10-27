import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


class ProductionDeploymentSettingsTests(SimpleTestCase):
    def test_external_media_and_proxy_security_settings(self):
        repository_root = Path(__file__).resolve().parent.parent
        public_media = repository_root / ".test-production-media"
        private_media = repository_root / ".test-production-media-private"
        notes_root = private_media / "notes"
        child_environment = os.environ.copy()
        child_environment.update(
            {
                "DEBUG": "False",
                "SECRET_KEY": "production-test-secret-key-with-sufficient-entropy",
                "ALLOWED_HOSTS": "test.itnsa.cn,127.0.0.1",
                "CSRF_TRUSTED_ORIGINS": "https://test.itnsa.cn",
                "DATABASE_URL": "sqlite:///:memory:",
                "MEDIA_ROOT": str(public_media),
                "PRIVATE_MEDIA_ROOT": str(private_media),
                "NOTES_ROOT": str(notes_root),
                "TRUST_X_FORWARDED_PROTO": "True",
                "SECURE_SSL_REDIRECT": "True",
                "SESSION_COOKIE_SECURE": "True",
                "CSRF_COOKIE_SECURE": "True",
                "SECURE_HSTS_SECONDS": "3600",
                "SECURE_HSTS_INCLUDE_SUBDOMAINS": "False",
                "SECURE_HSTS_PRELOAD": "False",
            }
        )
        script = """
import json
from django.conf import settings

print(json.dumps({
    "media_root": str(settings.MEDIA_ROOT),
    "private_media_root": str(settings.PRIVATE_MEDIA_ROOT),
    "notes_root": str(settings.NOTES_ROOT),
    "proxy_header": settings.SECURE_PROXY_SSL_HEADER,
    "ssl_redirect": settings.SECURE_SSL_REDIRECT,
    "session_cookie_secure": settings.SESSION_COOKIE_SECURE,
    "csrf_cookie_secure": settings.CSRF_COOKIE_SECURE,
    "hsts_seconds": settings.SECURE_HSTS_SECONDS,
    "hsts_include_subdomains": settings.SECURE_HSTS_INCLUDE_SUBDOMAINS,
    "hsts_preload": settings.SECURE_HSTS_PRELOAD,
}))
"""

        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=repository_root,
            env=child_environment,
            check=True,
            capture_output=True,
            text=True,
        )
        configured = json.loads(completed.stdout)

        self.assertEqual(configured["media_root"], str(public_media))
        self.assertEqual(configured["private_media_root"], str(private_media))
        self.assertEqual(configured["notes_root"], str(notes_root))
        self.assertEqual(configured["proxy_header"], ["HTTP_X_FORWARDED_PROTO", "https"])
        self.assertTrue(configured["ssl_redirect"])
        self.assertTrue(configured["session_cookie_secure"])
        self.assertTrue(configured["csrf_cookie_secure"])
        self.assertEqual(configured["hsts_seconds"], 3600)
        self.assertFalse(configured["hsts_include_subdomains"])
        self.assertFalse(configured["hsts_preload"])

