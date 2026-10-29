import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


REPOSITORY = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("tms_dependency_update", REPOSITORY / "scripts/update_dependencies.py")
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


def bash_run(script, *, check=True):
    bash = os.environ.get("TMS_TEST_BASH") or (shutil.which("bash") if os.name != "nt" else None)
    if not bash:
        pytest.skip("需要 Bash；Windows 可用 TMS_TEST_BASH 指定 Git Bash")
    environment = os.environ.copy()
    environment["TMS_TEST_PYTHON"] = Path(sys.executable).as_posix()
    if os.name == "nt":
        environment["MSYS2_ARG_CONV_EXCL"] = "/CN="
    result = subprocess.run(
        [bash, "-c", script, "bash", (REPOSITORY / "scripts/deploy_tms.sh").as_posix()],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_tls_modes_render_public_and_external_certificate_configs():
    result = bash_run('''
set -Eeuo pipefail
source "$1"
TEMPLATE_DIR_FROM_SCRIPT="$(dirname "$1")/../deploy/production"
TMS_TLS_MODE=automatic
validate_tls_config
render_caddy_site "${TEMPLATE_DIR_FROM_SCRIPT}/tms.caddy"
printf '\\nEXTERNAL_MODE\\n'
TMS_TLS_MODE=acme-sh
validate_tls_config
render_caddy_site "${TEMPLATE_DIR_FROM_SCRIPT}/tms.caddy"
''')
    public, external = result.stdout.split("EXTERNAL_MODE")
    assert "tls /etc/caddy/certs" not in public
    assert "tls /etc/caddy/certs/tms/current/fullchain.pem /etc/caddy/certs/tms/current/privkey.pem" in external
    assert "@@" not in result.stdout
    assert "media-private" not in result.stdout


def test_invalid_tls_mode_is_rejected():
    result = bash_run('source "$1"; TMS_TLS_MODE=internal; validate_tls_config', check=False)
    assert result.returncode != 0
    assert "automatic" in result.stderr


@pytest.mark.parametrize("supports_control_socket", [True, False])
def test_systemd_disables_control_socket_only_when_release_supports_flag(supports_control_socket):
    with patch.dict(os.environ, {"TMS_TEST_CONTROL_HELP": "--no-control-socket" if supports_control_socket else "--workers"}):
        result = bash_run('''
set -Eeuo pipefail
source "$1"
runuser() {
    [[ "$#" == 5 && "$1" == -u && "$2" == tms && "$3" == -- && "$4" == /candidate/.venv/bin/gunicorn && "$5" == --help ]] || return 99
    printf '%s\\n' "$TMS_TEST_CONTROL_HELP"
}
render_systemd_unit /candidate "$(dirname "$1")/../deploy/production/tms.service"
''')
    assert ("--no-control-socket" in result.stdout) is supports_control_socket
    assert "@@" not in result.stdout
    assert "ProtectSystem=strict" in result.stdout
    assert "ReadWritePaths=/srv/tms/shared/media /srv/tms/shared/media-private" in result.stdout


def test_gunicorn_help_failure_stops_service_rendering():
    result = bash_run('''
source "$1"
runuser() { return 42; }
render_systemd_unit /candidate "$(dirname "$1")/../deploy/production/tms.service"
''', check=False)
    assert result.returncode != 0
    assert result.stdout == ""


@pytest.mark.parametrize(("target", "mode"), [
    ("local", "ready_after_retry"),
    ("local", "unreachable"),
    ("https", "ready_after_retry"),
    ("https", "unreachable"),
    ("https", "wrong_http_status"),
])
def test_healthcheck_retries_quietly_and_reports_only_final_diagnostic(target, mode):
    with patch.dict(os.environ, {"TMS_TEST_HEALTH_TARGET": target, "TMS_TEST_HEALTH_MODE": mode}):
        result = bash_run('''
set -Eeuo pipefail
source "$1"
work="$(mktemp -d)"
trap 'rm -f "$work/attempts"; rmdir "$work"' EXIT
printf '0' >"$work/attempts"
sleep() { :; }
curl() {
    local count
    count=$(( $(cat "$work/attempts") + 1 ))
    printf '%s' "$count" >"$work/attempts"
    if [[ "$TMS_TEST_HEALTH_MODE" == unreachable || ( "$TMS_TEST_HEALTH_MODE" == ready_after_retry && "$count" == 1 ) ]]; then
        printf 'curl: (7) simulated connection refused\\n' >&2
        return 7
    fi
    if [[ "$TMS_TEST_HEALTH_TARGET" == https ]]; then
        if [[ "$TMS_TEST_HEALTH_MODE" == wrong_http_status ]]; then printf 200; else printf 401; fi
    fi
    return 0
}
result=0
if [[ "$TMS_TEST_HEALTH_TARGET" == local ]]; then
    local_healthcheck || result=$?
else
    https_healthcheck || result=$?
fi
if [[ "$TMS_TEST_HEALTH_MODE" == ready_after_retry ]]; then
    [[ "$(cat "$work/attempts")" == 2 && "$result" == 0 ]]
else
    if [[ "$TMS_TEST_HEALTH_TARGET" == local ]]; then expected=20; else expected=15; fi
    [[ "$(cat "$work/attempts")" == "$expected" && "$result" != 0 ]]
fi
''')
    assert result.stdout == ""
    if mode == "ready_after_retry":
        assert result.stderr == ""
    else:
        assert result.stderr.count("[WARN]") == 1
        if mode == "unreachable":
            assert result.stderr.count("simulated connection refused") == 1
        else:
            assert "HTTP=200" in result.stderr


def test_basic_auth_defaults_to_all_clients_and_only_explicit_networks_bypass():
    result = bash_run('''
set -Eeuo pipefail
source "$1"
policy_python() { "$TMS_TEST_PYTHON" "$@"; }
template="$(dirname "$1")/../deploy/production/tms.caddy"
[[ "$(basic_auth_policy 10.21.57.1)" == 1 ]]
render_caddy_site "$template"
printf '\\nTRUSTED_NETWORKS\\n'
TMS_BASIC_AUTH_TRUSTED_CIDRS="10.21.57.0/24 fd12:3456:789a::/64"
[[ "$(basic_auth_policy 10.21.57.1)" == 0 ]]
[[ "$(basic_auth_policy 10.21.58.1)" == 1 ]]
[[ "$(basic_auth_policy 192.168.1.1)" == 1 ]]
[[ "$(basic_auth_policy 127.0.0.1)" == 1 ]]
[[ "$(basic_auth_policy fd12:3456:789a::2)" == 0 ]]
[[ "$(basic_auth_policy fd12:3456:789b::2)" == 1 ]]
render_caddy_site "$template"
TMS_BASIC_AUTH_TRUSTED_CIDRS="127.0.0.1/32"
[[ "$(basic_auth_policy 127.0.0.1)" == 0 ]]
https_status_matches_policy 401 1
if https_status_matches_policy 200 1; then exit 10; fi
if https_status_matches_policy 401 0; then exit 11; fi
''')
    default, conditional = result.stdout.split("TRUSTED_NETWORKS")
    assert "@tms_basic_auth path *" in default
    assert "@tms_basic_auth not remote_ip 10.21.57.0/24 fd12:3456:789a::/64" in conditional
    assert "client_ip" not in conditional
    assert "X-Forwarded-For" not in conditional
    assert "@@" not in result.stdout


def test_explicitly_disabled_basic_auth_renders_django_only_and_checks_login_redirect():
    result = bash_run('''
set -Eeuo pipefail
source "$1"
TMS_BASIC_AUTH_ENABLED=0
render_caddy_site "$(dirname "$1")/../deploy/production/tms.caddy"
curl() { printf '302'; }
https_healthcheck
''')
    assert "tms_basic_auth" not in result.stdout
    assert "tms-basic-auth.caddy" not in result.stdout
    assert "@@" not in result.stdout
    assert "reverse_proxy 127.0.0.1:8010" in result.stdout


@pytest.mark.parametrize("cidrs", ["10.21.57.72/24", "10.21.57.0/33", "10.21.57.1", "10.21.57.0/24;abort", "not-a-network"])
def test_invalid_basic_auth_network_is_rejected(cidrs):
    with patch.dict(os.environ, {"TMS_TEST_CIDRS": cidrs}):
        result = bash_run('''
source "$1"
policy_python() { "$TMS_TEST_PYTHON" "$@"; }
TMS_BASIC_AUTH_TRUSTED_CIDRS="$TMS_TEST_CIDRS"
basic_auth_policy
''', check=False)
    assert result.returncode != 0
    assert "可信认证网段无效" in result.stderr


@pytest.mark.parametrize("python_available", [True, False])
def test_manage_pins_release_preserves_arguments_and_exit_status(python_available):
    with patch.dict(os.environ, {"TMS_TEST_PYTHON_AVAILABLE": str(int(python_available))}):
        result = bash_run('''
set -Eeuo pipefail
work="$(mktemp -d)"
trap 'rm -f "$work/releases/active/manage.py" "$work/tms.env"; rmdir "$work/releases/active" "$work/releases" "$work/current" "$work"' EXIT
source <(sed -e "s|^readonly ROOT_DIR=.*|readonly ROOT_DIR=\\"$work\\"|" \\
    -e "s|^readonly ENV_DIR=.*|readonly ENV_DIR=\\"$work\\"|" \\
    -e 's/\\[\\[ -L /[[ -d /g' "$1")
mkdir -p "$work/current" "$work/releases/active"
touch "$work/releases/active/manage.py" "$work/tms.env"
require_root() { :; }
require_root_owned_file() { :; }
safe_source_config() { :; }
readlink() { printf '%s\\n' "$work/releases/active"; }
run_as_app() {
    [[ "$#" == 4 && "$1" == "$work/releases/active/.venv/bin/python" && "$2" == -B && "$3" == -c ]] || return 91
    [[ "$TMS_TEST_PYTHON_AVAILABLE" == 1 ]]
}
env_run_as_app() {
    [[ "$PWD" == "$work/releases/active" ]] || return 92
    [[ "$#" == 7 && "$1" == "$work/tms.env" && "$2" == "$PWD/.venv/bin/python" && "$3" == -B && "$4" == "$PWD/manage.py" ]] || return 93
    [[ "$5" == bootstrap_tms && "$6" == --dry-run && "$7" == 'literal $value with spaces' ]] || return 94
    printf 'MANAGEMENT_CALLED\\n'
    return 23
}
main manage bootstrap_tms --dry-run 'literal $value with spaces'
''', check=False)
    if python_available:
        assert result.returncode == 23
        assert result.stdout.strip() == "MANAGEMENT_CALLED"
    else:
        assert result.returncode == 1
        assert "MANAGEMENT_CALLED" not in result.stdout
        assert "Python 3.13 环境不可用" in result.stderr


def test_manage_requires_root_before_loading_configuration():
    result = bash_run('''
source "$1"
require_root() { die "ROOT_REQUIRED"; }
safe_source_config() { printf 'CONFIG_LOADED\\n'; }
main manage check
''', check=False)
    assert result.returncode == 1
    assert "ROOT_REQUIRED" in result.stderr
    assert "CONFIG_LOADED" not in result.stdout


def test_runtime_environment_is_loaded_without_inherited_variables():
    result = bash_run('''
source "$1"
work="$(mktemp -d)"
trap 'rm -f "$work/runtime.env"; rmdir "$work"' EXIT
printf '# fixture\\nTEST_SETTING=literal $value with spaces\\n' >"$work/runtime.env"
export TMS_INHERITED_ONLY=must-not-leak
runuser() {
    [[ "$1" == -u && "$2" == tms && "$3" == -- ]] || return 95
    shift 3
    "$@"
}
env_run_as_app "$work/runtime.env" "$TMS_TEST_PYTHON" -c 'import os, pathlib; assert os.environ["TEST_SETTING"] == "literal $value with spaces"; assert "TMS_INHERITED_ONLY" not in os.environ; assert pathlib.Path(os.environ["HOME"]).as_posix().endswith("/var/lib/tms")'
''')
    assert result.stdout == ""


def test_update_entrypoint_rejects_first_install_and_unknown_commands():
    bash_run('''
set -Eeuo pipefail
entry="$(dirname "$1")/update_tms.sh"
if bash "$entry" plan --first-install; then exit 10; fi
if bash "$entry" prune; then exit 11; fi
bash "$entry" --help
''')


@pytest.mark.parametrize("skip_backup", [False, True])
def test_apply_backup_is_default_and_can_be_explicitly_skipped(skip_backup):
    with patch.dict(os.environ, {"TMS_TEST_SKIP_BACKUP": str(int(skip_backup))}):
        result = bash_run('''
set -Eeuo pipefail
work="$(mktemp -d)"
trap 'rm -f "$work/tms.env" "$work/migrate.env"; rmdir "$work/current" "$work"' EXIT
source <(sed -e "s|^readonly ROOT_DIR=.*|readonly ROOT_DIR=\\"$work\\"|" \\
    -e "s|^readonly ENV_DIR=.*|readonly ENV_DIR=\\"$work\\"|" \\
    -e 's/\\[\\[ -L /[[ -d /g' "$1")
# Use a directory fixture: Git Bash cannot reliably create native symlinks.
mkdir "$work/current"
touch "$work/tms.env" "$work/migrate.env"
require_root() { :; }
safe_source_config() { :; }
require_installed_layout() { :; }
require_cmd() { :; }
load_plan() { FIRST_INSTALL=0; SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa; }
check_external_certificate() { :; }
df() { printf 'Filesystem Available\\nmock 2097152\\n'; }
awk() { command awk 'NR==2 {print $2}'; }
backup_current() { printf 'BACKUP_CALLED\\n'; }
install_service_and_caddy() { printf 'CONTINUED\\n'; exit 0; }
args=()
[[ "$TMS_TEST_SKIP_BACKUP" == 0 ]] || args+=(--skip-backup)
cmd_apply plan-test --confirm-sha aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa "${args[@]}"
''')
    assert ("BACKUP_CALLED" in result.stdout) is not skip_backup
    assert "CONTINUED" in result.stdout
    assert ("本次升级不创建备份" in result.stderr) is skip_backup


def test_caddy_log_initialization_preserves_existing_content_and_other_logs():
    bash_run('''
set -Eeuo pipefail
source "$1"
work="$(mktemp -d)"
trap 'rm -f "$work/logs/tms-access.log" "$work/logs/other.log"; rmdir "$work/logs" "$work"' EXIT
ownership_calls=0
mode_calls=0
runuser() {
    [[ "$1" == -u && "$2" == caddy && "$3" == -- ]] || return 10
    shift 3
    "$@"
}
install() {
    [[ "$1" == -d && "$2" == -m && "$3" == 0750 && "$4" == -o && "$5" == caddy && "$6" == -g && "$7" == caddy ]] || return 11
    command mkdir -p "$8"
}
chown() {
    [[ "$1" == caddy:caddy && "$2" == "$work/logs/tms-access.log" ]] || return 12
    ownership_calls=$((ownership_calls + 1))
}
chmod() {
    [[ "$1" == 0640 && "$2" == "$work/logs/tms-access.log" ]] || return 13
    mode_calls=$((mode_calls + 1))
}
prepare_caddy_logging "$work/logs"
[[ -f "$work/logs/tms-access.log" ]]
printf 'existing TMS access log\\n' >"$work/logs/tms-access.log"
printf 'other site log\\n' >"$work/logs/other.log"
install() { printf 'existing directory must not be reinstalled\\n' >&2; return 14; }
prepare_caddy_logging "$work/logs"
[[ "$(cat "$work/logs/tms-access.log")" == 'existing TMS access log' ]]
[[ "$(cat "$work/logs/other.log")" == 'other site log' ]]
[[ "$ownership_calls" == 2 && "$mode_calls" == 2 ]]
''')


def test_caddy_log_symlink_is_rejected_without_touching_target():
    result = bash_run('''
set -Eeuo pipefail
source "$1"
work="$(mktemp -d)"
trap 'rm -f "$work/tms-access.log" "$work/target"; rmdir "$work"' EXIT
printf 'keep original\\n' >"$work/target"
ln -s "$work/target" "$work/tms-access.log"
[[ -L "$work/tms-access.log" ]] || exit 77
runuser() { shift 3; "$@"; }
chown() { printf 'unexpected chown\\n' >&2; exit 20; }
if (prepare_caddy_logging "$work"); then exit 21; fi
[[ "$(cat "$work/target")" == 'keep original' ]]
''', check=False)
    if result.returncode == 77:
        pytest.skip("当前文件系统不支持原生软链接")
    assert result.returncode == 0, result.stdout + result.stderr


def test_caddy_unwritable_log_directory_fails_before_creating_file():
    bash_run('''
set -Eeuo pipefail
source "$1"
work="$(mktemp -d)"
trap 'rmdir "$work"' EXIT
runuser() { return 1; }
if (prepare_caddy_logging "$work"); then exit 22; fi
[[ ! -e "$work/tms-access.log" ]]
''')


@pytest.mark.parametrize("exit_code", [0, 42])
def test_caddy_validation_uses_service_user_and_propagates_failure(exit_code):
    with patch.dict(os.environ, {"TMS_TEST_VALIDATE_EXIT": str(exit_code)}):
        result = bash_run('''
source "$1"
runuser() {
    [[ "$#" == 9 && "$1" == -u && "$2" == caddy && "$3" == -- && "$4" == caddy && "$5" == validate && "$6" == --config && "$7" == /etc/caddy/Caddyfile && "$8" == --adapter && "$9" == caddyfile ]] || return 99
    return "$TMS_TEST_VALIDATE_EXIT"
}
caddy() { printf 'unexpected root validation\\n' >&2; return 98; }
validate_caddy_config
''', check=False)
    assert result.returncode == exit_code
    assert "unexpected root validation" not in result.stderr


def test_auth_hash_passes_newline_to_caddy_and_accepts_eight_characters():
    result = bash_run('''
set -Eeuo pipefail
source "$1"
expected='ab$cd\\ef'
caddy() {
    [[ "$#" == 3 && "$1" == hash-password && "$2" == --algorithm && "$3" == argon2id ]] || return 2
    local received
    IFS= read -r received || { printf 'ERROR EOF\\n' >&2; return 1; }
    [[ "$received" == "$expected" ]] || return 3
    printf 'test-argon2id-hash\\n'
}
hash_basic_auth_password "$expected"
''')
    assert result.stdout.strip() == "test-argon2id-hash"
    assert "EOF" not in result.stderr


def test_auth_hash_rejects_short_password_before_calling_caddy():
    result = bash_run('''
source "$1"
caddy() { printf 'CADDY_WAS_CALLED\\n'; return 0; }
hash_basic_auth_password abcdefg
''', check=False)
    assert result.returncode != 0
    assert "至少需要 8 个字符" in result.stderr
    assert "CADDY_WAS_CALLED" not in result.stdout
    assert "abcdefg" not in result.stderr


@pytest.mark.parametrize("empty_output", [False, True])
def test_auth_hash_failure_never_returns_a_usable_password_hash(empty_output):
    with patch.dict(os.environ, {"TMS_TEST_HASH_EMPTY": str(int(empty_output))}):
        result = bash_run('''
source "$1"
caddy() {
    local password
    IFS= read -r password || return 2
    [[ "$TMS_TEST_HASH_EMPTY" == 1 ]] && return 0
    return 1
}
hash_basic_auth_password abcdefgh
''', check=False)
    assert result.returncode != 0
    assert result.stdout == ""
    assert "未保存该用户" in result.stderr
    assert "abcdefgh" not in result.stderr


def test_certificate_validator_rejects_untrusted_wrong_host_key_and_expiry():
    bash_run('''
set -Eeuo pipefail
source "$1"
work="$(mktemp -d)"
trap 'rm -f "$work/cert.pem" "$work/key.pem" "$work/other.key" "$work/short.pem"; rmdir "$work"' EXIT
openssl req -x509 -newkey rsa:2048 -nodes -days 3 \\
    -subj /CN=test.itnsa.cn -addext subjectAltName=DNS:test.itnsa.cn \\
    -keyout "$work/key.pem" -out "$work/cert.pem" >/dev/null 2>&1
if validate_certificate_pair "$work/cert.pem" "$work/key.pem"; then exit 10; fi
export SSL_CERT_FILE="$work/cert.pem"
if command -v cygpath >/dev/null; then export SSL_CERT_FILE="$(cygpath -m "$SSL_CERT_FILE")"; fi
validate_certificate_pair "$work/cert.pem" "$work/key.pem"
TMS_DOMAIN=wrong.itnsa.cn
if validate_certificate_pair "$work/cert.pem" "$work/key.pem"; then exit 11; fi
TMS_DOMAIN=test.itnsa.cn
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$work/other.key" >/dev/null 2>&1
if validate_certificate_pair "$work/cert.pem" "$work/other.key"; then exit 12; fi
openssl req -x509 -key "$work/key.pem" -days 1 -subj /CN=test.itnsa.cn \\
    -addext subjectAltName=DNS:test.itnsa.cn -out "$work/short.pem" >/dev/null 2>&1
if validate_certificate_pair "$work/short.pem" "$work/key.pem"; then exit 13; fi
''')


@pytest.mark.parametrize("target", ["python", "npm", "all"])
def test_dependency_dry_run_never_checks_out_or_executes_updates(target, capsys):
    with patch.object(updater, "run_command") as run, patch.object(updater, "require_development_checkout") as check:
        assert updater.main([target, "--dry-run"]) == 0
    run.assert_not_called()
    check.assert_not_called()
    output = capsys.readouterr().out
    assert "git diff --check" in output
    if target in {"python", "all"}:
        assert "uv lock --upgrade" in output
        assert "uv sync --locked" in output
    if target in {"npm", "all"}:
        assert "npm ci --include=dev" in output
        assert "npm run build:frontend" in output
        assert "npm run test:frontend" in output


def test_dependency_update_refuses_dirty_checkout_before_mutation(capsys):
    with patch.object(updater, "require_development_checkout", side_effect=RuntimeError("dirty")), \
            patch.object(updater, "run_command") as run:
        assert updater.main(["all"]) == 1
    run.assert_not_called()
    assert "dirty" in capsys.readouterr().err


def test_dependency_failure_stops_later_commands_and_keeps_changes():
    with patch.object(updater, "require_development_checkout"), \
            patch.object(updater.shutil, "which", return_value=sys.executable), \
            patch.object(updater, "run_command", side_effect=subprocess.CalledProcessError(1, "uv")) as run:
        assert updater.main(["python"]) == 1
    assert run.call_count == 1


def test_production_release_cannot_upgrade_dependencies():
    with patch.object(Path, "exists", return_value=True), pytest.raises(RuntimeError, match="开发 Git 工作区"):
        updater.require_development_checkout()
