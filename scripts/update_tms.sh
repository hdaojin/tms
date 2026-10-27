#!/usr/bin/env bash
# Installed root-owned as /usr/local/sbin/tms-update.
# Code updates reuse the reviewed deployment entrypoint and immutable releases.
set -Eeuo pipefail

case "${1:-}" in
    -h|--help|help|'')
        cat <<'EOF'
用法：
  tms-update plan [--revision develop] [--json]
  tms-update apply PLAN_ID --confirm-sha FULL_SHA
  tms-update verify [--json]
  tms-update status [--json]

plan 固定完整 SHA；apply 执行备份、迁移、切换和验收。
Python 依赖按新 release 的 uv.lock 同步；npm 产物随代码发布。
首次安装请使用 tms-deploy plan --first-install。
EOF
        exit 0 ;;
    plan|apply|verify|status) ;;
    *) printf '不支持的更新命令：%s\n' "$1" >&2; exit 2 ;;
esac
for argument in "$@"; do
    [[ "${argument}" != --first-install ]] || { printf '更新入口不支持 --first-install。\n' >&2; exit 2; }
done
readonly DEPLOY=/usr/local/sbin/tms-deploy
[[ -x "${DEPLOY}" && "$(stat -c '%U' "${DEPLOY}")" == root ]] || {
    printf '请先安装 root 所有的稳定部署入口 %s。\n' "${DEPLOY}" >&2
    exit 1
}
exec "${DEPLOY}" "$@"
