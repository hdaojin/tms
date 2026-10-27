#!/usr/bin/env bash
# TMS production deployment entrypoint.
# Review this file, then install it root-owned as /usr/local/sbin/tms-deploy.

set -Eeuo pipefail
IFS=$'\n\t'
umask 027

readonly SCRIPT_VERSION="3"
readonly CONFIG_FILE="${TMS_DEPLOY_CONFIG:-/etc/tms/deploy.conf}"
readonly TEMPLATE_DIR="${TMS_DEPLOY_TEMPLATE_DIR:-/usr/local/share/tms-deploy}"
readonly ROOT_DIR="/srv/tms"
readonly REPOSITORY_DIR="${ROOT_DIR}/repository.git"
readonly RELEASES_DIR="${ROOT_DIR}/releases"
readonly CURRENT_LINK="${ROOT_DIR}/current"
readonly SHARED_DIR="${ROOT_DIR}/shared"
readonly PUBLIC_MEDIA_DIR="${SHARED_DIR}/media"
readonly PRIVATE_MEDIA_DIR="${SHARED_DIR}/media-private"
readonly STATE_DIR="/var/lib/tms"
readonly PLAN_DIR="${STATE_DIR}/deploy-plans"
readonly BACKUP_DIR="/var/backups/tms"
readonly ENV_DIR="/etc/tms"
readonly RUNTIME_ENV="${ENV_DIR}/tms.env"
readonly MIGRATE_ENV="${ENV_DIR}/migrate.env"
readonly AUTH_USERS_FILE="${ENV_DIR}/basic-auth.users"
readonly AUTH_SNIPPET="/etc/caddy/tms-basic-auth.caddy"
readonly CADDY_SITE="/etc/caddy/sites-enabled/tms.caddy"
readonly SYSTEMD_UNIT="/etc/systemd/system/tms.service"
readonly MAINTENANCE_FLAG="${STATE_DIR}/maintenance.flag"
readonly DEPLOY_STATE="${STATE_DIR}/current-deployment"
readonly UV_CACHE_DIR="/var/cache/tms/uv"
readonly SWAP_FILE="/swapfile"
readonly CERT_DIR="/etc/caddy/certs/tms"
readonly CERT_INCOMING="/var/lib/tms-acme/incoming"

TMS_DOMAIN="test.itnsa.cn"
TMS_GIT_URL="git@github.com:hdaojin/tms.git"
TMS_GIT_REVISION="develop"
TMS_DEPLOY_USER="ecs-user"
TMS_APP_USER="tms"
TMS_APP_GROUP="tms"
TMS_CADDY_USER="caddy"
TMS_CADDY_GROUP="caddy"
TMS_DB_NAME="tms"
TMS_DB_MIGRATOR="tms_migrator"
TMS_DB_APP="tms_app"
TMS_BIND="127.0.0.1:8010"
TMS_WORKERS="2"
TMS_SWAP_SIZE="2G"
TMS_BASIC_AUTH_TRUSTED_CIDRS=""
TMS_TLS_MODE="automatic"
TMS_ACME_USER="demo"
TMS_ACME_HOME="/home/demo/.acme.sh"
TMS_ACME_DOMAIN=""
TMS_ACME_ECC=1

JSON=0

