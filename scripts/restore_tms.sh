#!/usr/bin/env bash
#
# restore_tms.sh
#
# TMS 完整备份恢复工具，与 backup_tms.sh / tms-backup-v2.sh 生成的目录配套使用。
#
# 安全模型：
#   1. 强制校验 SHA256SUMS。
#   2. 先预检并显示完整恢复计划。
#   3. 默认进入 drill（恢复演练）模式，不触碰生产数据库/生产 media。
#   4. production 模式必须显式指定 --mode production --force。
#   5. 默认不恢复 PostgreSQL globals、不覆盖 .env、不修改 Samba/systemd/Nginx。
#
# 默认演练：
#   sudo ./restore_tms.sh --backup /var/backups/tms/<backup-dir>
#
# 只预览：
#   sudo ./restore_tms.sh --backup /var/backups/tms/<backup-dir> --dry-run
#
# 生产恢复示例：
#   sudo ./restore_tms.sh \
#       --backup /var/backups/tms/<backup-dir> \
#       --mode production \
#       --force
#
# 生产恢复并先恢复 PostgreSQL roles/tablespaces：
#   sudo ./restore_tms.sh \
#       --backup /var/backups/tms/<backup-dir> \
#       --mode production \
#       --restore-globals \
#       --force
#
# 注意：
#   - 生产恢复前应停止 TMS 的写入流量和后台任务。
#   - 本脚本只自动恢复 PostgreSQL + TMS 持久化文件。
#   - Samba、systemd、Nginx 等系统级配置只做备份存在性提示，不自动覆盖系统。
#

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

# ==============================================================================
# 默认值
# ==============================================================================

BACKUP_DIR=""
MODE="drill"
TARGET_DB=""
TARGET_DB_OWNER=""
RESTORE_ROOT=""

MEDIA_TARGET=""
PRIVATE_MEDIA_TARGET=""
NOTES_TARGET=""

POSTGRES_OS_USER="${POSTGRES_OS_USER:-postgres}"
PG_ROLE="${PG_ROLE:-postgres}"
PGHOST_OVERRIDE="${PGHOST:-}"
PGPORT_OVERRIDE="${PGPORT:-}"

RESTORE_GLOBALS=0
RESTORE_ENV=0
ENV_TARGET=""

SKIP_DB=0
SKIP_FILES=0
SKIP_CODE=0
FORCE=0
YES=0
DRY_RUN=0

TIMESTAMP="$(date '+%Y%m%dT%H%M%S%z')"

TEMP_FILES=()

cleanup_temp_files() {
    local f
    for f in "${TEMP_FILES[@]:-}"; do
        [[ -n "${f}" ]] && rm -f -- "${f}" >/dev/null 2>&1 || true
    done
}
trap cleanup_temp_files EXIT

# ==============================================================================
# 输出与帮助
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

usage() {
    cat <<'EOF'
用法：
  sudo ./restore_tms.sh --backup BACKUP_DIR [options]

必要参数：
  --backup DIR              backup_tms.sh 生成的某次完整备份目录

模式：
  --mode drill              恢复演练（默认）。数据库和文件恢复到隔离目标
  --mode production         正式恢复。必须同时指定 --force

数据库：
  --target-db NAME          目标数据库名
  --target-db-owner ROLE    drill 模式下恢复对象的 owner；默认优先使用原 Django DB user
  --restore-globals         production 模式下先执行 postgres-globals.sql
  --skip-db                 不恢复数据库

文件：
  --restore-root DIR        drill 模式隔离根目录
  --media-target DIR        production 模式 MEDIA_ROOT 目标
  --private-media-target DIR
                            production 模式 PRIVATE_MEDIA_ROOT 目标
  --notes-target DIR        production 模式独立 NOTES_ROOT 目标
  --skip-files              不恢复 media / media-private / 独立 notes

代码与配置：
  --skip-code               drill 模式不解压 tms-source.tar.gz
  --restore-env             production 模式恢复备份中的 config/.env
  --env-target FILE         .env 目标路径；默认使用备份记录的 PROJECT_DIR/.env

执行控制：
  --dry-run                 完成校验和预检，显示计划后退出，不写入
  --force                   允许 destructive 操作；production 模式必须指定
  --yes                     跳过交互确认
  -h, --help                显示帮助

环境变量：
  POSTGRES_OS_USER          PostgreSQL 系统用户，默认 postgres
  PG_ROLE                   PostgreSQL 管理角色，默认 postgres
  PGHOST / PGPORT           非默认 PostgreSQL 连接时使用

安全说明：
  * drill 模式默认不会覆盖生产数据库、生产 media 或生产 .env。
  * production 模式仍不会自动恢复 Samba、Nginx、systemd 或覆盖生产源码。
  * --restore-globals 会创建/修改 PostgreSQL roles/tablespaces，必须人工确认。
EOF
}

