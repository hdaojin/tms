#!/usr/bin/env bash
#
# TMS 生产服务器完整备份脚本（v2）
#
# 面向 hdaojin/tms develop 分支当前架构：
#   - Django 6 / Python 3.13+
#   - PostgreSQL（生产）
#   - MEDIA_ROOT：公共上传
#   - PRIVATE_MEDIA_ROOT：私有业务文件
#   - NOTES_ROOT：教学笔记文件，可位于 PRIVATE_MEDIA_ROOT 内，也可独立配置
#   - .env：包含 SECRET_KEY / DATABASE_URL / PRIVATE_MEDIA_ROOT /
#           SAMBA_TASK_ENCRYPTION_KEY 等恢复所需配置
#
# 备份内容：
#   1. PostgreSQL 业务数据库（pg_dump custom archive）
#   2. PostgreSQL 全局对象（roles / tablespaces）
#   3. PostgreSQL schema-only SQL
#   4. Django dumpdata JSON.gz 辅助快照
#   5. MEDIA_ROOT
#   6. PRIVATE_MEDIA_ROOT
#   7. NOTES_ROOT（仅当它不位于 PRIVATE_MEDIA_ROOT 内时单独备份）
#   8. .env
#   9. 当前源码工作区快照（保留未提交修改）
#  10. Git bundle + commit / branch / status / log
#  11. Python / Django / PostgreSQL / OS / 运行配置元数据
#  12. 可选 Samba 账户状态快照
#  13. SHA256 完整性校验
#
# 重要：
#   - pg_dump 能提供数据库内部一致的快照，但数据库和上传文件之间不是同一个事务。
#   - 作为“核心重构前基线备份”时，强烈建议先停止会产生写入的 TMS Web/后台任务，
#     或进入维护窗口，再执行本脚本。
#   - 本脚本默认假定生产 PostgreSQL 位于本机。若 Django 指向远程 PostgreSQL，
#     脚本会拒绝猜测，要求明确提供 PGHOST / PGPORT / PG_ROLE 及认证。
#
# 常用：
#   sudo ./tms-backup-v2.sh
#
# 覆盖目录：
#   sudo PROJECT_DIR=/srv/tms BACKUP_ROOT=/var/backups/tms ./tms-backup-v2.sh
#
# 完整数据库恢复验证：
#   sudo VERIFY_RESTORE=1 ./tms-backup-v2.sh
#

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

# ==============================================================================
# 1. 用户配置
# ==============================================================================

PROJECT_DIR="${PROJECT_DIR:-/srv/tms}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/tms}"

# 留空时从 Django settings.DATABASES["default"]["NAME"] 自动读取。
DB_NAME_OVERRIDE="${DB_NAME:-}"

POSTGRES_OS_USER="${POSTGRES_OS_USER:-postgres}"
PG_ROLE="${PG_ROLE:-postgres}"
APP_OS_USER="${APP_OS_USER:-}"

PGHOST_OVERRIDE="${PGHOST:-}"
PGPORT_OVERRIDE="${PGPORT:-}"

MEDIA_ROOT_OVERRIDE="${MEDIA_ROOT:-}"
PRIVATE_MEDIA_ROOT_OVERRIDE="${PRIVATE_MEDIA_ROOT:-}"
NOTES_ROOT_OVERRIDE="${NOTES_ROOT:-}"

ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"

INCLUDE_ENV="${INCLUDE_ENV:-1}"
INCLUDE_DJANGO_FIXTURE="${INCLUDE_DJANGO_FIXTURE:-1}"
INCLUDE_SOURCE="${INCLUDE_SOURCE:-1}"
INCLUDE_GIT_BUNDLE="${INCLUDE_GIT_BUNDLE:-1}"

# auto: 当 Django SAMBA_INTEGRATION_ENABLED=True 时备份 Samba 状态
# 1: 强制尝试
# 0: 不备份
INCLUDE_SAMBA_STATE="${INCLUDE_SAMBA_STATE:-auto}"

# 0: 仅 pg_restore --list 验证
# 1: 额外创建临时数据库，真正执行一次完整 pg_restore
VERIFY_RESTORE="${VERIFY_RESTORE:-0}"

# ==============================================================================
# 2. 基础函数
# ==============================================================================