heading() { printf '\n== %s ==\n' "$*"; }
info() { printf '[INFO] %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"; }
require_root() { [[ "${EUID}" -eq 0 ]] || die "该命令必须由 root 执行。"; }

require_root_owned_file() {
    local path="$1" owner mode
    [[ -f "${path}" ]] || die "缺少文件：${path}"
    owner="$(stat -c '%U' "${path}")"
    mode="$(stat -c '%a' "${path}")"
    [[ "${owner}" == "root" ]] || die "文件必须由 root 所有：${path}"
    (( (8#${mode} & 8#022) == 0 )) || die "文件不能被 group/other 写入：${path}"
}

usage() {
    cat <<'EOF'
用法：
  tms-deploy inspect [--json]
  tms-deploy plan [--revision REVISION] [--first-install] [--json]
  tms-deploy apply PLAN_ID --confirm-sha FULL_SHA
  tms-deploy verify [--json]
  tms-deploy status [--json]
  tms-deploy rollback --to RELEASE_ID
  tms-deploy auth add|remove|list [USERNAME]
  tms-deploy admin create
  tms-deploy prune [--keep NUMBER] [--yes]
  tms-deploy tls configure-acme|install|check

inspect 严格只读。plan 只写入候选 release 和带哈希的计划记录。
apply 与所有管理子命令都要求 root 权限。
EOF
}

validate_identifier() {
    [[ "$1" =~ ^[a-z_][a-z0-9_]*$ ]] || die "非法数据库标识符：$1"
}

validate_release_id() {
    [[ "$1" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$ ]] || die "非法 release id：$1"
}

validate_plan_id() {
    [[ "$1" =~ ^plan-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$ ]] || die "非法 plan id：$1"
}

safe_source_config() {
    [[ -f "${CONFIG_FILE}" ]] || return 0
    require_root_owned_file "${CONFIG_FILE}"
    # shellcheck disable=SC1090
    source "${CONFIG_FILE}"
    validate_identifier "${TMS_DB_NAME}"
    validate_identifier "${TMS_DB_MIGRATOR}"
    validate_identifier "${TMS_DB_APP}"
    [[ "${TMS_DOMAIN}" =~ ^[A-Za-z0-9.-]+$ ]] || die "非法域名：${TMS_DOMAIN}"
    [[ "${TMS_DEPLOY_USER}" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "非法部署用户名。"
    [[ "${TMS_APP_USER}" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "非法应用用户名。"
    [[ "${TMS_APP_GROUP}" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "非法应用组名。"
    [[ "${TMS_CADDY_USER}" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "非法 Caddy 用户名。"
    [[ "${TMS_CADDY_GROUP}" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "非法 Caddy 组名。"
    [[ "${TMS_BIND}" =~ ^127\.0\.0\.1:[0-9]{2,5}$ ]] || die "TMS_BIND 必须为 127.0.0.1:<port>。"
    [[ "${TMS_WORKERS}" =~ ^[1-9][0-9]*$ ]] || die "TMS_WORKERS 必须为正整数。"
    [[ "${TMS_SWAP_SIZE}" =~ ^[1-9][0-9]*[MG]$ ]] || die "TMS_SWAP_SIZE 必须为正整数加 M/G。"
    validate_tls_config
    TMS_BASIC_AUTH_TRUSTED_CIDRS="$(basic_auth_policy)" || die "可信认证网段配置无效。"
}

policy_python() { /usr/bin/python3.13 "$@"; }

basic_auth_policy() {
    # Normalize before inserting into Caddyfile; never interpolate raw config.
    policy_python - "${TMS_BASIC_AUTH_TRUSTED_CIDRS}" "${1:-}" <<'PY'
import ipaddress
import sys

try:
    networks = []
    for value in sys.argv[1].split():
        if '/' not in value:
            raise ValueError('请显式填写 CIDR 前缀，如 10.21.57.0/24')
        networks.append(ipaddress.ip_network(value, strict=True))
    if sys.argv[2]:
        address = ipaddress.ip_address(sys.argv[2])
        print(int(not any(address in network for network in networks)))
    else:
        print(' '.join(str(network) for network in networks))
except ValueError as exc:
    print(f'可信认证网段无效：{exc}', file=sys.stderr)
    sys.exit(1)
PY
}

validate_tls_config() {
    case "${TMS_TLS_MODE}" in
        automatic|acme-sh) ;;
        *) die "TMS_TLS_MODE 只能为 automatic 或 acme-sh。" ;;
    esac
    TMS_ACME_DOMAIN="${TMS_ACME_DOMAIN:-${TMS_DOMAIN}}"
    [[ "${TMS_ACME_DOMAIN}" =~ ^[A-Za-z0-9.-]+$ ]] || die "非法 acme.sh 主域名。"
    [[ "${TMS_ACME_USER}" =~ ^[a-z_][a-z0-9_-]*$ ]] || die "非法 acme.sh 用户名。"
    [[ "${TMS_ACME_HOME}" =~ ^/[A-Za-z0-9_./-]+$ && "${TMS_ACME_HOME}" != *'/../'* ]] || die "acme.sh home 必须为无空白的绝对路径。"
    [[ "${TMS_ACME_ECC}" == 0 || "${TMS_ACME_ECC}" == 1 ]] || die "TMS_ACME_ECC 必须为 0 或 1。"
}

render_caddy_site() {
    local tls_directive='# Caddy Automatic HTTPS' template="${1:-${TEMPLATE_DIR}/tms.caddy}"
    local auth_matcher='@tms_basic_auth path *' trusted_cidrs
    if [[ -n "${TMS_BASIC_AUTH_TRUSTED_CIDRS}" ]]; then
        trusted_cidrs="$(basic_auth_policy)" || return 1
        auth_matcher="@tms_basic_auth not remote_ip ${trusted_cidrs}"
    fi
    if [[ "${TMS_TLS_MODE}" == acme-sh ]]; then
        tls_directive="tls ${CERT_DIR}/current/fullchain.pem ${CERT_DIR}/current/privkey.pem"
    fi
    sed -e "s/@@DOMAIN@@/${TMS_DOMAIN}/g" -e "s/@@BIND@@/${TMS_BIND}/g" \
        -e "s|@@AUTH_MATCHER@@|${auth_matcher}|g" \
        -e "s|@@TLS_DIRECTIVE@@|${tls_directive}|g" "${template}"
}

validate_certificate_pair() {
    local fullchain="$1" key="$2" cert_public key_public
    openssl x509 -in "${fullchain}" -noout -checkhost "${TMS_DOMAIN}" >/dev/null || return 1
    openssl x509 -in "${fullchain}" -noout -checkend 86400 >/dev/null || return 1
    cert_public="$(openssl x509 -in "${fullchain}" -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum)" || return 1
    key_public="$(openssl pkey -in "${key}" -passin pass: -pubout -outform DER | sha256sum)" || return 1
    [[ "${cert_public}" == "${key_public}" ]] || return 1
    openssl verify -purpose sslserver -verify_hostname "${TMS_DOMAIN}" \
        -untrusted "${fullchain}" "${fullchain}" >/dev/null || return 1
}

check_external_certificate() {
    [[ "${TMS_TLS_MODE}" == acme-sh ]] || return 0
    require_cmd openssl
    validate_certificate_pair "${CERT_DIR}/current/fullchain.pem" "${CERT_DIR}/current/privkey.pem" || \
        die "外部证书的域名、信任链、密钥匹配或有效期校验失败（至少需剩余 24 小时）。"
    runuser -u "${TMS_CADDY_USER}" -- test -r "${CERT_DIR}/current/privkey.pem" || die "Caddy 无法读取外部证书私钥。"
}

install_acme_certificate() {
    require_cmd flock
    install -d -m 0750 -o root -g "${TMS_CADDY_GROUP}" /etc/caddy/certs "${CERT_DIR}"
    # acme.sh finishes writing both staging files before invoking this hook.
    local stage previous='' failed=0
    exec 8>"${CERT_DIR}/install.lock"
    flock -x 8
    [[ -f "${CERT_INCOMING}/fullchain.pem" && ! -L "${CERT_INCOMING}/fullchain.pem" && \
       -f "${CERT_INCOMING}/privkey.pem" && ! -L "${CERT_INCOMING}/privkey.pem" ]] || die "acme.sh 暂存证书缺失或为软链接。"
    stage="$(mktemp -d "${CERT_DIR}/cert-XXXXXXXX")"
    chmod 0750 "${stage}"; chown root:"${TMS_CADDY_GROUP}" "${stage}"
    install -m 0640 -o root -g "${TMS_CADDY_GROUP}" "${CERT_INCOMING}/fullchain.pem" "${stage}/fullchain.pem"
    install -m 0640 -o root -g "${TMS_CADDY_GROUP}" "${CERT_INCOMING}/privkey.pem" "${stage}/privkey.pem"
    if ! validate_certificate_pair "${stage}/fullchain.pem" "${stage}/privkey.pem"; then
        rm -f "${stage}/fullchain.pem" "${stage}/privkey.pem"; rmdir "${stage}"
        die "拒绝安装无效证书，原证书保持不变。"
    fi
    [[ ! -e "${CERT_DIR}/current" || -L "${CERT_DIR}/current" ]] || die "证书 current 路径冲突。"
    [[ ! -L "${CERT_DIR}/current" ]] || previous="$(readlink "${CERT_DIR}/current")"
    ln -sfn "${stage}" "${CERT_DIR}/current.new"
    mv -Tf "${CERT_DIR}/current.new" "${CERT_DIR}/current"
    if [[ -f "${CADDY_SITE}" ]]; then
        caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile || failed=1
        if (( failed == 0 )); then
            runuser -u "${TMS_CADDY_USER}" -- test -r "${CERT_DIR}/current/privkey.pem" || failed=1
        fi
        if (( failed == 0 )) && systemctl is-active --quiet caddy; then
            caddy reload --force --config /etc/caddy/Caddyfile --adapter caddyfile || failed=1
        fi
    fi
    if (( failed )); then
        if [[ -n "${previous}" ]]; then
            ln -sfn "${previous}" "${CERT_DIR}/current.new"
            mv -Tf "${CERT_DIR}/current.new" "${CERT_DIR}/current"
        else
            rm -f "${CERT_DIR}/current"
        fi
        die "证书安装后的 Caddy 校验或 reload 失败，已恢复原证书链接；请检查 Caddy 日志。"
    fi
    info "证书已安装；续期版本保留于 ${stage}。"
}

configure_acme_install() {
    [[ "$(realpath "$0")" == /usr/local/sbin/tms-deploy ]] || die "请先安装稳定入口 /usr/local/sbin/tms-deploy。"
    require_cmd visudo
    id "${TMS_ACME_USER}" >/dev/null 2>&1 || die "acme.sh 用户不存在。"
    [[ -f "${TMS_ACME_HOME}/acme.sh" ]] || die "请先按手册安装 acme.sh 并通过 DNS-01 签发证书。"
    install -d -m 0755 -o root -g root /var/lib/tms-acme
    install -d -m 0700 -o "${TMS_ACME_USER}" -g "$(id -gn "${TMS_ACME_USER}")" "${CERT_INCOMING}"
    local sudoers ecc_args=()
    sudoers="$(mktemp)"
    printf '%s ALL=(root) NOPASSWD: /usr/local/sbin/tms-deploy tls install\n' "${TMS_ACME_USER}" >"${sudoers}"
    chmod 0440 "${sudoers}"
    if ! visudo -cf "${sudoers}"; then rm -f "${sudoers}"; die "证书安装 hook 的 sudoers 校验失败。"; fi
    install -m 0440 -o root -g root "${sudoers}" /etc/sudoers.d/tms-acme-install
    rm -f "${sudoers}"
    [[ "${TMS_ACME_ECC}" == 0 ]] || ecc_args=(--ecc)
    runuser -u "${TMS_ACME_USER}" -- "${TMS_ACME_HOME}/acme.sh" \
        --home "${TMS_ACME_HOME}" --install-cert -d "${TMS_ACME_DOMAIN}" "${ecc_args[@]}" \
        --key-file "${CERT_INCOMING}/privkey.pem" --fullchain-file "${CERT_INCOMING}/fullchain.pem" \
        --reloadcmd 'sudo -n /usr/local/sbin/tms-deploy tls install'
    check_external_certificate
}

cmd_tls() {
    require_root
    require_root_owned_file "$0"
    safe_source_config
    [[ $# -eq 1 ]] || die "用法：tms-deploy tls configure-acme|install|check"
    [[ "${TMS_TLS_MODE}" == acme-sh ]] || die "该命令仅适用于 TMS_TLS_MODE=acme-sh。"
    case "$1" in
        configure-acme) configure_acme_install ;;
        install) install_acme_certificate ;;
        check) check_external_certificate; info "外部证书校验通过。" ;;
        *) die "未知 tls 动作：$1" ;;
    esac
}

ssh_git_env() {
    printf '%s' 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10'
}

run_as_deployer() {
    runuser -u "${TMS_DEPLOY_USER}" -- env \
        GIT_SSH_COMMAND="$(ssh_git_env)" UV_CACHE_DIR="${UV_CACHE_DIR}" "$@"
}

run_as_app() {
    runuser -u "${TMS_APP_USER}" -- "$@"
}

env_run_as() {
    local user="$1" env_file="$2"
    shift 2
    local env_args=() line
    while IFS= read -r line || [[ -n "${line}" ]]; do
        [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
        [[ "${line}" =~ ^[A-Za-z_][A-Za-z0-9_]*=.*$ ]] || die "环境文件包含无效行：${env_file}"
        env_args+=("${line}")
    done <"${env_file}"
    runuser -u "${user}" -- env --ignore-environment \
        PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
        HOME="/var/lib/tms" LANG="C.UTF-8" \
        "${env_args[@]}" "$@"
}

env_run_as_app() {
    local env_file="$1"
    shift
    env_run_as "${TMS_APP_USER}" "${env_file}" "$@"
}

require_installed_layout() {
    require_root_owned_file "$0"
    require_root_owned_file "${TEMPLATE_DIR}/tms.service"
    require_root_owned_file "${TEMPLATE_DIR}/tms.caddy"
    require_root_owned_file "${CONFIG_FILE}"
}

json_bool() { [[ "$1" == "yes" ]] && printf true || printf false; }

cmd_inspect() {
    while (($#)); do case "$1" in --json) JSON=1; shift ;; *) die "未知参数：$1" ;; esac; done
    local swap="no" service="absent" current="none" postgres="unknown" caddy="unknown"
    local free_kib=0 disk_target="${ROOT_DIR}"
    [[ -n "$(swapon --noheadings 2>/dev/null || true)" ]] && swap="yes"
    [[ -L "${CURRENT_LINK}" ]] && current="$(readlink -f "${CURRENT_LINK}")"
    if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet tms.service 2>/dev/null; then
        service="active"
    elif [[ -f "${SYSTEMD_UNIT}" ]]; then
        service="inactive"
    fi
    command -v psql >/dev/null 2>&1 && postgres="$(psql --version | head -n 1)"
    command -v caddy >/dev/null 2>&1 && caddy="$(caddy version 2>/dev/null | head -n 1)"
    [[ -e "${disk_target}" ]] || disk_target="/srv"
    [[ -d "${disk_target}" ]] || disk_target="/"
    free_kib="$(df -Pk "${disk_target}" 2>/dev/null | awk 'NR==2 {print $4}' || true)"
    free_kib="${free_kib:-0}"

    if (( JSON )); then
        printf '{"version":"%s","swap":%s,"service":"%s","current":"%s","free_kib":%s,"postgres":"%s","caddy":"%s"}\n' \
            "${SCRIPT_VERSION}" "$(json_bool "${swap}")" "${service}" "${current}" "${free_kib}" "${postgres}" "${caddy}"
        return
    fi
    heading "TMS_INSPECT（只读）"
    printf 'script_version=%s\n' "${SCRIPT_VERSION}"
    printf 'os=%s\n' "$(. /etc/os-release 2>/dev/null && printf '%s %s' "${NAME:-unknown}" "${VERSION_ID:-unknown}")"
    printf 'kernel=%s\n' "$(uname -sr)"
    printf 'cpu_count=%s\n' "$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf unknown)"
    printf 'memory=%s\n' "$(awk '/MemTotal/ {print $2 " KiB"}' /proc/meminfo)"
    printf 'swap=%s\n' "${swap}"
    printf 'root_free_kib=%s\n' "${free_kib}"
    printf 'python=%s\n' "$(python3.13 --version 2>/dev/null || printf missing)"
    printf 'uv=%s\n' "$(uv --version 2>/dev/null || printf missing)"
    printf 'postgres=%s\n' "${postgres}"
    printf 'caddy=%s\n' "${caddy}"
    printf 'service=%s\n' "${service}"
    printf 'current=%s\n' "${current}"
    printf 'config=%s\n' "$([[ -f "${CONFIG_FILE}" ]] && printf present || printf absent)"
    printf 'runtime_env=%s\n' "$([[ -f "${RUNTIME_ENV}" ]] && printf present || printf absent)"
    printf 'migrate_env=%s\n' "$([[ -f "${MIGRATE_ENV}" ]] && printf present || printf absent)"
    printf 'basic_auth=%s\n' "$([[ -s "${AUTH_USERS_FILE}" ]] && printf configured || printf missing)"
    printf 'postgres_listen=%s\n' "$(ss -ltn 2>/dev/null | awk '$4 ~ /:5432$/ {print $4}' | paste -sd, - || true)"
    printf 'gunicorn_listen=%s\n' "$(ss -ltn 2>/dev/null | awk '$4 ~ /:8010$/ {print $4}' | paste -sd, - || true)"
}

ensure_plan_prerequisites() {
    require_root
    require_installed_layout
    for cmd in git tar uv sha256sum runuser install df awk sed stat; do require_cmd "${cmd}"; done
    id "${TMS_DEPLOY_USER}" >/dev/null 2>&1 || die "部署用户不存在：${TMS_DEPLOY_USER}"
    getent group "${TMS_CADDY_GROUP}" >/dev/null 2>&1 || die "Caddy 组不存在：${TMS_CADDY_GROUP}"
    [[ -x /usr/bin/python3.13 ]] || die "缺少 /usr/bin/python3.13"
    install -d -m 0755 -o root -g root "${ROOT_DIR}" "${RELEASES_DIR}" "${STATE_DIR}"
    install -d -m 0700 -o root -g root "${PLAN_DIR}"
    install -d -m 0750 -o "${TMS_DEPLOY_USER}" -g "${TMS_DEPLOY_USER}" "${UV_CACHE_DIR}"
}

secure_release_permissions() {
    local release_dir="$1" code_group="root"
    getent group "${TMS_APP_GROUP}" >/dev/null 2>&1 && code_group="${TMS_APP_GROUP}"
    chown -R root:"${code_group}" "${release_dir}"
    chmod -R u=rwX,g=rX,o= "${release_dir}"
    chmod 0751 "${release_dir}"
    if [[ -d "${release_dir}/staticfiles" ]]; then
        chown -R root:"${TMS_CADDY_GROUP}" "${release_dir}/staticfiles"
        find "${release_dir}/staticfiles" -type d -exec chmod 0750 {} +
        find "${release_dir}/staticfiles" -type f -exec chmod 0640 {} +
    fi
}

prepare_repository() {
    if [[ ! -d "${REPOSITORY_DIR}" ]]; then
        install -d -m 0750 -o "${TMS_DEPLOY_USER}" -g "${TMS_DEPLOY_USER}" "${REPOSITORY_DIR}"
        run_as_deployer git init --bare "${REPOSITORY_DIR}" >/dev/null
        run_as_deployer git --git-dir="${REPOSITORY_DIR}" remote add origin "${TMS_GIT_URL}"
    fi
    [[ "$(stat -c '%U' "${REPOSITORY_DIR}")" == "${TMS_DEPLOY_USER}" ]] || die "裸仓库所有者异常。"
    local remote_url
    remote_url="$(run_as_deployer git --git-dir="${REPOSITORY_DIR}" remote get-url origin)"
    [[ "${remote_url}" == "${TMS_GIT_URL}" ]] || die "origin 与配置不一致：${remote_url}"
    run_as_deployer git --git-dir="${REPOSITORY_DIR}" fetch --prune origin \
        '+refs/heads/*:refs/remotes/origin/*' '+refs/tags/*:refs/tags/*'
}

resolve_revision() {
    local revision="$1"
    if [[ "${revision}" =~ ^[0-9a-f]{40}$ ]]; then
        run_as_deployer git --git-dir="${REPOSITORY_DIR}" rev-parse --verify "${revision}^{commit}"
    elif run_as_deployer git --git-dir="${REPOSITORY_DIR}" show-ref --verify --quiet "refs/remotes/origin/${revision}"; then
        run_as_deployer git --git-dir="${REPOSITORY_DIR}" rev-parse "refs/remotes/origin/${revision}^{commit}"
    else
        run_as_deployer git --git-dir="${REPOSITORY_DIR}" rev-parse --verify "${revision}^{commit}"
    fi
}

candidate_django() {
    local release_dir="$1"
    shift
    if [[ -f "${RUNTIME_ENV}" ]]; then
        env_run_as "${TMS_DEPLOY_USER}" "${RUNTIME_ENV}" \
            "${release_dir}/.venv/bin/python" "${release_dir}/manage.py" "$@"
    else
        runuser -u "${TMS_DEPLOY_USER}" -- env \
            DEBUG=False SECRET_KEY='plan-only-strong-placeholder-key-0123456789' \
            ALLOWED_HOSTS="${TMS_DOMAIN},127.0.0.1" \
            CSRF_TRUSTED_ORIGINS="https://${TMS_DOMAIN}" \
            DATABASE_URL='sqlite:///:memory:' \
            MEDIA_ROOT="${PUBLIC_MEDIA_DIR}" PRIVATE_MEDIA_ROOT="${PRIVATE_MEDIA_DIR}" \
            "${release_dir}/.venv/bin/python" "${release_dir}/manage.py" "$@"
    fi
}

cmd_plan() {
    local revision='' first_install=0
    while (($#)); do
        case "$1" in
            --revision) [[ $# -ge 2 ]] || die "--revision 缺少值"; revision="$2"; shift 2 ;;
            --first-install) first_install=1; shift ;;
            --json) JSON=1; shift ;;
            *) die "未知参数：$1" ;;
        esac
    done
    if (( JSON )); then
        exec 3>&1
        exec 1>&2
    fi
    require_root
    safe_source_config
    revision="${revision:-${TMS_GIT_REVISION}}"
    ensure_plan_prerequisites
    check_external_certificate
    prepare_repository

    local sha timestamp release_id release_dir plan_id manifest manifest_hash free_kib required_kib
    sha="$(resolve_revision "${revision}")"
    [[ "${sha}" =~ ^[0-9a-f]{40}$ ]] || die "无法固定完整提交 SHA。"
    timestamp="$(date -u '+%Y%m%dT%H%M%SZ')"
    release_id="${timestamp}-${sha:0:12}"
    release_dir="${RELEASES_DIR}/${release_id}"
    plan_id="plan-${release_id}"
    [[ ! -e "${release_dir}" ]] || die "候选 release 已存在：${release_dir}"

    free_kib="$(df -Pk "${ROOT_DIR}" | awk 'NR==2 {print $4}')"
    required_kib=2097152
    (( free_kib >= required_kib )) || die "磁盘空间不足：至少需要 2 GiB 可用空间。"

    heading "PREPARE CANDIDATE ${release_id}"
    install -d -m 0750 -o "${TMS_DEPLOY_USER}" -g "${TMS_DEPLOY_USER}" "${release_dir}"
    run_as_deployer bash -c 'set -Eeuo pipefail; git --git-dir="$1" archive "$2" | tar -x -C "$3"' \
        bash "${REPOSITORY_DIR}" "${sha}" "${release_dir}"
    printf '%s\n' "${sha}" >"${release_dir}/.tms-release-sha"
    chown "${TMS_DEPLOY_USER}:${TMS_DEPLOY_USER}" "${release_dir}/.tms-release-sha"

    run_as_deployer bash -c 'cd "$1" && uv sync --locked --no-dev --python /usr/bin/python3.13' bash "${release_dir}"
    [[ -s "${release_dir}/static/css/output.css" ]] || die "仓库缺少已构建的 static/css/output.css"
    [[ -d "${release_dir}/static/vendor" ]] || die "仓库缺少已提交的 static/vendor"
    candidate_django "${release_dir}" check
    candidate_django "${release_dir}" check --deploy | tee "${release_dir}/.tms-check-deploy.txt"
    candidate_django "${release_dir}" makemigrations --check --dry-run
    candidate_django "${release_dir}" migrate --plan | tee "${release_dir}/.tms-migration-plan.txt"
    candidate_django "${release_dir}" collectstatic --noinput --clear

    secure_release_permissions "${release_dir}"

    manifest="${PLAN_DIR}/${plan_id}.manifest"
    {
        printf 'PLAN_VERSION=%q\n' "${SCRIPT_VERSION}"
        printf 'PLAN_ID=%q\n' "${plan_id}"
        printf 'RELEASE_ID=%q\n' "${release_id}"
        printf 'RELEASE_DIR=%q\n' "${release_dir}"
        printf 'REVISION=%q\n' "${revision}"
        printf 'SHA=%q\n' "${sha}"
        printf 'FIRST_INSTALL=%q\n' "${first_install}"
        printf 'TLS_MODE=%q\n' "${TMS_TLS_MODE}"
        printf 'BASIC_AUTH_TRUSTED_CIDRS=%q\n' "${TMS_BASIC_AUTH_TRUSTED_CIDRS}"
        printf 'CREATED_AT=%q\n' "$(date -u '+%FT%TZ')"
        printf 'SCRIPT_SHA256=%q\n' "$(sha256sum "$0" | awk '{print $1}')"
        printf 'CONFIG_SHA256=%q\n' "$(sha256sum "${CONFIG_FILE}" | awk '{print $1}')"
        printf 'SERVICE_TEMPLATE_SHA256=%q\n' "$(sha256sum "${TEMPLATE_DIR}/tms.service" | awk '{print $1}')"
        printf 'CADDY_TEMPLATE_SHA256=%q\n' "$(sha256sum "${TEMPLATE_DIR}/tms.caddy" | awk '{print $1}')"
    } >"${manifest}"
    chmod 0600 "${manifest}"
    sha256sum "${manifest}" >"${manifest}.sha256"
    chmod 0600 "${manifest}.sha256"
    manifest_hash="$(awk '{print $1}' "${manifest}.sha256")"

    if (( JSON )); then
        printf '{"plan_id":"%s","release_id":"%s","sha":"%s","first_install":%s,"manifest_sha256":"%s","tls_mode":"%s","basic_auth_trusted_cidrs":"%s"}\n' \
            "${plan_id}" "${release_id}" "${sha}" "$([[ ${first_install} -eq 1 ]] && printf true || printf false)" "${manifest_hash}" "${TMS_TLS_MODE}" "${TMS_BASIC_AUTH_TRUSTED_CIDRS}" >&3
    else
        heading "TMS_PLAN_READY"
        printf 'plan_id=%s\nrelease_id=%s\nsha=%s\nfirst_install=%s\nmanifest_sha256=%s\n' \
            "${plan_id}" "${release_id}" "${sha}" "${first_install}" "${manifest_hash}"
        printf 'tls_mode=%s\n' "${TMS_TLS_MODE}"
        printf 'basic_auth_trusted_cidrs=%s\n' "${TMS_BASIC_AUTH_TRUSTED_CIDRS}"
        printf '下一步：再次人工确认后执行 tms-deploy apply %s --confirm-sha %s\n' "${plan_id}" "${sha}"
    fi
}

load_plan() {
    local plan_id="$1" manifest
    manifest="${PLAN_DIR}/${plan_id}.manifest"
    validate_plan_id "${plan_id}"
    [[ -f "${manifest}" && -f "${manifest}.sha256" ]] || die "计划不存在：${plan_id}"
    [[ "$(stat -c '%U:%a' "${manifest}")" == "root:600" ]] || die "计划文件权限异常。"
    (cd "${PLAN_DIR}" && sha256sum -c "${plan_id}.manifest.sha256" >/dev/null) || die "计划哈希校验失败。"
    # The manifest is generated by this root-owned script and checked above.
    # shellcheck disable=SC1090
    source "${manifest}"
    [[ "${PLAN_ID}" == "${plan_id}" ]] || die "计划 ID 不匹配。"
    validate_release_id "${RELEASE_ID}"
    [[ "${RELEASE_DIR}" == "${RELEASES_DIR}/${RELEASE_ID}" ]] || die "候选路径越界。"
    [[ -d "${RELEASE_DIR}" ]] || die "候选 release 不存在。"
    [[ "$(<"${RELEASE_DIR}/.tms-release-sha")" == "${SHA}" ]] || die "候选 SHA 标记不匹配。"
    [[ "$(sha256sum "$0" | awk '{print $1}')" == "${SCRIPT_SHA256}" ]] || die "部署入口自 plan 后已变化，请重新 plan。"
    [[ "$(sha256sum "${CONFIG_FILE}" | awk '{print $1}')" == "${CONFIG_SHA256}" ]] || die "部署配置自 plan 后已变化，请重新 plan。"
    [[ "$(sha256sum "${TEMPLATE_DIR}/tms.service" | awk '{print $1}')" == "${SERVICE_TEMPLATE_SHA256}" ]] || die "systemd 模板已变化，请重新 plan。"
    [[ "$(sha256sum "${TEMPLATE_DIR}/tms.caddy" | awk '{print $1}')" == "${CADDY_TEMPLATE_SHA256}" ]] || die "Caddy 模板已变化，请重新 plan。"
}

ensure_swap() {
    [[ -z "$(swapon --noheadings 2>/dev/null || true)" ]] || { info "系统已有 swap，保持不变。"; return; }
    [[ ! -e "${SWAP_FILE}" ]] || die "${SWAP_FILE} 已存在但未启用；拒绝覆盖。"
    findmnt --verify --tab-file /etc/fstab >/dev/null || die "/etc/fstab 校验失败。"
    require_cmd fallocate; require_cmd mkswap; require_cmd swapon; require_cmd swapoff
    local fstab_backup
    fstab_backup="$(mktemp /etc/fstab.tms-deploy.XXXXXX)"
    cp -a /etc/fstab "${fstab_backup}"
    if ! fallocate -l "${TMS_SWAP_SIZE}" "${SWAP_FILE}" || \
       ! chmod 0600 "${SWAP_FILE}" || \
       ! mkswap "${SWAP_FILE}" >/dev/null || \
       ! swapon "${SWAP_FILE}"; then
        rm -f "${SWAP_FILE}"
        rm -f "${fstab_backup}"
        die "创建 swap 失败，已清理本次创建的文件。"
    fi
    printf '%s\n' '/swapfile none swap sw 0 0' >>/etc/fstab
    if ! findmnt --verify --tab-file /etc/fstab >/dev/null; then
        cp -a "${fstab_backup}" /etc/fstab
        swapoff "${SWAP_FILE}" || true
        rm -f "${SWAP_FILE}" "${fstab_backup}"
        die "写入 swap 后 /etc/fstab 校验失败，已恢复原配置。"
    fi
    rm -f "${fstab_backup}"
}

ensure_accounts_and_dirs() {
    getent passwd "${TMS_APP_USER}" >/dev/null || \
        useradd --system --home-dir "${STATE_DIR}" --shell /usr/sbin/nologin --user-group "${TMS_APP_USER}"
    id "${TMS_CADDY_USER}" >/dev/null 2>&1 || die "Caddy 用户不存在：${TMS_CADDY_USER}"
    install -d -m 0755 -o root -g root "${ROOT_DIR}" "${RELEASES_DIR}" "${SHARED_DIR}" "${STATE_DIR}"
    install -d -m 2750 -o "${TMS_APP_USER}" -g "${TMS_CADDY_GROUP}" "${PUBLIC_MEDIA_DIR}"
    install -d -m 0750 -o "${TMS_APP_USER}" -g "${TMS_APP_GROUP}" "${PRIVATE_MEDIA_DIR}"
    install -d -m 0700 -o root -g root "${BACKUP_DIR}" "${ENV_DIR}" "${PLAN_DIR}"
    chown -R "${TMS_APP_USER}:${TMS_CADDY_GROUP}" "${PUBLIC_MEDIA_DIR}"
    find "${PUBLIC_MEDIA_DIR}" -type d -exec chmod 2750 {} +
    find "${PUBLIC_MEDIA_DIR}" -type f -exec chmod 0640 {} +
    chown -R "${TMS_APP_USER}:${TMS_APP_GROUP}" "${PRIVATE_MEDIA_DIR}"
    find "${PRIVATE_MEDIA_DIR}" -type d -exec chmod 0750 {} +
    find "${PRIVATE_MEDIA_DIR}" -type f -exec chmod 0640 {} +
}

write_secret_files_and_database() {
    require_cmd openssl; require_cmd psql
    local app_password migrator_password secret_key existing_roles existing_database
    if [[ -f "${RUNTIME_ENV}" && -f "${MIGRATE_ENV}" ]]; then
        existing_roles="$(runuser -u postgres -- psql --tuples-only --no-align \
            --set=ON_ERROR_STOP=1 \
            --command="SELECT count(*) FROM pg_roles WHERE rolname IN ('${TMS_DB_MIGRATOR}', '${TMS_DB_APP}')")" || \
            die "无法检查首次安装恢复点。"
        existing_database="$(runuser -u postgres -- psql --tuples-only --no-align \
            --set=ON_ERROR_STOP=1 \
            --command="SELECT count(*) FROM pg_database WHERE datname='${TMS_DB_NAME}'")" || \
            die "无法检查首次安装恢复点。"
        if [[ "${existing_roles}" == "2" && "${existing_database}" == "1" && \
              "$(stat -c '%U:%G:%a' "${RUNTIME_ENV}")" == "root:${TMS_APP_GROUP}:640" && \
              "$(stat -c '%U:%G:%a' "${MIGRATE_ENV}")" == "root:root:600" ]]; then
            info "检测到完整的首次安装秘密和数据库对象，复用它们继续未完成的 apply。"
            return
        fi
        die "检测到不完整的首次安装状态；拒绝覆盖秘密或数据库，请按手册人工核对。"
    fi
    [[ ! -e "${RUNTIME_ENV}" && ! -e "${MIGRATE_ENV}" ]] || die "只存在一个环境文件；拒绝覆盖不完整状态。"
    existing_roles="$(runuser -u postgres -- psql --tuples-only --no-align \
        --set=ON_ERROR_STOP=1 \
        --command="SELECT 1 FROM pg_roles WHERE rolname IN ('${TMS_DB_MIGRATOR}', '${TMS_DB_APP}') LIMIT 1")" || \
        die "无法预检 PostgreSQL 角色。"
    [[ -z "${existing_roles}" ]] || die "目标 PostgreSQL 角色已存在；拒绝覆盖。"
    existing_database="$(runuser -u postgres -- psql --tuples-only --no-align \
        --set=ON_ERROR_STOP=1 \
        --command="SELECT 1 FROM pg_database WHERE datname='${TMS_DB_NAME}'")" || \
        die "无法预检 PostgreSQL 数据库。"
    [[ -z "${existing_database}" ]] || die "目标 PostgreSQL 数据库已存在；拒绝覆盖。"
    app_password="$(openssl rand -hex 32)"
    migrator_password="$(openssl rand -hex 32)"
    secret_key="$(openssl rand -hex 48)"

    install -m 0640 -o root -g "${TMS_APP_GROUP}" /dev/null "${RUNTIME_ENV}"
    {
        printf 'DEBUG=False\nSECRET_KEY=%s\n' "${secret_key}"
        printf 'ALLOWED_HOSTS=%s,127.0.0.1\n' "${TMS_DOMAIN}"
        printf 'CSRF_TRUSTED_ORIGINS=https://%s\n' "${TMS_DOMAIN}"
        printf 'DATABASE_URL=postgres://%s:%s@127.0.0.1:5432/%s\n' "${TMS_DB_APP}" "${app_password}" "${TMS_DB_NAME}"
        printf 'MEDIA_ROOT=%s\nPRIVATE_MEDIA_ROOT=%s\nNOTES_ROOT=%s/notes\n' "${PUBLIC_MEDIA_DIR}" "${PRIVATE_MEDIA_DIR}" "${PRIVATE_MEDIA_DIR}"
        printf 'TRUST_X_FORWARDED_PROTO=True\nSECURE_SSL_REDIRECT=True\nSESSION_COOKIE_SECURE=True\nCSRF_COOKIE_SECURE=True\n'
        printf 'SECURE_HSTS_SECONDS=3600\nSECURE_HSTS_INCLUDE_SUBDOMAINS=False\nSECURE_HSTS_PRELOAD=False\n'
        printf 'SAMBA_INTEGRATION_ENABLED=False\nSAMBA_ASYNC_OPERATIONS_ENABLED=False\n'
    } >"${RUNTIME_ENV}"
    chown root:"${TMS_APP_GROUP}" "${RUNTIME_ENV}"; chmod 0640 "${RUNTIME_ENV}"

    install -m 0600 -o root -g root /dev/null "${MIGRATE_ENV}"
    sed "s#postgres://${TMS_DB_APP}:${app_password}@#postgres://${TMS_DB_MIGRATOR}:${migrator_password}@#" \
        "${RUNTIME_ENV}" >"${MIGRATE_ENV}"
    chown root:root "${MIGRATE_ENV}"; chmod 0600 "${MIGRATE_ENV}"

    runuser -u postgres -- psql --set=ON_ERROR_STOP=1 <<SQL
CREATE ROLE ${TMS_DB_MIGRATOR} LOGIN PASSWORD '${migrator_password}';
CREATE ROLE ${TMS_DB_APP} LOGIN PASSWORD '${app_password}';
CREATE DATABASE ${TMS_DB_NAME} OWNER ${TMS_DB_MIGRATOR};
REVOKE ALL ON DATABASE ${TMS_DB_NAME} FROM PUBLIC;
GRANT CONNECT ON DATABASE ${TMS_DB_NAME} TO ${TMS_DB_APP};
SQL
    runuser -u postgres -- psql --set=ON_ERROR_STOP=1 --dbname="${TMS_DB_NAME}" <<SQL
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO ${TMS_DB_MIGRATOR};
GRANT USAGE ON SCHEMA public TO ${TMS_DB_APP};
ALTER DEFAULT PRIVILEGES FOR ROLE ${TMS_DB_MIGRATOR} IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${TMS_DB_APP};
ALTER DEFAULT PRIVILEGES FOR ROLE ${TMS_DB_MIGRATOR} IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ${TMS_DB_APP};
SQL
}

grant_runtime_database_permissions() {
    runuser -u postgres -- psql --set=ON_ERROR_STOP=1 --dbname="${TMS_DB_NAME}" <<SQL
GRANT USAGE ON SCHEMA public TO ${TMS_DB_APP};
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ${TMS_DB_APP};
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO ${TMS_DB_APP};
ALTER DEFAULT PRIVILEGES FOR ROLE ${TMS_DB_MIGRATOR} IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${TMS_DB_APP};
ALTER DEFAULT PRIVILEGES FOR ROLE ${TMS_DB_MIGRATOR} IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO ${TMS_DB_APP};
SQL
}

render_auth_snippet() {
    install -m 0640 -o root -g "${TMS_CADDY_GROUP}" /dev/null "${AUTH_SNIPPET}"
    {
        printf 'basic_auth @tms_basic_auth argon2id {\n'
        if [[ -f "${AUTH_USERS_FILE}" ]]; then
            while IFS=: read -r username password_hash; do
                [[ -n "${username}" && -n "${password_hash}" ]] || continue
                printf '\t%s %s\n' "${username}" "${password_hash}"
            done <"${AUTH_USERS_FILE}"
        fi
        printf '}\n'
    } >"${AUTH_SNIPPET}"
    chown root:"${TMS_CADDY_GROUP}" "${AUTH_SNIPPET}"; chmod 0640 "${AUTH_SNIPPET}"
}

install_service_and_caddy() {
    [[ -s "${AUTH_USERS_FILE}" ]] || die "尚未配置 Basic Auth；先执行 tms-deploy auth add USERNAME。"
    [[ -f /etc/caddy/Caddyfile ]] || die "缺少 /etc/caddy/Caddyfile"
    local verify_unit unit_backup site_backup main_backup
    local unit_existed=0 site_existed=0 validation_failed=0
    unit_backup="$(mktemp)"
    site_backup="$(mktemp)"
    main_backup="$(mktemp)"
    if [[ -f "${SYSTEMD_UNIT}" ]]; then
        cp --preserve=all "${SYSTEMD_UNIT}" "${unit_backup}"
        unit_existed=1
    fi
    if [[ -f "${CADDY_SITE}" ]]; then
        cp --preserve=all "${CADDY_SITE}" "${site_backup}"
        site_existed=1
    fi
    cp --preserve=all /etc/caddy/Caddyfile "${main_backup}"

    sed -e "s/@@APP_USER@@/${TMS_APP_USER}/g" \
        -e "s/@@APP_GROUP@@/${TMS_APP_GROUP}/g" \
        -e "s/@@BIND@@/${TMS_BIND}/g" \
        -e "s/@@WORKERS@@/${TMS_WORKERS}/g" \
        "${TEMPLATE_DIR}/tms.service" >"${SYSTEMD_UNIT}"
    chown root:root "${SYSTEMD_UNIT}"; chmod 0644 "${SYSTEMD_UNIT}"
    install -d -m 0755 -o root -g root /etc/caddy/sites-enabled
    render_caddy_site >"${CADDY_SITE}"
    chown root:root "${CADDY_SITE}"; chmod 0644 "${CADDY_SITE}"
    render_auth_snippet
    if ! grep -Fqx 'import /etc/caddy/sites-enabled/*' /etc/caddy/Caddyfile; then
        cp -a /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.before-tms.$(date -u '+%Y%m%dT%H%M%SZ')"
        printf '\n%s\n' 'import /etc/caddy/sites-enabled/*' >>/etc/caddy/Caddyfile
    fi
    verify_unit="$(mktemp --suffix=.service)"
    sed "s#/srv/tms/current#${RELEASE_DIR}#g" "${SYSTEMD_UNIT}" >"${verify_unit}"
    systemd-analyze verify "${verify_unit}" || validation_failed=1
    rm -f "${verify_unit}"
    if (( validation_failed == 0 )); then
        caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile || validation_failed=1
    fi
    if (( validation_failed != 0 )); then
        if (( unit_existed )); then cp --preserve=all "${unit_backup}" "${SYSTEMD_UNIT}"; else rm -f "${SYSTEMD_UNIT}"; fi
        if (( site_existed )); then cp --preserve=all "${site_backup}" "${CADDY_SITE}"; else rm -f "${CADDY_SITE}"; fi
        cp --preserve=all "${main_backup}" /etc/caddy/Caddyfile
        rm -f "${unit_backup}" "${site_backup}" "${main_backup}"
        die "systemd 或 Caddy 配置校验失败；已恢复磁盘上的原配置。"
    fi
    rm -f "${unit_backup}" "${site_backup}" "${main_backup}"
    systemctl daemon-reload
    systemctl enable tms.service >/dev/null
    if systemctl is-active --quiet caddy; then
        systemctl reload caddy
    else
        systemctl enable --now caddy
    fi
}

backup_current() {
    [[ -L "${CURRENT_LINK}" ]] || return 0
    local backup_script="${CURRENT_LINK}/scripts/backup_tms.sh"
    [[ -x "${backup_script}" || -f "${backup_script}" ]] || die "当前 release 缺少 backup_tms.sh"
    local before after latest source_kib database_kib required_kib free_kib current_release
    current_release="$(readlink -f "${CURRENT_LINK}")"
    source_kib="$(du -sk "${current_release}" "${PUBLIC_MEDIA_DIR}" "${PRIVATE_MEDIA_DIR}" | awk '{total += $1} END {print total + 0}')"
    database_kib="$(runuser -u postgres -- psql --tuples-only --no-align --set=ON_ERROR_STOP=1 \
        --dbname=postgres --command="SELECT pg_database_size('${TMS_DB_NAME}') / 1024")" || \
        die "无法估算 PostgreSQL 备份空间。"
    required_kib=$(( (source_kib + database_kib) * 12 / 10 + 524288 ))
    free_kib="$(df -Pk "${BACKUP_DIR}" | awk 'NR==2 {print $4}')"
    (( free_kib >= required_kib )) || \
        die "备份空间不足：保守估算需要 ${required_kib} KiB，可用 ${free_kib} KiB。"
    before="$(find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
    set -a
    # shellcheck disable=SC1090
    source "${RUNTIME_ENV}"
    set +a
    PROJECT_DIR="${CURRENT_LINK}" BACKUP_ROOT="${BACKUP_DIR}" ENV_FILE="${RUNTIME_ENV}" \
        APP_OS_USER="${TMS_APP_USER}" INCLUDE_GIT_BUNDLE=0 bash "${backup_script}"
    after="$(find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
    (( after > before )) || die "备份脚本未生成新的备份目录。"
    latest="$(find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
    [[ -f "${latest}/SHA256SUMS" ]] || die "最新备份缺少 SHA256SUMS：${latest}"
    (cd "${latest}" && sha256sum -c SHA256SUMS >/dev/null) || die "备份完整性校验失败。"
    local dump
    dump="$(find "${latest}" -type f \( -name '*.dump' -o -name '*.backup' \) | head -n1)"
    [[ -n "${dump}" ]] || die "备份中未找到 PostgreSQL custom dump。"
    pg_restore --list "${dump}" >/dev/null || die "pg_restore 无法读取最新数据库归档。"
    info "备份已验证：${latest}"
}

atomic_switch() {
    local release_dir="$1"
    ln -sfn "${release_dir}" "${CURRENT_LINK}.new"
    mv -Tf "${CURRENT_LINK}.new" "${CURRENT_LINK}"
}

local_healthcheck() {
    local attempt
    for attempt in {1..20}; do
        if curl --silent --show-error --fail --max-time 3 \
            --header "Host: ${TMS_DOMAIN}" --header 'X-Forwarded-Proto: https' \
            "http://${TMS_BIND}/" >/dev/null; then
            return 0
        fi
        sleep 1
    done
    return 1
}

https_healthcheck() {
    # Loopback may itself be explicitly trusted. Do not misreport it as failure.
    local attempt code requires_auth=1
    if [[ -n "${TMS_BASIC_AUTH_TRUSTED_CIDRS}" ]]; then
        requires_auth="$(basic_auth_policy 127.0.0.1)" || return 1
    fi
    for attempt in {1..15}; do
        if code="$(curl --noproxy '*' --silent --show-error --max-time 4 \
            --resolve "${TMS_DOMAIN}:443:127.0.0.1" --output /dev/null --write-out '%{http_code}' \
            "https://${TMS_DOMAIN}/")" && https_status_matches_policy "${code}" "${requires_auth}"; then
            return 0
        fi
        sleep 2
    done
    return 1
}

https_status_matches_policy() {
    local code="$1" requires_auth="$2"
    if [[ "${requires_auth}" == 1 ]]; then
        [[ "${code}" == 401 ]]
    elif [[ -e "${MAINTENANCE_FLAG}" ]]; then
        [[ "${code}" == 503 ]]
    else
        [[ "${code}" == 200 || "${code}" == 302 ]]
    fi
}

record_deploy_state() {
    local release_id="$1" sha="$2" previous="$3" migrations="$4"
    {
        printf 'RELEASE_ID=%q\nSHA=%q\nPREVIOUS_RELEASE=%q\nMIGRATIONS_APPLIED=%q\nDEPLOYED_AT=%q\n' \
            "${release_id}" "${sha}" "${previous}" "${migrations}" "$(date -u '+%FT%TZ')"
    } >"${DEPLOY_STATE}"
    chown root:root "${DEPLOY_STATE}"; chmod 0600 "${DEPLOY_STATE}"
}

cmd_apply() {
    require_root
    [[ $# -ge 3 ]] || die "用法：tms-deploy apply PLAN_ID --confirm-sha FULL_SHA"
    local plan_id="$1" confirm_sha=""
    shift
    while (($#)); do
        case "$1" in
            --confirm-sha) [[ $# -ge 2 ]] || die "--confirm-sha 缺少值"; confirm_sha="$2"; shift 2 ;;
            *) die "未知参数：$1" ;;
        esac
    done
    safe_source_config
    require_installed_layout
    for command in awk bash caddy curl df du find findmnt getent grep install ln mv \
        openssl pg_restore psql readlink runuser sed sha256sum ss stat systemctl systemd-analyze useradd; do
        require_cmd "${command}"
    done
    load_plan "${plan_id}"
    check_external_certificate
    [[ "${confirm_sha}" == "${SHA}" && "${confirm_sha}" =~ ^[0-9a-f]{40}$ ]] || die "确认 SHA 与计划不一致。"
    local free_kib previous="" migration_count=0 migrations_applied=0
    free_kib="$(df -Pk "${ROOT_DIR}" | awk 'NR==2 {print $4}')"
    (( free_kib >= 1048576 )) || die "可用空间少于 1 GiB；拒绝 apply。"
    [[ -L "${CURRENT_LINK}" ]] && previous="$(readlink -f "${CURRENT_LINK}")"

    if [[ "${FIRST_INSTALL}" == "1" ]]; then
        [[ -z "${previous}" ]] || die "--first-install 计划不能用于已有部署。"
        ensure_swap
        ensure_accounts_and_dirs
        secure_release_permissions "${RELEASE_DIR}"
        write_secret_files_and_database
        : >"${MAINTENANCE_FLAG}"
        chmod 0644 "${MAINTENANCE_FLAG}"
        install_service_and_caddy
    else
        [[ -n "${previous}" ]] || die "当前不存在 release；请重新 plan --first-install。"
        [[ -f "${RUNTIME_ENV}" && -f "${MIGRATE_ENV}" ]] || die "生产环境文件不完整。"
        backup_current
        install_service_and_caddy
    fi

    local migration_output
    if ! migration_output="$(env_run_as_app "${MIGRATE_ENV}" "${RELEASE_DIR}/.venv/bin/python" \
        "${RELEASE_DIR}/manage.py" showmigrations --plan)"; then
        die "无法读取待执行迁移；尚未进入维护状态。"
    fi
    migration_count="$(grep -c '^\[ \]' <<<"${migration_output}" || true)"
    : >"${MAINTENANCE_FLAG}"
    chmod 0644 "${MAINTENANCE_FLAG}"
    systemctl stop tms.service || true
    env_run_as_app "${MIGRATE_ENV}" "${RELEASE_DIR}/.venv/bin/python" "${RELEASE_DIR}/manage.py" migrate --noinput
    (( migration_count > 0 )) && migrations_applied=1
    grant_runtime_database_permissions
    if [[ "${FIRST_INSTALL}" == "1" ]]; then
        env_run_as_app "${MIGRATE_ENV}" "${RELEASE_DIR}/.venv/bin/python" "${RELEASE_DIR}/manage.py" bootstrap_tms --dry-run
        env_run_as_app "${MIGRATE_ENV}" "${RELEASE_DIR}/.venv/bin/python" "${RELEASE_DIR}/manage.py" bootstrap_tms --yes
    fi
    atomic_switch "${RELEASE_DIR}"
    systemctl start tms.service
    if local_healthcheck && https_healthcheck; then
        rm -f "${MAINTENANCE_FLAG}"
        record_deploy_state "${RELEASE_ID}" "${SHA}" "${previous}" "${migrations_applied}"
        heading "TMS_DEPLOYMENT_COMPLETE"
        printf 'release_id=%s\nsha=%s\nmigrations_applied=%s\n' "${RELEASE_ID}" "${SHA}" "${migrations_applied}"
        return
    fi

    if (( migrations_applied == 0 )) && [[ -n "${previous}" ]]; then
        warn "健康检查失败且未执行迁移；恢复上一 current 链接。"
        atomic_switch "${previous}"
        systemctl restart tms.service
        local_healthcheck || warn "恢复旧 release 后健康检查仍失败。"
        rm -f "${MAINTENANCE_FLAG}"
    else
        warn "健康检查失败且数据库迁移已经执行；保持维护状态，不自动回退代码或数据库。"
    fi
    die "部署验收失败。"
}

verify_permissions() {
    run_as_app test ! -w "${CURRENT_LINK}/manage.py" || die "tms 不应能写 release 代码。"
    runuser -u "${TMS_CADDY_USER}" -- test -r "${CURRENT_LINK}/staticfiles" || die "Caddy 无法读取 staticfiles。"
    runuser -u "${TMS_CADDY_USER}" -- test -r "${PUBLIC_MEDIA_DIR}" || die "Caddy 无法读取公共 media。"
    runuser -u "${TMS_CADDY_USER}" -- test ! -r "${PRIVATE_MEDIA_DIR}" || die "Caddy 不应读取私有 media。"
    runuser -u "${TMS_CADDY_USER}" -- test ! -r "${RUNTIME_ENV}" || die "Caddy 不应读取应用环境文件。"
    runuser -u "${TMS_CADDY_USER}" -- test ! -r "${BACKUP_DIR}" || die "Caddy 不应读取备份目录。"
}

verify_database_roles() {
    env_run_as_app "${RUNTIME_ENV}" "${CURRENT_LINK}/.venv/bin/python" "${CURRENT_LINK}/manage.py" check
    local db_url
    db_url="$(awk -F= '$1=="DATABASE_URL" {sub(/^[^=]*=/, ""); print}' "${RUNTIME_ENV}")"
    psql "${db_url}" --set=ON_ERROR_STOP=1 --command='SELECT 1' >/dev/null
    if psql "${db_url}" --set=ON_ERROR_STOP=1 --command='CREATE TABLE tms_permission_probe(id integer)' >/dev/null 2>&1; then
        psql "${db_url}" --command='DROP TABLE IF EXISTS tms_permission_probe' >/dev/null 2>&1 || true
        die "tms_app 意外拥有 CREATE TABLE 权限。"
    fi
}

cmd_verify() {
    while (($#)); do case "$1" in --json) JSON=1; shift ;; *) die "未知参数：$1" ;; esac; done
    require_root
    if (( JSON )); then
        exec 3>&1
        exec 1>&2
    fi
    safe_source_config
    check_external_certificate
    [[ -L "${CURRENT_LINK}" ]] || die "current 不存在。"
    systemctl is-active --quiet tms.service || die "tms.service 未运行。"
    systemctl is-active --quiet caddy || die "caddy 未运行。"
    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
    ss -ltn | grep -Eq '127\.0\.0\.1:8010|\[::1\]:8010' || die "Gunicorn 未仅在回环地址监听 8010。"
    if ss -ltn | awk '$4 ~ /:5432$/ {print $4}' | grep -Evq '^(127\.0\.0\.1|\[::1\]):5432$'; then
        die "PostgreSQL 发现非回环监听地址。"
    fi
    verify_permissions
    verify_database_roles
    local_healthcheck || die "本机 Gunicorn 健康检查失败。"
    https_healthcheck || die "HTTPS 信任链、域名或客户端网段认证策略验收失败。"
    if (( JSON )); then
        printf '{"ok":true,"release":"%s","service":"active"}\n' "$(basename "$(readlink -f "${CURRENT_LINK}")")" >&3
    else
        heading "TMS_VERIFY_OK"
        printf 'release=%s\nservice=active\n' "$(basename "$(readlink -f "${CURRENT_LINK}")")"
    fi
}

cmd_status() {
    while (($#)); do case "$1" in --json) JSON=1; shift ;; *) die "未知参数：$1" ;; esac; done
    local release="none" sha="none" active="no" maintenance="no"
    [[ -L "${CURRENT_LINK}" ]] && release="$(basename "$(readlink -f "${CURRENT_LINK}")")"
    [[ -f "${CURRENT_LINK}/.tms-release-sha" ]] && sha="$(<"${CURRENT_LINK}/.tms-release-sha")"
    systemctl is-active --quiet tms.service 2>/dev/null && active="yes"
    [[ -e "${MAINTENANCE_FLAG}" ]] && maintenance="yes"
    if (( JSON )); then
        printf '{"release":"%s","sha":"%s","active":%s,"maintenance":%s}\n' \
            "${release}" "${sha}" "$(json_bool "${active}")" "$(json_bool "${maintenance}")"
    else
        heading "TMS_STATUS"
        printf 'release=%s\nsha=%s\nservice_active=%s\nmaintenance=%s\n' "${release}" "${sha}" "${active}" "${maintenance}"
    fi
}

cmd_rollback() {
    require_root
    require_root_owned_file "$0"
    safe_source_config
    [[ "${1:-}" == "--to" && $# -eq 2 ]] || die "用法：tms-deploy rollback --to RELEASE_ID"
    local release_id="$2" target previous migrations="unknown"
    validate_release_id "${release_id}"
    target="${RELEASES_DIR}/${release_id}"
    [[ -d "${target}" ]] || die "release 不存在：${release_id}"
    [[ -L "${CURRENT_LINK}" ]] || die "current 不存在。"
    previous="$(readlink -f "${CURRENT_LINK}")"
    if [[ -f "${DEPLOY_STATE}" ]]; then
        [[ "$(stat -c '%U:%a' "${DEPLOY_STATE}")" == "root:600" ]] || die "部署状态文件权限异常。"
        # shellcheck disable=SC1090
        source "${DEPLOY_STATE}"
        migrations="${MIGRATIONS_APPLIED:-unknown}"
    fi
    [[ "${migrations}" == "0" ]] || die "当前发布可能执行过数据库迁移；禁止自动代码回滚，请按手册前滚修复或完整恢复。"
    : >"${MAINTENANCE_FLAG}"; chmod 0644 "${MAINTENANCE_FLAG}"
    systemctl stop tms.service
    atomic_switch "${target}"
    systemctl start tms.service
    if local_healthcheck; then
        rm -f "${MAINTENANCE_FLAG}"
        record_deploy_state "${release_id}" "$(<"${target}/.tms-release-sha")" "${previous}" 0
        heading "TMS_ROLLBACK_COMPLETE"
        printf 'release=%s\n' "${release_id}"
    else
        atomic_switch "${previous}"
        systemctl restart tms.service
        rm -f "${MAINTENANCE_FLAG}"
        die "目标 release 验证失败，已恢复原链接。"
    fi
}

auth_validate_username() {
    [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || die "Basic Auth 用户名格式无效。"
}

hash_basic_auth_password() {
    local password="$1" password_hash
    [[ ${#password} -ge 8 ]] || die "密码至少需要 8 个字符。"
    # Caddy reads a complete line from piped stdin. Missing LF produces EOF.
    # Keep the plaintext out of Caddy's command-line arguments.
    if ! password_hash="$(printf '%s\n' "${password}" | caddy hash-password --algorithm argon2id)"; then
        die "Basic Auth 密码哈希生成失败，未保存该用户。"
    fi
    [[ -n "${password_hash}" ]] || die "Caddy 未输出密码哈希，未保存该用户。"
    printf '%s\n' "${password_hash}"
}

cmd_auth() {
    require_root
    require_root_owned_file "$0"
    safe_source_config
    [[ $# -ge 1 ]] || die "用法：tms-deploy auth add|remove|list [USERNAME]"
    local action="$1" username="${2:-}" password password_hash tmp
    install -d -m 0750 -o root -g root "${ENV_DIR}"
    touch "${AUTH_USERS_FILE}"; chown root:root "${AUTH_USERS_FILE}"; chmod 0600 "${AUTH_USERS_FILE}"
    case "${action}" in
        list)
            cut -d: -f1 "${AUTH_USERS_FILE}"
            return ;;
        add)
            [[ -t 0 ]] || die "auth add 必须在 TTY 中隐藏读取密码。"
            auth_validate_username "${username}"
            read -r -s -p "Basic Auth password: " password; printf '\n'
            if ! password_hash="$(hash_basic_auth_password "${password}")"; then
                unset password
                return 1
            fi
            unset password
            tmp="$(mktemp "${ENV_DIR}/basic-auth.users.XXXXXX")"
            awk -F: -v user="${username}" '$1 != user' "${AUTH_USERS_FILE}" >"${tmp}"
            printf '%s:%s\n' "${username}" "${password_hash}" >>"${tmp}"
            chown root:root "${tmp}"; chmod 0600 "${tmp}"; mv -f "${tmp}" "${AUTH_USERS_FILE}" ;;
        remove)
            auth_validate_username "${username}"
            grep -Fq "${username}:" "${AUTH_USERS_FILE}" || die "用户不存在：${username}"
            [[ "$(wc -l <"${AUTH_USERS_FILE}")" -gt 1 ]] || die "不能删除最后一个 Basic Auth 用户。"
            tmp="$(mktemp "${ENV_DIR}/basic-auth.users.XXXXXX")"
            awk -F: -v user="${username}" '$1 != user' "${AUTH_USERS_FILE}" >"${tmp}"
            chown root:root "${tmp}"; chmod 0600 "${tmp}"; mv -f "${tmp}" "${AUTH_USERS_FILE}" ;;
        *) die "未知 auth 动作：${action}" ;;
    esac
    render_auth_snippet
    if [[ -f "${CADDY_SITE}" ]]; then
        caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
        systemctl reload caddy
    fi
    info "Basic Auth 配置已更新；未保存明文密码。"
}

cmd_admin() {
    require_root
    require_root_owned_file "$0"
    safe_source_config
    [[ "${1:-}" == "create" && $# -eq 1 ]] || die "用法：tms-deploy admin create"
    [[ -L "${CURRENT_LINK}" && -f "${RUNTIME_ENV}" ]] || die "TMS 尚未部署。"
    env_run_as_app "${RUNTIME_ENV}" "${CURRENT_LINK}/.venv/bin/python" "${CURRENT_LINK}/manage.py" createsuperuser
}

cmd_prune() {
    require_root
    require_root_owned_file "$0"
    local keep=5 assume_yes=0
    while (($#)); do
        case "$1" in
            --keep) [[ $# -ge 2 && "$2" =~ ^[1-9][0-9]*$ ]] || die "--keep 必须为正整数"; keep="$2"; shift 2 ;;
            --yes) assume_yes=1; shift ;;
            *) die "未知参数：$1" ;;
        esac
    done
    local current candidates=() release
    current="$(readlink -f "${CURRENT_LINK}" 2>/dev/null || true)"
    while IFS= read -r release; do
        [[ "${release}" == "${current}" ]] && continue
        candidates+=("${release}")
    done < <(find "${RELEASES_DIR}" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -nr | tail -n "+$((keep + 1))" | cut -d' ' -f2-)
    ((${#candidates[@]})) || { info "没有可清理的旧 release。"; return; }
    heading "TMS_PRUNE_CANDIDATES"
    printf '%s\n' "${candidates[@]}"
    if (( assume_yes == 0 )); then
        [[ -t 0 ]] || die "非交互执行必须显式添加 --yes。"
        local answer
        read -r -p "输入 DELETE 确认删除以上 release（不会删除备份）: " answer
        [[ "${answer}" == "DELETE" ]] || die "已取消。"
    fi
    for release in "${candidates[@]}"; do
        [[ "${release}" == "${RELEASES_DIR}/"* && "${release}" != "${RELEASES_DIR}" ]] || die "清理路径越界。"
        rm -rf --one-file-system "${release}"
    done
    info "旧 release 已清理；备份未改动。"
}

main() {
    local command="${1:-}"
    [[ -n "${command}" ]] || { usage; exit 2; }
    shift || true
    case "${command}" in
        -h|--help|help) usage ;;
        inspect) cmd_inspect "$@" ;;
        plan) cmd_plan "$@" ;;
        apply) cmd_apply "$@" ;;
        verify) cmd_verify "$@" ;;
        status) cmd_status "$@" ;;
        rollback) cmd_rollback "$@" ;;
        auth) cmd_auth "$@" ;;
        admin) cmd_admin "$@" ;;
        prune) cmd_prune "$@" ;;
        tls) cmd_tls "$@" ;;
        *) usage; die "未知命令：${command}" ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