# ==============================================================================
# 参数解析
# ==============================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backup)
            [[ $# -ge 2 ]] || die "--backup 缺少参数"
            BACKUP_DIR="$2"
            shift 2
            ;;
        --mode)
            [[ $# -ge 2 ]] || die "--mode 缺少参数"
            MODE="$2"
            shift 2
            ;;
        --target-db)
            [[ $# -ge 2 ]] || die "--target-db 缺少参数"
            TARGET_DB="$2"
            shift 2
            ;;
        --target-db-owner)
            [[ $# -ge 2 ]] || die "--target-db-owner 缺少参数"
            TARGET_DB_OWNER="$2"
            shift 2
            ;;
        --restore-root)
            [[ $# -ge 2 ]] || die "--restore-root 缺少参数"
            RESTORE_ROOT="$2"
            shift 2
            ;;
        --media-target)
            [[ $# -ge 2 ]] || die "--media-target 缺少参数"
            MEDIA_TARGET="$2"
            shift 2
            ;;
        --private-media-target)
            [[ $# -ge 2 ]] || die "--private-media-target 缺少参数"
            PRIVATE_MEDIA_TARGET="$2"
            shift 2
            ;;
        --notes-target)
            [[ $# -ge 2 ]] || die "--notes-target 缺少参数"
            NOTES_TARGET="$2"
            shift 2
            ;;
        --restore-globals)
            RESTORE_GLOBALS=1
            shift
            ;;
        --restore-env)
            RESTORE_ENV=1
            shift
            ;;
        --env-target)
            [[ $# -ge 2 ]] || die "--env-target 缺少参数"
            ENV_TARGET="$2"
            shift 2
            ;;
        --skip-db)
            SKIP_DB=1
            shift
            ;;
        --skip-files)
            SKIP_FILES=1
            shift
            ;;
        --skip-code)
            SKIP_CODE=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --force)
            FORCE=1
            shift
            ;;
        --yes)
            YES=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "未知参数：$1；使用 --help 查看帮助"
            ;;
    esac
done

# ==============================================================================
# 基础函数
# ==============================================================================

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}

metadata_value() {
    local key="$1"
    local file="${BACKUP_DIR}/metadata/backup-info.txt"
    awk -F= -v k="${key}" '
        $1 == k {
            sub(/^[^=]*=/, "", $0)
            print $0
            exit
        }
    ' "${file}"
}

run_as_postgres() {
    runuser -u "${POSTGRES_OS_USER}" -- "$@"
}

db_exists() {
    local name="$1"
    printf '%s\n' "SELECT 1 FROM pg_database WHERE datname = :'target_db';" \
        | run_as_postgres psql \
            "${PG_ARGS[@]}" \
            --dbname=postgres \
            --no-psqlrc \
            --no-password \
            --set=target_db="${name}" \
            -Atq \
        | grep -qx '1'
}

role_exists() {
    local name="$1"
    printf '%s\n' "SELECT 1 FROM pg_roles WHERE rolname = :'target_role';" \
        | run_as_postgres psql \
            "${PG_ARGS[@]}" \
            --dbname=postgres \
            --no-psqlrc \
            --no-password \
            --set=target_role="${name}" \
            -Atq \
        | grep -qx '1'
}

path_is_same_or_inside() {
    local child parent
    child="$(realpath -m -- "$1")"
    parent="$(realpath -m -- "$2")"
    [[ "${child}" == "${parent}" || "${child}" == "${parent}/"* ]]
}

assert_safe_destructive_dir() {
    local raw="$1"
    local label="$2"
    local dir

    [[ -n "${raw}" ]] || die "${label} 路径为空"
    dir="$(realpath -m -- "${raw}")"

    case "${dir}" in
        /|/bin|/boot|/dev|/etc|/home|/lib|/lib64|/media|/mnt|/opt|/proc|/root|/run|/sbin|/srv|/sys|/tmp|/usr|/var|/var/tmp)
            die "拒绝对高风险系统目录执行恢复替换：${label}=${dir}"
            ;;
    esac
}

assert_safe_target_db() {
    local name="$1"

    [[ -n "${name}" ]] || die "目标数据库名为空"

    case "${name}" in
        postgres|template0|template1)
            die "拒绝使用 PostgreSQL 系统数据库作为恢复目标：${name}"
            ;;
    esac

    if [[ "${MODE}" == "drill" && "${name}" == "${ORIGINAL_DB}" ]]; then
        die "drill 模式禁止恢复到原生产数据库名 ${ORIGINAL_DB}"
    fi
}

validate_production_dir_target() {
    local dir="$1"
    local label="$2"

    [[ -n "${dir}" ]] || die "${label} 目标路径为空"
    assert_safe_destructive_dir "${dir}" "${label}"

    if [[ -n "${ORIGINAL_PROJECT_DIR}" ]]; then
        if [[ "$(realpath -m -- "${dir}")" == "$(realpath -m -- "${ORIGINAL_PROJECT_DIR}")" ]] || \
           path_is_same_or_inside "${ORIGINAL_PROJECT_DIR}" "${dir}"; then
            die "${label} 目标 ${dir} 等于或包含 TMS 项目目录 ${ORIGINAL_PROJECT_DIR}，拒绝执行目录替换。"
        fi
    fi

    if [[ -L "${dir}" ]]; then
        die "${label} 目标是符号链接：${dir}。为避免恢复到错误位置，请显式指定真实目录路径。"
    fi

    if [[ -e "${dir}" && ! -d "${dir}" ]]; then
        die "${label} 目标存在但不是目录：${dir}"
    fi
}