log() {
    printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

warn() {
    printf '[%s] WARNING: %s\n' "$(date '+%F %T')" "$*" >&2
}

die() {
    printf '[%s] ERROR: %s\n' "$(date '+%F %T')" "$*" >&2
    exit 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}

on_error() {
    local exit_code=$?
    warn "备份失败，退出码：${exit_code}"
    if [[ -n "${BACKUP_DIR:-}" && -d "${BACKUP_DIR:-}" ]]; then
        warn "未完成的备份目录保留在：${BACKUP_DIR}"
    fi
    exit "${exit_code}"
}
trap on_error ERR

normalize_path() {
    local value="$1"
    if [[ -z "${value}" ]]; then
        printf '\n'
    elif [[ "${value}" = /* ]]; then
        realpath -m -- "${value}"
    else
        realpath -m -- "${PROJECT_DIR}/${value}"
    fi
}

path_is_same_or_inside() {
    local child parent
    child="$(realpath -m -- "$1")"
    parent="$(realpath -m -- "$2")"
    [[ "${child}" == "${parent}" || "${child}" == "${parent}/"* ]]
}

# ==============================================================================
# 3. 前置检查与 Django 运行器
# ==============================================================================

[[ "${EUID}" -eq 0 ]] || die "请使用 root 执行：sudo $0"
[[ -d "${PROJECT_DIR}" ]] || die "PROJECT_DIR 不存在：${PROJECT_DIR}"
[[ -f "${PROJECT_DIR}/manage.py" ]] || die "未找到 ${PROJECT_DIR}/manage.py"

for cmd in \
    runuser pg_dump pg_dumpall pg_restore psql createdb dropdb \
    tar gzip sha256sum find git install stat realpath hostname du awk sed grep
do
    require_cmd "${cmd}"
done

if [[ -z "${APP_OS_USER}" ]]; then
    APP_OS_USER="$(stat -c '%U' "${PROJECT_DIR}")"
fi

id "${POSTGRES_OS_USER}" >/dev/null 2>&1 || die "系统用户不存在：${POSTGRES_OS_USER}"
id "${APP_OS_USER}" >/dev/null 2>&1 || die "系统用户不存在：${APP_OS_USER}"

run_as_postgres() {
    runuser -u "${POSTGRES_OS_USER}" -- "$@"
}

run_as_app_in_project() {
    runuser -u "${APP_OS_USER}" -- bash -c '
        set -Eeuo pipefail
        cd "$1"
        shift
        exec "$@"
    ' bash "${PROJECT_DIR}" "$@"
}

DJANGO_RUNNER=()
if [[ -x "${PROJECT_DIR}/.venv/bin/python" ]]; then
    DJANGO_RUNNER=("${PROJECT_DIR}/.venv/bin/python")
elif command -v uv >/dev/null 2>&1; then
    DJANGO_RUNNER=("$(command -v uv)" "run" "python")
elif command -v python3 >/dev/null 2>&1; then
    DJANGO_RUNNER=("$(command -v python3)")
else
    die "未找到可运行 TMS 的 Python：.venv/bin/python / uv / python3"
fi

run_django() {
    run_as_app_in_project "${DJANGO_RUNNER[@]}" manage.py "$@"
}

git_as_app() {
    run_as_app_in_project git "$@"
}

# ==============================================================================
# 4. 从 Django settings 获取实际运行配置
# ==============================================================================

log "读取 TMS Django settings……"

DJANGO_SNAPSHOT="$(
    run_django shell -c '
from django.conf import settings

db = settings.DATABASES["default"]

def out(key, value):
    if value is None:
        value = ""
    print(f"__TMS_BACKUP__{key}={value}")

out("DB_ENGINE", db.get("ENGINE", ""))
out("DB_NAME", db.get("NAME", ""))
out("DB_HOST", db.get("HOST", ""))
out("DB_PORT", db.get("PORT", ""))
out("DB_USER", db.get("USER", ""))
out("MEDIA_ROOT", settings.MEDIA_ROOT)
out("PRIVATE_MEDIA_ROOT", settings.PRIVATE_MEDIA_ROOT)
out("NOTES_ROOT", settings.NOTES_ROOT)
out("SAMBA_INTEGRATION_ENABLED", getattr(settings, "SAMBA_INTEGRATION_ENABLED", False))
'
)"

django_value() {
    local key="$1"
    printf '%s\n' "${DJANGO_SNAPSHOT}" \
        | sed -n "s/^__TMS_BACKUP__${key}=//p" \
        | tail -n 1
}

DJANGO_DB_ENGINE="$(django_value DB_ENGINE)"
DJANGO_DB_NAME="$(django_value DB_NAME)"
DJANGO_DB_HOST="$(django_value DB_HOST)"
DJANGO_DB_PORT="$(django_value DB_PORT)"
DJANGO_DB_USER="$(django_value DB_USER)"
DJANGO_MEDIA_ROOT="$(django_value MEDIA_ROOT)"
DJANGO_PRIVATE_MEDIA_ROOT="$(django_value PRIVATE_MEDIA_ROOT)"
DJANGO_NOTES_ROOT="$(django_value NOTES_ROOT)"
SAMBA_ENABLED="$(django_value SAMBA_INTEGRATION_ENABLED)"

[[ "${DJANGO_DB_ENGINE}" == *"postgresql"* ]] || \
    die "当前 Django default database 不是 PostgreSQL：${DJANGO_DB_ENGINE}"

if [[ -n "${DB_NAME_OVERRIDE}" ]]; then
    DB_NAME="${DB_NAME_OVERRIDE}"
    if [[ -n "${DJANGO_DB_NAME}" && "${DB_NAME}" != "${DJANGO_DB_NAME}" ]]; then
        warn "DB_NAME=${DB_NAME} 与 Django 实际数据库 ${DJANGO_DB_NAME} 不同；将按显式 DB_NAME 备份。"
    fi
else
    DB_NAME="${DJANGO_DB_NAME}"
fi

[[ -n "${DB_NAME}" ]] || die "无法从 Django settings 确定 PostgreSQL 数据库名"

if [[ -n "${MEDIA_ROOT_OVERRIDE}" ]]; then
    MEDIA_ROOT_RESOLVED="$(normalize_path "${MEDIA_ROOT_OVERRIDE}")"
else
    MEDIA_ROOT_RESOLVED="$(normalize_path "${DJANGO_MEDIA_ROOT}")"
fi

if [[ -n "${PRIVATE_MEDIA_ROOT_OVERRIDE}" ]]; then
    PRIVATE_MEDIA_ROOT_RESOLVED="$(normalize_path "${PRIVATE_MEDIA_ROOT_OVERRIDE}")"
else
    PRIVATE_MEDIA_ROOT_RESOLVED="$(normalize_path "${DJANGO_PRIVATE_MEDIA_ROOT}")"
fi

if [[ -n "${NOTES_ROOT_OVERRIDE}" ]]; then
    NOTES_ROOT_RESOLVED="$(normalize_path "${NOTES_ROOT_OVERRIDE}")"
else
    NOTES_ROOT_RESOLVED="$(normalize_path "${DJANGO_NOTES_ROOT}")"
fi

# ==============================================================================
# 5. PostgreSQL 连接策略
# ==============================================================================

PG_ARGS=(--username="${PG_ROLE}")

if [[ -n "${PGHOST_OVERRIDE}" ]]; then
    PG_ARGS+=(--host="${PGHOST_OVERRIDE}")
else
    case "${DJANGO_DB_HOST}" in
        ""|"localhost"|"127.0.0.1"|"::1")
            ;;
        /*)
            PG_ARGS+=(--host="${DJANGO_DB_HOST}")
            ;;
        *)
            die "Django 指向远程 PostgreSQL (${DJANGO_DB_HOST})。为避免备份错误实例，请显式设置 PGHOST/PGPORT/PG_ROLE 及认证。"
            ;;
    esac
fi

if [[ -n "${PGPORT_OVERRIDE}" ]]; then
    PG_ARGS+=(--port="${PGPORT_OVERRIDE}")
elif [[ -n "${DJANGO_DB_PORT}" ]]; then
    PG_ARGS+=(--port="${DJANGO_DB_PORT}")
fi

# ==============================================================================
# 6. 创建备份目录
# ==============================================================================

TIMESTAMP="$(date '+%Y%m%dT%H%M%S%z')"
HOSTNAME_SHORT="$(hostname -s 2>/dev/null || hostname)"
BACKUP_NAME="${TIMESTAMP}-${HOSTNAME_SHORT}-tms"
BACKUP_DIR="${BACKUP_ROOT}/${BACKUP_NAME}"

DB_DIR="${BACKUP_DIR}/database"
FILES_DIR="${BACKUP_DIR}/files"
CODE_DIR="${BACKUP_DIR}/code"
CONFIG_DIR="${BACKUP_DIR}/config"
META_DIR="${BACKUP_DIR}/metadata"

PROJECT_REAL="$(realpath -m -- "${PROJECT_DIR}")"
BACKUP_ROOT_REAL="$(realpath -m -- "${BACKUP_ROOT}")"

[[ "${BACKUP_ROOT_REAL}" != "${PROJECT_REAL}" ]] || \
    die "BACKUP_ROOT 不能等于 PROJECT_DIR，否则源码归档会递归包含备份本身。"

install -d -m 0700 \
    "${BACKUP_ROOT}" \
    "${BACKUP_DIR}" \
    "${DB_DIR}" \
    "${FILES_DIR}" \
    "${CODE_DIR}" \
    "${CONFIG_DIR}" \
    "${META_DIR}"

log "备份目录：${BACKUP_DIR}"
warn "重构基线建议在维护窗口执行：数据库 dump 内部一致，但数据库与上传文件并非同一个事务快照。"

# ==============================================================================
# 7. PostgreSQL 连通性与元数据
# ==============================================================================

log "检查 PostgreSQL 连接……"

run_as_postgres psql "${PG_ARGS[@]}" --dbname=postgres --no-psqlrc --no-password \
    -Atqc 'SELECT 1;' | grep -qx '1' || \
    die "无法以 ${PG_ROLE} 连接 PostgreSQL postgres 数据库"

run_as_postgres psql "${PG_ARGS[@]}" --dbname="${DB_NAME}" --no-psqlrc --no-password \
    -Atqc 'SELECT 1;' | grep -qx '1' || \
    die "无法连接 Django 业务数据库：${DB_NAME}"

SERVER_VERSION="$(
    run_as_postgres psql "${PG_ARGS[@]}" --dbname=postgres --no-psqlrc --no-password \
        -Atqc 'SHOW server_version;'
)"

{
    echo "backup_name=${BACKUP_NAME}"
    echo "created_at=$(date --iso-8601=seconds)"
    echo "hostname=$(hostname -f 2>/dev/null || hostname)"
    echo "project_dir=${PROJECT_REAL}"
    echo "backup_root=${BACKUP_ROOT_REAL}"
    echo
    echo "django_db_engine=${DJANGO_DB_ENGINE}"
    echo "django_db_name=${DJANGO_DB_NAME}"
    echo "django_db_host=${DJANGO_DB_HOST}"
    echo "django_db_port=${DJANGO_DB_PORT}"
    echo "django_db_user=${DJANGO_DB_USER}"
    echo "backup_db_name=${DB_NAME}"
    echo "backup_pg_role=${PG_ROLE}"
    echo
    echo "media_root=${MEDIA_ROOT_RESOLVED}"
    echo "private_media_root=${PRIVATE_MEDIA_ROOT_RESOLVED}"
    echo "notes_root=${NOTES_ROOT_RESOLVED}"
    echo
    echo "include_env=${INCLUDE_ENV}"
    echo "include_django_fixture=${INCLUDE_DJANGO_FIXTURE}"
    echo "include_source=${INCLUDE_SOURCE}"
    echo "include_git_bundle=${INCLUDE_GIT_BUNDLE}"
    echo "include_samba_state=${INCLUDE_SAMBA_STATE}"
    echo "samba_integration_enabled=${SAMBA_ENABLED}"
    echo "verify_restore=${VERIFY_RESTORE}"
} > "${META_DIR}/backup-info.txt"

{
    echo "=== OS ==="
    cat /etc/os-release 2>/dev/null || true
    echo
    echo "=== Kernel ==="
    uname -a || true
    echo
    echo "=== Python ==="
    run_as_app_in_project "${DJANGO_RUNNER[@]}" --version 2>&1 || true
    echo
    echo "=== Django ==="
    run_as_app_in_project "${DJANGO_RUNNER[@]}" -c \
        'import django; print(django.get_version())' 2>&1 || true
    echo
    echo "=== PostgreSQL client ==="
    pg_dump --version || true
    echo
    echo "=== PostgreSQL server ==="
    echo "${SERVER_VERSION}"
    echo
    echo "=== Database size ==="
    run_as_postgres psql "${PG_ARGS[@]}" --dbname="${DB_NAME}" --no-psqlrc --no-password \
        -Atqc "SELECT pg_size_pretty(pg_database_size(current_database()));" || true
    echo
    echo "=== User table count ==="
    run_as_postgres psql "${PG_ARGS[@]}" --dbname="${DB_NAME}" --no-psqlrc --no-password \
        -Atqc "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema');" || true
} > "${META_DIR}/system.txt"

run_as_postgres psql "${PG_ARGS[@]}" --dbname=postgres --no-psqlrc --no-password \
    -F $'\t' -Atqc \
    "SELECT name, setting, COALESCE(unit,''), source, COALESCE(sourcefile,'') FROM pg_settings ORDER BY name;" \
    > "${META_DIR}/postgres-settings.tsv" || true

{
    echo "=== Django check ==="
    run_django check 2>&1 || true
    echo
    echo "=== Django migrations ==="
    run_django showmigrations --plan 2>&1 || true
} > "${META_DIR}/django.txt"

# ==============================================================================
# 8. PostgreSQL 主备份
# ==============================================================================

DB_DUMP="${DB_DIR}/${DB_NAME}.dump"
GLOBALS_SQL="${DB_DIR}/postgres-globals.sql"
SCHEMA_SQL="${DB_DIR}/${DB_NAME}-schema.sql"

log "备份 PostgreSQL 数据库 ${DB_NAME}（custom format）……"
run_as_postgres pg_dump \
    "${PG_ARGS[@]}" \
    --dbname="${DB_NAME}" \
    --format=custom \
    --compress=9 \
    --no-password \
    > "${DB_DUMP}"

[[ -s "${DB_DUMP}" ]] || die "数据库 dump 文件为空：${DB_DUMP}"

log "备份 PostgreSQL 全局对象（roles / tablespaces）……"
run_as_postgres pg_dumpall \
    "${PG_ARGS[@]}" \
    --globals-only \
    --no-password \
    > "${GLOBALS_SQL}"

[[ -s "${GLOBALS_SQL}" ]] || warn "postgres-globals.sql 为空，请人工检查。"

log "导出 schema-only SQL 供重构前后对照……"
run_as_postgres pg_dump \
    "${PG_ARGS[@]}" \
    --dbname="${DB_NAME}" \
    --schema-only \
    --no-owner \
    --no-privileges \
    --no-password \
    > "${SCHEMA_SQL}"

log "验证 PostgreSQL archive 可读性……"
pg_restore --list "${DB_DUMP}" > "${DB_DIR}/${DB_NAME}-archive.list"
[[ -s "${DB_DIR}/${DB_NAME}-archive.list" ]] || die "pg_restore 无法读取数据库 archive"

# ==============================================================================
# 9. 可选完整恢复验证
# ==============================================================================

if [[ "${VERIFY_RESTORE}" == "1" ]]; then
    VERIFY_DB="${DB_NAME}_backup_verify_$(date '+%Y%m%d%H%M%S')_$$"
    VERIFY_DUMP="$(mktemp /tmp/tms-backup-verify.XXXXXX.dump)"

    log "执行完整 PostgreSQL 恢复验证：${VERIFY_DB}"

    install -o "${POSTGRES_OS_USER}" -g "${POSTGRES_OS_USER}" -m 0600 \
        "${DB_DUMP}" "${VERIFY_DUMP}"

    cleanup_verify_db() {
        run_as_postgres dropdb "${PG_ARGS[@]}" --if-exists "${VERIFY_DB}" >/dev/null 2>&1 || true
        rm -f "${VERIFY_DUMP}" >/dev/null 2>&1 || true
    }
    trap cleanup_verify_db EXIT

    run_as_postgres createdb "${PG_ARGS[@]}" --template=template0 "${VERIFY_DB}"

    run_as_postgres pg_restore \
        "${PG_ARGS[@]}" \
        --dbname="${VERIFY_DB}" \
        --exit-on-error \
        --no-password \
        "${VERIFY_DUMP}"

    run_as_postgres psql "${PG_ARGS[@]}" --dbname="${VERIFY_DB}" --no-psqlrc --no-password \
        -Atqc 'SELECT 1;' | grep -qx '1'

    cleanup_verify_db
    trap - EXIT
    log "完整 PostgreSQL 恢复验证通过。"
fi

# ==============================================================================
# 10. Django dumpdata 辅助快照
# ==============================================================================

if [[ "${INCLUDE_DJANGO_FIXTURE}" == "1" ]]; then
    log "生成 Django dumpdata 辅助快照……"

    FIXTURE_FILE="${DB_DIR}/${DB_NAME}-django-data.json.gz"
    FIXTURE_TMP="$(mktemp /tmp/tms-django-data.XXXXXX.json.gz)"
    chown "${APP_OS_USER}:${APP_OS_USER}" "${FIXTURE_TMP}"

    set +e
    run_django dumpdata \
        --all \
        --natural-foreign \
        --natural-primary \
        --indent 2 \
        --output "${FIXTURE_TMP}"
    fixture_rc=$?
    set -e

    if [[ "${fixture_rc}" -eq 0 && -s "${FIXTURE_TMP}" ]]; then
        install -m 0600 "${FIXTURE_TMP}" "${FIXTURE_FILE}"
    else
        warn "Django dumpdata 失败；PostgreSQL pg_dump 仍是权威主备份。"
        echo "Django dumpdata FAILED; PostgreSQL pg_dump remains authoritative." \
            > "${META_DIR}/django-dumpdata-warning.txt"
    fi

    rm -f "${FIXTURE_TMP}"
fi

# ==============================================================================
# 11. 文件目录备份
# ==============================================================================

archive_directory() {
    local source="$1"
    local archive="$2"
    local label="$3"

    if [[ -z "${source}" ]]; then
        warn "${label} 路径为空；跳过。"
        return 0
    fi

    if [[ ! -d "${source}" ]]; then
        warn "${label} 目录不存在：${source}"
        return 0
    fi

    log "备份 ${label}：${source}"

    tar \
        --acls \
        --xattrs \
        --numeric-owner \
        -C "${source}" \
        -czf "${archive}" \
        .

    tar -tzf "${archive}" >/dev/null
}

MEDIA_ARCHIVE="${FILES_DIR}/media.tar.gz"
PRIVATE_MEDIA_ARCHIVE="${FILES_DIR}/media-private.tar.gz"
NOTES_ARCHIVE="${FILES_DIR}/notes.tar.gz"

archive_directory "${MEDIA_ROOT_RESOLVED}" "${MEDIA_ARCHIVE}" "MEDIA_ROOT"
archive_directory "${PRIVATE_MEDIA_ROOT_RESOLVED}" "${PRIVATE_MEDIA_ARCHIVE}" "PRIVATE_MEDIA_ROOT"

if [[ -n "${NOTES_ROOT_RESOLVED}" && -n "${PRIVATE_MEDIA_ROOT_RESOLVED}" ]] && \
   path_is_same_or_inside "${NOTES_ROOT_RESOLVED}" "${PRIVATE_MEDIA_ROOT_RESOLVED}"; then
    log "NOTES_ROOT 位于 PRIVATE_MEDIA_ROOT 内，已随 media-private.tar.gz 备份，不重复打包。"
    echo "NOTES_ROOT is included in PRIVATE_MEDIA_ROOT archive." \
        > "${META_DIR}/notes-backup.txt"
else
    archive_directory "${NOTES_ROOT_RESOLVED}" "${NOTES_ARCHIVE}" "NOTES_ROOT"
fi

# ==============================================================================
# 12. .env 与部署配置
# ==============================================================================

if [[ "${INCLUDE_ENV}" == "1" ]]; then
    if [[ -f "${ENV_FILE}" ]]; then
        log "备份 .env（敏感文件，仅 root 可读）……"
        install -m 0600 "${ENV_FILE}" "${CONFIG_DIR}/.env"
    else
        warn "INCLUDE_ENV=1，但未找到 ENV_FILE：${ENV_FILE}"
    fi
fi

if command -v systemctl >/dev/null 2>&1; then
    for unit in tms.service tms-gunicorn.service gunicorn.service; do
        if systemctl cat "${unit}" >/dev/null 2>&1; then
            systemctl cat "${unit}" > "${CONFIG_DIR}/${unit}.txt" 2>/dev/null || true
        fi
    done
fi

if command -v nginx >/dev/null 2>&1; then
    nginx -T > "${CONFIG_DIR}/nginx-config.txt" 2>&1 || true
fi

# ==============================================================================
# 13. 可选 Samba 系统状态
# ==============================================================================

SHOULD_BACKUP_SAMBA=0
case "${INCLUDE_SAMBA_STATE}" in
    1|"true"|"True"|"TRUE")
        SHOULD_BACKUP_SAMBA=1
        ;;
    0|"false"|"False"|"FALSE")
        SHOULD_BACKUP_SAMBA=0
        ;;
    auto)
        if [[ "${SAMBA_ENABLED}" == "True" || "${SAMBA_ENABLED}" == "true" || "${SAMBA_ENABLED}" == "1" ]]; then
            SHOULD_BACKUP_SAMBA=1
        fi
        ;;
    *)
        die "INCLUDE_SAMBA_STATE 必须是 auto / 1 / 0"
        ;;
esac

if [[ "${SHOULD_BACKUP_SAMBA}" == "1" ]]; then
    log "Samba 集成已启用/被要求，保存 Samba 账户状态快照……"

    if command -v pdbedit >/dev/null 2>&1; then
        pdbedit -L -w > "${CONFIG_DIR}/samba-passdb-export.txt" 2>/dev/null || \
            warn "pdbedit -L -w 导出失败。"
        chmod 0600 "${CONFIG_DIR}/samba-passdb-export.txt" 2>/dev/null || true

        pdbedit -L -v > "${META_DIR}/samba-users.txt" 2>/dev/null || true
    else
        warn "Samba 集成启用，但系统不存在 pdbedit。"
    fi

    getent passwd > "${META_DIR}/system-passwd.txt" 2>/dev/null || true
    getent group > "${META_DIR}/system-group.txt" 2>/dev/null || true

    if [[ -f /etc/samba/smb.conf ]]; then
        install -m 0600 /etc/samba/smb.conf "${CONFIG_DIR}/smb.conf"
    fi
fi

# ==============================================================================
# 14. Git 元数据与源码工作区
# ==============================================================================

if git_as_app rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log "保存 Git 元数据……"

    {
        echo "commit=$(git_as_app rev-parse HEAD)"
        echo "branch=$(git_as_app branch --show-current || true)"
        echo "describe=$(git_as_app describe --always --dirty --tags 2>/dev/null || true)"
        echo
        echo "=== remotes ==="
        git_as_app remote -v || true
        echo
        echo "=== status ==="
        git_as_app status --short --branch || true
        echo
        echo "=== last commits ==="
        git_as_app log -n 20 --date=iso --pretty=fuller || true
    } > "${CODE_DIR}/git-info.txt"

    if [[ "${INCLUDE_GIT_BUNDLE}" == "1" ]]; then
        log "生成 Git bundle……"
        GIT_BUNDLE_TMP="$(mktemp /tmp/tms-git-bundle.XXXXXX)"
        chown "${APP_OS_USER}:${APP_OS_USER}" "${GIT_BUNDLE_TMP}"

        git_as_app bundle create "${GIT_BUNDLE_TMP}" --all

        # verify 需要仓库上下文；在 PROJECT_DIR 中以应用用户验证临时 bundle。
        git_as_app bundle verify "${GIT_BUNDLE_TMP}" \
            > "${META_DIR}/git-bundle-verify.txt" 2>&1

        install -m 0600 "${GIT_BUNDLE_TMP}" "${CODE_DIR}/tms.git.bundle"
        rm -f "${GIT_BUNDLE_TMP}"
    fi
else
    warn "${PROJECT_DIR} 不是有效 Git 工作区。"
fi

if [[ "${INCLUDE_SOURCE}" == "1" ]]; then
    log "备份当前源码工作区（包括未提交修改）……"

    TAR_EXCLUDES=(
        "--exclude=./.git"
        "--exclude=./.env"
        "--exclude=./.env.*"
        "--exclude=./.venv"
        "--exclude=./venv"
        "--exclude=./.uv-cache"
        "--exclude=./node_modules"
        "--exclude=./__pycache__"
        "--exclude=*/__pycache__"
        "--exclude=./.pytest_cache"
        "--exclude=./.mypy_cache"
        "--exclude=./.ruff_cache"
        "--exclude=./staticfiles"
        "--exclude=./media"
        "--exclude=./media-private"
        "--exclude=./backups"
    )

    for data_root in \
        "${MEDIA_ROOT_RESOLVED}" \
        "${PRIVATE_MEDIA_ROOT_RESOLVED}" \
        "${NOTES_ROOT_RESOLVED}"
    do
        if [[ -n "${data_root}" ]] && \
           path_is_same_or_inside "${data_root}" "${PROJECT_REAL}" && \
           [[ "$(realpath -m -- "${data_root}")" != "${PROJECT_REAL}" ]]; then
            rel="$(realpath --relative-to="${PROJECT_REAL}" "$(realpath -m -- "${data_root}")")"
            TAR_EXCLUDES+=("--exclude=./${rel}")
        fi
    done

    if path_is_same_or_inside "${BACKUP_ROOT_REAL}" "${PROJECT_REAL}"; then
        rel_backup="$(realpath --relative-to="${PROJECT_REAL}" "${BACKUP_ROOT_REAL}")"
        TAR_EXCLUDES+=("--exclude=./${rel_backup}")
    fi

    tar \
        --acls \
        --xattrs \
        --numeric-owner \
        -C "${PROJECT_DIR}" \
        "${TAR_EXCLUDES[@]}" \
        -czf "${CODE_DIR}/tms-source.tar.gz" \
        .

    tar -tzf "${CODE_DIR}/tms-source.tar.gz" >/dev/null
fi

for f in \
    pyproject.toml \
    uv.lock \
    requirements.txt \
    package.json \
    package-lock.json \
    pnpm-lock.yaml \
    yarn.lock \
    README.md \
    CONTEXT.md \
    AGENTS.md
do
    if [[ -f "${PROJECT_DIR}/${f}" ]]; then
        cp -a "${PROJECT_DIR}/${f}" "${META_DIR}/${f}"
    fi
done

# ==============================================================================
# 15. 恢复说明
# ==============================================================================

cat > "${BACKUP_DIR}/RESTORE.txt" <<EOF
TMS backup: ${BACKUP_NAME}
Created: $(date --iso-8601=seconds)

原运行配置：
  PROJECT_DIR=${PROJECT_REAL}
  DB_NAME=${DB_NAME}
  MEDIA_ROOT=${MEDIA_ROOT_RESOLVED}
  PRIVATE_MEDIA_ROOT=${PRIVATE_MEDIA_ROOT_RESOLVED}
  NOTES_ROOT=${NOTES_ROOT_RESOLVED}

建议恢复顺序：

1. 准备与备份兼容的 PostgreSQL、Python 和 TMS 代码环境。

2. 如需完整恢复 PostgreSQL roles/tablespaces，先人工审阅并执行：
     psql -U postgres -d postgres -f database/postgres-globals.sql

3. 创建空数据库（建议 template0）并恢复：
     createdb -U postgres --template=template0 ${DB_NAME}
     pg_restore -U postgres -d ${DB_NAME} database/${DB_NAME}.dump

4. 恢复公共上传文件：
     mkdir -p "${MEDIA_ROOT_RESOLVED}"
     tar -xzf files/media.tar.gz -C "${MEDIA_ROOT_RESOLVED}"

5. 恢复私有上传文件：
     mkdir -p "${PRIVATE_MEDIA_ROOT_RESOLVED}"
     tar -xzf files/media-private.tar.gz -C "${PRIVATE_MEDIA_ROOT_RESOLVED}"

6. NOTES_ROOT 如果位于 PRIVATE_MEDIA_ROOT 内，不需要再次恢复。
   如果本备份存在 files/notes.tar.gz，则恢复到：
     "${NOTES_ROOT_RESOLVED}"

7. 恢复 config/.env，并根据新服务器环境核对路径、域名和数据库连接。

8. 恢复/检出对应 Git 提交，然后执行：
     python manage.py check
     python manage.py showmigrations
   不要在确认数据迁移方案前直接对生产恢复库执行新的 destructive migrations。

9. 最后校验：
     sha256sum --check SHA256SUMS

注意：
- config/.env、database/postgres-globals.sql、数据库 dump，以及可能存在的
  config/samba-passdb-export.txt 都包含敏感信息。
- 不建议在未审阅的目标系统上直接执行 postgres-globals.sql。
EOF

# ==============================================================================
# 16. 文件清单与 SHA256
# ==============================================================================

log "生成文件清单和 SHA256……"

(
    cd "${BACKUP_DIR}"

    find . -type f ! -name 'SHA256SUMS' -printf '%P\t%s bytes\n' \
        | LC_ALL=C sort \
        > MANIFEST.txt

    find . -type f ! -name 'SHA256SUMS' -print0 \
        | LC_ALL=C sort -z \
        | xargs -0 sha256sum \
        > SHA256SUMS

    sha256sum --check SHA256SUMS >/dev/null
)

chmod -R go-rwx "${BACKUP_DIR}"

# ==============================================================================
# 17. 完成摘要
# ==============================================================================

TOTAL_SIZE="$(du -sh "${BACKUP_DIR}" | awk '{print $1}')"

log "============================================================"
log "TMS 备份完成"
log "目录：${BACKUP_DIR}"
log "大小：${TOTAL_SIZE}"
log "数据库：${DB_DUMP}"

if [[ -f "${MEDIA_ARCHIVE}" ]]; then
    log "公共媒体：${MEDIA_ARCHIVE}"
fi
if [[ -f "${PRIVATE_MEDIA_ARCHIVE}" ]]; then
    log "私有媒体：${PRIVATE_MEDIA_ARCHIVE}"
fi
if [[ -f "${NOTES_ARCHIVE}" ]]; then
    log "独立 Notes：${NOTES_ARCHIVE}"
fi

log "恢复说明：${BACKUP_DIR}/RESTORE.txt"
log "校验：${BACKUP_DIR}/SHA256SUMS"
log "============================================================"
log "该备份含业务数据和敏感配置；异机保存前建议使用加密存储。"
