import os
import shutil
import subprocess
from pathlib import Path

from django.test import SimpleTestCase


class DeploymentAssetsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.repository_root = Path(__file__).resolve().parent.parent
        cls.deploy_script = cls.repository_root / "scripts" / "deploy_tms.sh"

    def test_deploy_script_has_valid_bash_syntax(self):
        bash = os.environ.get("TMS_TEST_BASH") or (shutil.which("bash") if os.name != "nt" else None)
        if bash is None:
            self.skipTest("bash -n is exercised on Linux CI and by the release checklist")

        subprocess.run([bash, "-n", str(self.deploy_script)], check=True)
        subprocess.run([bash, "-n", str(self.repository_root / "scripts/update_tms.sh")], check=True)

    def test_help_documents_stable_command_surface(self):
        script = self.deploy_script.read_text(encoding="utf-8")
        for command in (
            "inspect [--json]",
            "plan [--revision REVISION] [--first-install] [--json]",
            "apply PLAN_ID --confirm-sha FULL_SHA",
            "verify [--json]",
            "status [--json]",
            "rollback --to RELEASE_ID",
            "auth add|remove|list [USERNAME]",
            "admin create",
            "manage COMMAND [ARGS...]",
            "prune [--keep NUMBER] [--yes]",
        ):
            self.assertIn(command, script)

    def test_plan_is_bound_to_paths_sha_and_installed_inputs(self):
        script = self.deploy_script.read_text(encoding="utf-8")

        for setting in (
            'readonly REPOSITORY_DIR="${ROOT_DIR}/repository.git"',
            'readonly RELEASES_DIR="${ROOT_DIR}/releases"',
            'readonly CURRENT_LINK="${ROOT_DIR}/current"',
            'readonly PLAN_DIR="${STATE_DIR}/deploy-plans"',
            'SCRIPT_SHA256=',
            'CONFIG_SHA256=',
            'SERVICE_TEMPLATE_SHA256=',
            'CADDY_TEMPLATE_SHA256=',
            'sha256sum -c "${plan_id}.manifest.sha256"',
            'StrictHostKeyChecking=yes',
            'uv sync --locked --no-dev --link-mode copy --python /usr/bin/python3.13',
        ):
            self.assertIn(setting, script)

        checksum_index = script.index('sha256sum -c "${plan_id}.manifest.sha256"')
        source_index = script.index('source "${manifest}"')
        self.assertLess(checksum_index, source_index)
        self.assertNotIn("npm run", script)

    def test_caddy_template_never_exposes_private_media(self):
        template = (
            self.repository_root / "deploy" / "production" / "tms.caddy"
        ).read_text(encoding="utf-8")

        self.assertIn("/srv/tms/shared/media", template)
        self.assertNotIn("media-private", template)
        self.assertIn("reverse_proxy @@BIND@@", template)
        self.assertIn("/var/lib/tms", template)

    def test_systemd_template_uses_restricted_runtime_user(self):
        template = (
            self.repository_root / "deploy" / "production" / "tms.service"
        ).read_text(encoding="utf-8")

        for setting in (
            "User=@@APP_USER@@",
            "Group=@@APP_GROUP@@",
            "NoNewPrivileges=true",
            "PrivateTmp=true",
            "ProtectSystem=strict",
            "ProtectHome=true",
            "UMask=0027",
            "@@BIND@@",
            "@@WORKERS@@",
        ):
            self.assertIn(setting, template)

        defaults = (
            self.repository_root / "deploy" / "production" / "deploy.conf.example"
        ).read_text(encoding="utf-8")
        self.assertIn("TMS_APP_USER=tms", defaults)
        self.assertIn("TMS_BIND=127.0.0.1:8010", defaults)
        self.assertIn("TMS_WORKERS=2", defaults)