archive_is_safe() {
    local archive="$1"
    local bad=0
    local entry clean

    while IFS= read -r entry; do
        clean="${entry#./}"

        [[ -z "${clean}" || "${clean}" == "." ]] && continue

        if [[ "${clean}" = /* ||
              "${clean}" == ".." ||
              "${clean}" == ../* ||
              "${clean}" == *"/../"* ]]; then
            warn "归档包含不安全路径：${entry}"
            bad=1
            break
        fi
    done < <(tar -tzf "${archive}")

    [[ "${bad}" -eq 0 ]]
}

directory_nonempty() {
    local dir="$1"
    [[ -d "${dir}" ]] && find "${dir}" -mindepth 1 -maxdepth 1 -print -quit | grep -q .
}

prepare_isolated_dir() {
    local dir="$1"

    assert_safe_destructive_dir "${dir}" "RESTORE_ROOT"

    if [[ -e "${dir}" ]]; then
        if directory_nonempty "${dir}"; then
            if [[ "${FORCE}" -ne 1 ]]; then
                die "目标目录非空：${dir}；drill 模式可换一个 --restore-root，或显式 --force"
            fi
            rm -rf -- "${dir}"
        elif [[ ! -d "${dir}" ]]; then
            die "目标路径存在但不是目录：${dir}"
        fi
    fi

    install -d -m 0700 "${dir}"
}

prepare_production_dir() {
    local dir="$1"
    local label="$2"

    validate_production_dir_target "${dir}" "${label}"

    if directory_nonempty "${dir}"; then
        [[ "${FORCE}" -eq 1 ]] || die "${label} 目标非空：${dir}；production 模式需要 --force"

        local safety="${dir}.before-restore-${TIMESTAMP}"
        log "保留现有 ${label}：${dir} -> ${safety}"
        mv -- "${dir}" "${safety}"
    fi

    install -d -m 0750 "${dir}"
}

extract_archive() {
    local archive="$1"
    local target="$2"
    local label="$3"

    [[ -f "${archive}" ]] || {
        warn "${label} 归档不存在：${archive}"
        return 0
    }

    archive_is_safe "${archive}" || die "${label} 归档路径检查失败：${archive}"

    install -d -m 0750 "${target}"

    log "恢复 ${label} -> ${target}"
    tar \
        --acls \
        --xattrs \
        --numeric-owner \
        -xzf "${archive}" \
        -C "${target}"
}

confirm_restore() {
    if [[ "${YES}" -eq 1 ]]; then
        return 0
    fi

    echo
    if [[ "${MODE}" == "production" ]]; then
        printf '这是正式恢复。请输入 RESTORE-PRODUCTION 继续：'
        read -r answer
        [[ "${answer}" == "RESTORE-PRODUCTION" ]] || die "用户取消恢复"
    else
        printf '请输入 RESTORE 继续恢复演练：'
        read -r answer
        [[ "${answer}" == "RESTORE" ]] || die "用户取消恢复"
    fi
}

# ==============================================================================
# 前置检查
# ==============================================================================

[[ "${EUID}" -eq 0 ]] || die "请使用 root 执行：sudo $0"
[[ -n "${BACKUP_DIR}" ]] || die "必须指定 --backup BACKUP_DIR"

BACKUP_DIR="$(realpath -m -- "${BACKUP_DIR}")"

[[ "${MODE}" == "drill" || "${MODE}" == "production" ]] || \
    die "--mode 只能是 drill 或 production"

if [[ "${MODE}" == "production" && "${FORCE}" -ne 1 ]]; then
    die "production 模式必须显式指定 --force"
fi

if [[ "${MODE}" == "drill" && "${RESTORE_GLOBALS}" -eq 1 ]]; then
    die "drill 模式禁止 --restore-globals，避免演练修改现有 PostgreSQL 全局角色"
fi

if [[ "${MODE}" == "drill" && "${RESTORE_ENV}" -eq 1 ]]; then
    die "drill 模式禁止 --restore-env；演练环境请按文档创建隔离 .env"
fi

for cmd in \
    tar sha256sum awk grep find install realpath mv rm date
do
    require_cmd "${cmd}"
done

if [[ "${SKIP_DB}" -eq 0 || "${RESTORE_GLOBALS}" -eq 1 ]]; then
    for cmd in runuser psql pg_restore createdb dropdb; do
        require_cmd "${cmd}"
    done

    id "${POSTGRES_OS_USER}" >/dev/null 2>&1 || \
        die "系统用户不存在：${POSTGRES_OS_USER}"
fi

[[ -d "${BACKUP_DIR}" ]] || die "备份目录不存在：${BACKUP_DIR}"
[[ -f "${BACKUP_DIR}/metadata/backup-info.txt" ]] || \
    die "缺少 metadata/backup-info.txt；这不是受支持的 TMS 完整备份目录"
[[ -f "${BACKUP_DIR}/SHA256SUMS" ]] || die "缺少 SHA256SUMS"

# ==============================================================================
# 读取备份元数据
# ==============================================================================

ORIGINAL_PROJECT_DIR="$(metadata_value project_dir)"
ORIGINAL_DB="$(metadata_value backup_db_name)"
ORIGINAL_DB_USER="$(metadata_value django_db_user)"
ORIGINAL_MEDIA_ROOT="$(metadata_value media_root)"
ORIGINAL_PRIVATE_MEDIA_ROOT="$(metadata_value private_media_root)"
ORIGINAL_NOTES_ROOT="$(metadata_value notes_root)"
BACKUP_NAME="$(metadata_value backup_name)"
BACKUP_CREATED_AT="$(metadata_value created_at)"

[[ -n "${ORIGINAL_DB}" ]] || die "backup-info.txt 中缺少 backup_db_name"
[[ -n "${BACKUP_NAME}" ]] || BACKUP_NAME="$(basename "${BACKUP_DIR}")"

DB_DUMP="${BACKUP_DIR}/database/${ORIGINAL_DB}.dump"
GLOBALS_SQL="${BACKUP_DIR}/database/postgres-globals.sql"

MEDIA_ARCHIVE="${BACKUP_DIR}/files/media.tar.gz"
PRIVATE_MEDIA_ARCHIVE="${BACKUP_DIR}/files/media-private.tar.gz"
NOTES_ARCHIVE="${BACKUP_DIR}/files/notes.tar.gz"
SOURCE_ARCHIVE="${BACKUP_DIR}/code/tms-source.tar.gz"
BACKUP_ENV="${BACKUP_DIR}/config/.env"

[[ "${SKIP_DB}" -eq 1 || -f "${DB_DUMP}" ]] || die "缺少数据库归档：${DB_DUMP}"

# ==============================================================================
# PostgreSQL 连接
# ==============================================================================

PG_ARGS=(--username="${PG_ROLE}")

if [[ -n "${PGHOST_OVERRIDE}" ]]; then
    PG_ARGS+=(--host="${PGHOST_OVERRIDE}")
fi

if [[ -n "${PGPORT_OVERRIDE}" ]]; then
    PG_ARGS+=(--port="${PGPORT_OVERRIDE}")
fi

if [[ "${SKIP_DB}" -eq 0 || "${RESTORE_GLOBALS}" -eq 1 ]]; then
    run_as_postgres psql \
        "${PG_ARGS[@]}" \
        --dbname=postgres \
        --no-psqlrc \
        --no-password \
        -Atqc 'SELECT 1;' | grep -qx '1' || \
        die "无法连接 PostgreSQL"
fi

# ==============================================================================
# 强制完整性校验
# ==============================================================================

log "校验备份 SHA256……"
(
    cd "${BACKUP_DIR}"
    sha256sum --check SHA256SUMS
)

if [[ "${SKIP_DB}" -eq 0 ]]; then
    log "验证 PostgreSQL custom archive……"
    pg_restore --list "${DB_DUMP}" >/dev/null
fi

if [[ "${SKIP_FILES}" -eq 0 ]]; then
    for archive in "${MEDIA_ARCHIVE}" "${PRIVATE_MEDIA_ARCHIVE}" "${NOTES_ARCHIVE}"; do
        if [[ -f "${archive}" ]]; then
            archive_is_safe "${archive}" || die "文件归档安全检查失败：${archive}"
        fi
    done
fi

# ==============================================================================
# 计算恢复目标
# ==============================================================================

if [[ "${MODE}" == "drill" ]]; then
    if [[ -z "${RESTORE_ROOT}" ]]; then
        RESTORE_ROOT="/var/tmp/tms-restore/${BACKUP_NAME}-${TIMESTAMP}"
    fi
    RESTORE_ROOT="$(realpath -m -- "${RESTORE_ROOT}")"

    if [[ -z "${TARGET_DB}" ]]; then
        # PostgreSQL identifier 最长 63 字节；保守截断原数据库名。
        db_prefix="${ORIGINAL_DB:0:32}"
        TARGET_DB="${db_prefix}_drill_$(date '+%Y%m%d%H%M%S')"
    fi

    DRILL_PROJECT_DIR="${RESTORE_ROOT}/project"
    MEDIA_TARGET="${DRILL_PROJECT_DIR}/media"
    PRIVATE_MEDIA_TARGET="${DRILL_PROJECT_DIR}/media-private"

    if [[ -f "${NOTES_ARCHIVE}" ]]; then
        NOTES_TARGET="${DRILL_PROJECT_DIR}/notes-restored"
    elif [[ -n "${ORIGINAL_NOTES_ROOT}" &&
            -n "${ORIGINAL_PRIVATE_MEDIA_ROOT}" ]] &&
         path_is_same_or_inside "${ORIGINAL_NOTES_ROOT}" "${ORIGINAL_PRIVATE_MEDIA_ROOT}"; then
        notes_rel="$(realpath -m --relative-to="${ORIGINAL_PRIVATE_MEDIA_ROOT}" "${ORIGINAL_NOTES_ROOT}")"
        NOTES_TARGET="${PRIVATE_MEDIA_TARGET}/${notes_rel}"
    else
        NOTES_TARGET=""
    fi

    if [[ "${SKIP_DB}" -eq 0 && -z "${TARGET_DB_OWNER}" ]]; then
        if [[ -n "${ORIGINAL_DB_USER}" ]] && role_exists "${ORIGINAL_DB_USER}"; then
            TARGET_DB_OWNER="${ORIGINAL_DB_USER}"
        else
            TARGET_DB_OWNER="${PG_ROLE}"
        fi
    elif [[ "${SKIP_DB}" -eq 1 ]]; then
        TARGET_DB_OWNER="[skip]"
    fi
else
    RESTORE_ROOT="/var/tmp/tms-restore/${BACKUP_NAME}-production-${TIMESTAMP}"

    [[ -n "${TARGET_DB}" ]] || TARGET_DB="${ORIGINAL_DB}"
    [[ -n "${MEDIA_TARGET}" ]] || MEDIA_TARGET="${ORIGINAL_MEDIA_ROOT}"
    [[ -n "${PRIVATE_MEDIA_TARGET}" ]] || PRIVATE_MEDIA_TARGET="${ORIGINAL_PRIVATE_MEDIA_ROOT}"
    [[ -n "${NOTES_TARGET}" ]] || NOTES_TARGET="${ORIGINAL_NOTES_ROOT}"

    if [[ "${RESTORE_ENV}" -eq 1 && -z "${ENV_TARGET}" ]]; then
        [[ -n "${ORIGINAL_PROJECT_DIR}" ]] || \
            die "无法从备份元数据确定原 PROJECT_DIR，请显式指定 --env-target"
        ENV_TARGET="${ORIGINAL_PROJECT_DIR}/.env"
    fi
fi

# ==============================================================================
# 恢复目标安全预检
# ==============================================================================

if [[ "${SKIP_DB}" -eq 0 ]]; then
    assert_safe_target_db "${TARGET_DB}"
fi

if [[ "${MODE}" == "drill" ]]; then
    assert_safe_destructive_dir "${RESTORE_ROOT}" "RESTORE_ROOT"
else
    if [[ "${SKIP_FILES}" -eq 0 ]]; then
        [[ ! -f "${MEDIA_ARCHIVE}" ]] || validate_production_dir_target "${MEDIA_TARGET}" "MEDIA_ROOT"
        [[ ! -f "${PRIVATE_MEDIA_ARCHIVE}" ]] || validate_production_dir_target "${PRIVATE_MEDIA_TARGET}" "PRIVATE_MEDIA_ROOT"
        [[ ! -f "${NOTES_ARCHIVE}" ]] || validate_production_dir_target "${NOTES_TARGET}" "NOTES_ROOT"
    fi

    if [[ "${RESTORE_ENV}" -eq 1 ]]; then
        [[ -n "${ENV_TARGET}" ]] || die ".env 目标为空"
        [[ "$(basename "${ENV_TARGET}")" == ".env" ]] || \
            die "--env-target 必须指向名为 .env 的文件：${ENV_TARGET}"

        if [[ "${TARGET_DB}" != "${ORIGINAL_DB}" ||
              "$(realpath -m -- "${PRIVATE_MEDIA_TARGET}")" != "$(realpath -m -- "${ORIGINAL_PRIVATE_MEDIA_ROOT}")" ||
              "$(realpath -m -- "${NOTES_TARGET}")" != "$(realpath -m -- "${ORIGINAL_NOTES_ROOT}")" ]]; then
            die "--restore-env 只允许原拓扑恢复（原数据库名、PRIVATE_MEDIA_ROOT、NOTES_ROOT 必须保持不变）。新服务器/新路径请人工创建 .env。"
        fi
    fi
fi

# ==============================================================================
# 展示计划
# ==============================================================================

echo
echo "================================================================"
echo "TMS 恢复计划"
echo "================================================================"
echo "模式                : ${MODE}"
echo "备份                : ${BACKUP_DIR}"
echo "备份时间            : ${BACKUP_CREATED_AT:-unknown}"
echo "原数据库            : ${ORIGINAL_DB}"
echo "目标数据库          : $([[ "${SKIP_DB}" -eq 1 ]] && echo '[skip]' || echo "${TARGET_DB}")"

if [[ "${MODE}" == "drill" ]]; then
    echo "目标数据库 owner    : ${TARGET_DB_OWNER}"
fi

echo "恢复 PostgreSQL globals: $([[ "${RESTORE_GLOBALS}" -eq 1 ]] && echo YES || echo NO)"
echo "恢复文件            : $([[ "${SKIP_FILES}" -eq 1 ]] && echo NO || echo YES)"
echo "MEDIA target        : $([[ "${SKIP_FILES}" -eq 1 ]] && echo '[skip]' || echo "${MEDIA_TARGET}")"
echo "PRIVATE MEDIA target: $([[ "${SKIP_FILES}" -eq 1 ]] && echo '[skip]' || echo "${PRIVATE_MEDIA_TARGET}")"
echo "NOTES target        : $([[ "${SKIP_FILES}" -eq 1 ]] && echo '[skip]' || echo "${NOTES_TARGET:-included/not-present}")"

if [[ "${MODE}" == "drill" ]]; then
    echo "恢复源码快照        : $([[ "${SKIP_CODE}" -eq 1 ]] && echo NO || echo YES)"
    echo "演练目录            : ${RESTORE_ROOT}"
else
    echo "恢复 .env           : $([[ "${RESTORE_ENV}" -eq 1 ]] && echo "YES -> ${ENV_TARGET}" || echo NO)"
    echo "系统级配置          : 不自动覆盖 Samba / Nginx / systemd"
fi

echo "================================================================"

if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "dry-run 完成：未进行任何恢复写入。"
    exit 0
fi

confirm_restore

# ==============================================================================
# 准备恢复工作目录
# ==============================================================================

if [[ "${MODE}" == "drill" ]]; then
    prepare_isolated_dir "${RESTORE_ROOT}"
    install -d -m 0700 "${DRILL_PROJECT_DIR}"
else
    install -d -m 0700 "${RESTORE_ROOT}"
fi

REPORT="${RESTORE_ROOT}/restore-report.txt"

{
    echo "TMS restore report"
    echo "started_at=$(date --iso-8601=seconds)"
    echo "mode=${MODE}"
    echo "backup=${BACKUP_DIR}"
    echo "backup_created_at=${BACKUP_CREATED_AT}"
    echo "original_db=${ORIGINAL_DB}"
    echo "target_db=${TARGET_DB}"
    echo "media_target=${MEDIA_TARGET}"
    echo "private_media_target=${PRIVATE_MEDIA_TARGET}"
    echo "notes_target=${NOTES_TARGET}"
} > "${REPORT}"

# ==============================================================================
# drill：先恢复源码快照到隔离目录
# ==============================================================================

if [[ "${MODE}" == "drill" && "${SKIP_CODE}" -eq 0 ]]; then
    if [[ -f "${SOURCE_ARCHIVE}" ]]; then
        archive_is_safe "${SOURCE_ARCHIVE}" || die "源码归档路径检查失败"
        log "解压 TMS 源码快照 -> ${DRILL_PROJECT_DIR}"
        tar -xzf "${SOURCE_ARCHIVE}" -C "${DRILL_PROJECT_DIR}"
    else
        warn "未找到源码快照：${SOURCE_ARCHIVE}"
    fi
fi

# ==============================================================================
# PostgreSQL globals（仅 production + 显式）
# ==============================================================================

if [[ "${RESTORE_GLOBALS}" -eq 1 ]]; then
    [[ -f "${GLOBALS_SQL}" ]] || die "缺少 postgres-globals.sql"

    GLOBALS_TMP="$(mktemp /tmp/tms-postgres-globals.XXXXXX.sql)"
    TEMP_FILES+=("${GLOBALS_TMP}")
    install -o "${POSTGRES_OS_USER}" -g "${POSTGRES_OS_USER}" -m 0600 \
        "${GLOBALS_SQL}" "${GLOBALS_TMP}"

    log "恢复 PostgreSQL 全局对象（roles / tablespaces）……"
    if ! run_as_postgres psql \
        "${PG_ARGS[@]}" \
        --dbname=postgres \
        --no-psqlrc \
        --no-password \
        --set=ON_ERROR_STOP=1 \
        --file="${GLOBALS_TMP}"; then
        rm -f "${GLOBALS_TMP}"
        die "PostgreSQL globals 恢复失败"
    fi
    rm -f "${GLOBALS_TMP}"
fi

# ==============================================================================
# 数据库恢复
# ==============================================================================

if [[ "${SKIP_DB}" -eq 0 ]]; then
    if db_exists "${TARGET_DB}"; then
        if [[ "${FORCE}" -ne 1 ]]; then
            die "目标数据库已存在：${TARGET_DB}；请换 --target-db，或显式 --force"
        fi

        log "终止目标数据库 ${TARGET_DB} 的现有连接……"
        printf '%s\n' \
            "SELECT pg_terminate_backend(pid)
             FROM pg_stat_activity
             WHERE datname = :'target_db'
               AND pid <> pg_backend_pid();" \
            | run_as_postgres psql \
                "${PG_ARGS[@]}" \
                --dbname=postgres \
                --no-psqlrc \
                --no-password \
                --set=target_db="${TARGET_DB}" \
                -v ON_ERROR_STOP=1 \
                -q >/dev/null

        log "删除已有目标数据库：${TARGET_DB}"
        run_as_postgres dropdb \
            "${PG_ARGS[@]}" \
            --if-exists \
            "${TARGET_DB}"
    fi

    if [[ "${MODE}" == "drill" ]]; then
        if ! role_exists "${TARGET_DB_OWNER}"; then
            warn "目标 owner ${TARGET_DB_OWNER} 不存在，改用 ${PG_ROLE}"
            TARGET_DB_OWNER="${PG_ROLE}"
        fi

        log "创建演练数据库：${TARGET_DB}（owner=${TARGET_DB_OWNER}）"
        run_as_postgres createdb \
            "${PG_ARGS[@]}" \
            --template=template0 \
            --owner="${TARGET_DB_OWNER}" \
            "${TARGET_DB}"
    else
        log "创建生产恢复数据库：${TARGET_DB}"
        if [[ -n "${ORIGINAL_DB_USER}" ]] && role_exists "${ORIGINAL_DB_USER}"; then
            run_as_postgres createdb \
                "${PG_ARGS[@]}" \
                --template=template0 \
                --owner="${ORIGINAL_DB_USER}" \
                "${TARGET_DB}"
        else
            warn "原 Django DB role '${ORIGINAL_DB_USER}' 不存在；目标数据库将由 ${PG_ROLE} 创建。"
            warn "若要精确恢复 roles/owner，请重新执行并加入 --restore-globals。"
            run_as_postgres createdb \
                "${PG_ARGS[@]}" \
                --template=template0 \
                --owner="${PG_ROLE}" \
                "${TARGET_DB}"
        fi
    fi

    DUMP_TMP="$(mktemp /tmp/tms-restore.XXXXXX.dump)"
    TEMP_FILES+=("${DUMP_TMP}")
    install -o "${POSTGRES_OS_USER}" -g "${POSTGRES_OS_USER}" -m 0600 \
        "${DB_DUMP}" "${DUMP_TMP}"

    log "pg_restore -> ${TARGET_DB}"

    if [[ "${MODE}" == "drill" ]]; then
        RESTORE_ARGS=(
            --exit-on-error
            --no-owner
            --no-privileges
            --role="${TARGET_DB_OWNER}"
        )
    else
        # production 模式尽量保留 archive 中的 owner / ACL。
        # 若对应 roles 不存在，pg_restore 会明确失败，而不是静默改变权限语义。
        RESTORE_ARGS=(
            --exit-on-error
        )
    fi

    if ! run_as_postgres pg_restore \
        "${PG_ARGS[@]}" \
        --dbname="${TARGET_DB}" \
        --no-password \
        "${RESTORE_ARGS[@]}" \
        "${DUMP_TMP}"; then
        rm -f "${DUMP_TMP}"
        die "pg_restore 失败。目标数据库 ${TARGET_DB} 已保留，便于诊断。"
    fi

    rm -f "${DUMP_TMP}"

    log "执行 ANALYZE……"
    run_as_postgres psql \
        "${PG_ARGS[@]}" \
        --dbname="${TARGET_DB}" \
        --no-psqlrc \
        --no-password \
        -v ON_ERROR_STOP=1 \
        -c 'ANALYZE;' >/dev/null

    USER_TABLE_COUNT="$(
        run_as_postgres psql \
            "${PG_ARGS[@]}" \
            --dbname="${TARGET_DB}" \
            --no-psqlrc \
            --no-password \
            -Atqc "SELECT count(*)
                   FROM pg_tables
                   WHERE schemaname NOT IN ('pg_catalog', 'information_schema');"
    )"

    MIGRATION_COUNT="$(
        run_as_postgres psql \
            "${PG_ARGS[@]}" \
            --dbname="${TARGET_DB}" \
            --no-psqlrc \
            --no-password \
            -Atqc "SELECT CASE
                       WHEN to_regclass('public.django_migrations') IS NULL THEN -1
                       ELSE (SELECT count(*) FROM django_migrations)
                   END;"
    )"

    {
        echo "database_restored=yes"
        echo "target_db_owner=${TARGET_DB_OWNER:-archive/original}"
        echo "user_table_count=${USER_TABLE_COUNT}"
        echo "django_migration_count=${MIGRATION_COUNT}"
    } >> "${REPORT}"
fi

# ==============================================================================
# 文件恢复
# ==============================================================================

if [[ "${SKIP_FILES}" -eq 0 ]]; then
    if [[ "${MODE}" == "production" ]]; then
        if [[ -f "${MEDIA_ARCHIVE}" ]]; then
            prepare_production_dir "${MEDIA_TARGET}" "MEDIA_ROOT"
        fi

        if [[ -f "${PRIVATE_MEDIA_ARCHIVE}" ]]; then
            prepare_production_dir "${PRIVATE_MEDIA_TARGET}" "PRIVATE_MEDIA_ROOT"
        fi

        if [[ -f "${NOTES_ARCHIVE}" ]]; then
            prepare_production_dir "${NOTES_TARGET}" "NOTES_ROOT"
        fi
    else
        install -d -m 0750 "${MEDIA_TARGET}" "${PRIVATE_MEDIA_TARGET}"
        if [[ -f "${NOTES_ARCHIVE}" ]]; then
            install -d -m 0750 "${NOTES_TARGET}"
        fi
    fi

    if [[ -f "${MEDIA_ARCHIVE}" ]]; then
        extract_archive "${MEDIA_ARCHIVE}" "${MEDIA_TARGET}" "MEDIA_ROOT"
    else
        warn "备份中没有 media.tar.gz"
    fi

    if [[ -f "${PRIVATE_MEDIA_ARCHIVE}" ]]; then
        extract_archive "${PRIVATE_MEDIA_ARCHIVE}" "${PRIVATE_MEDIA_TARGET}" "PRIVATE_MEDIA_ROOT"
    else
        warn "备份中没有 media-private.tar.gz"
    fi

    if [[ -f "${NOTES_ARCHIVE}" ]]; then
        extract_archive "${NOTES_ARCHIVE}" "${NOTES_TARGET}" "独立 NOTES_ROOT"
    elif [[ -n "${NOTES_TARGET}" ]]; then
        log "NOTES_ROOT 已包含在 PRIVATE_MEDIA_ROOT 备份中：${NOTES_TARGET}"
    fi

    {
        echo "files_restored=yes"
        echo "media_target=${MEDIA_TARGET}"
        echo "private_media_target=${PRIVATE_MEDIA_TARGET}"
        echo "notes_target=${NOTES_TARGET}"
    } >> "${REPORT}"
fi

# ==============================================================================
# production：可选恢复 .env
# ==============================================================================

if [[ "${MODE}" == "production" && "${RESTORE_ENV}" -eq 1 ]]; then
    [[ -f "${BACKUP_ENV}" ]] || die "备份中不存在 config/.env"
    [[ -n "${ENV_TARGET}" ]] || die ".env 目标为空"
    [[ "$(basename "${ENV_TARGET}")" == ".env" ]] || \
        die "--env-target 必须指向名为 .env 的文件，避免误覆盖其他系统配置：${ENV_TARGET}"
    [[ ! -d "${ENV_TARGET}" ]] || die ".env 目标是目录：${ENV_TARGET}"

    install -d -m 0750 "$(dirname "${ENV_TARGET}")"

    if [[ -f "${ENV_TARGET}" ]]; then
        ENV_SAFETY="${ENV_TARGET}.before-restore-${TIMESTAMP}"
        log "保留现有 .env：${ENV_TARGET} -> ${ENV_SAFETY}"
        install -m 0600 "${ENV_TARGET}" "${ENV_SAFETY}"
    fi

    log "恢复 .env -> ${ENV_TARGET}"
    install -m 0600 "${BACKUP_ENV}" "${ENV_TARGET}"
    echo "env_restored=${ENV_TARGET}" >> "${REPORT}"
fi

# ==============================================================================
# 系统级配置提示
# ==============================================================================

if [[ -f "${BACKUP_DIR}/config/samba-passdb-export.txt" ||
      -f "${BACKUP_DIR}/config/smb.conf" ]]; then
    warn "备份包含 Samba 状态；本脚本不会自动导入 Samba 用户或覆盖 smb.conf。请按恢复演练文档人工处理。"
fi

if find "${BACKUP_DIR}/config" -maxdepth 1 -type f -name '*.service.txt' -print -quit 2>/dev/null | grep -q .; then
    warn "备份包含 systemd unit 参考文件；本脚本不会覆盖 /etc/systemd/system。"
fi

if [[ -f "${BACKUP_DIR}/config/nginx-config.txt" ]]; then
    warn "备份包含 Nginx 配置快照；本脚本不会覆盖当前 Nginx 配置。"
fi

# ==============================================================================
# 完成
# ==============================================================================

{
    echo "finished_at=$(date --iso-8601=seconds)"
    echo "status=success"
} >> "${REPORT}"

echo
log "============================================================"
log "TMS 恢复完成"
log "模式：${MODE}"
[[ "${SKIP_DB}" -eq 1 ]] || log "数据库：${TARGET_DB}"
if [[ "${MODE}" == "drill" ]]; then
    log "隔离目录：${RESTORE_ROOT}"
    log "源码/媒体：${DRILL_PROJECT_DIR}"
fi
log "恢复报告：${REPORT}"
log "============================================================"

if [[ "${MODE}" == "drill" ]]; then
    log "下一步：按恢复演练文档使用恢复后的数据库与文件执行 Django 应用级 smoke test。"
else
    warn "正式恢复后不要立即开放流量：先执行 Django check、关键业务抽查和文件下载验证。"
fi
