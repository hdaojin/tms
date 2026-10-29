# 内网服务器升级记录（2026-10-28）

## 目标与恢复边界

- 主机：`demo@10.21.57.72`（`server72`），严格校验 SSH 主机密钥。
- 原部署：`/srv/www/tms`，数据库 `tmsdb`，Nginx + Gunicorn，代码 `b343872fbf7fc48d25c0cd4c266470f1d888b883`。
- 目标代码：`e400da6343ec800a7dcf94f43860a78dcdd65a33`，按 `uv.lock` 安装生产依赖。
- 正式候选计划：`plan-20261028T045016Z-e400da6343ec`，release 为 `/srv/tms/releases/20261028T045016Z-e400da6343ec`。
- 源库不运行新版迁移；恢复副本转换后迁入全新 `tms` 库。开放写入后不自动回切旧库。

## 备份与文件

备份根目录为 `/var/backups/tms/internal-upgrade-20261028`，仅 root 可访问。独立副本暂缓；本机恢复验证通过后允许切换。

- `source/`：原站完整目录，包含公共/私有媒体、笔记、未跟踪文件、原配置和历史备份。
- `database-online.dump`：在线基线数据库备份，已恢复为 `tms_legacy_restore_online` 演练。
- `database-final.dump`：维护停写后的最终源库备份；正式转换使用其新的恢复副本。
- `postgres-globals.sql` 和最终角色归档：仅供服务器端恢复，不可输出认证内容。
- `config/system-recovery.tar`：原 systemd、Nginx、Samba、证书及续期任务等配置；`postgres-recovery.tar` 补充 PostgreSQL 配置。
- `config/samba-final.tar`：停止共享服务后的 Samba 账户库和配置；`postgres-tls.tar` 保存 PostgreSQL 引用的服务器证书。
- `database-new-verified.dump`、`config/new-deployment.tar`、`new-release-and-repository.tar`：开放写入前验证的新库，以及新版配置、依赖、静态文件和代码仓库恢复材料。
- `FILES_SHA256SUMS`：基线逐文件 SHA-256；最终清单单独保留。最终同步保留被替换和删除文件的旧版本。

媒体保留在原物理目录，以绑定挂载接入 `/srv/tms/shared/media` 和 `/srv/tms/shared/media-private`；`/etc/fstab` 保存挂载关系。Samba 原共享路径不变。保留原所有者，以 ACL 授予 tms 访问权限，明确拒绝 Caddy 访问私有目录；原 ACL 保存在 `media-acls.before`。

原环境及最终备份至少保留30天，不自动删除。**原路径下的媒体仍为活动数据，不能随旧代码一起删除。** 后续标准部署会要求另一个完整备份的空间；当前磁盘不能同时再容纳约738 GB媒体的额外完整副本。

## 数据转换

转换入口为 `scripts/migrate_internal_legacy.py`；服务器操作副本位于 `/var/lib/tms/internal-upgrade/`。默认预览，显式 `--apply` 才导入。源库名必须以 `tms_legacy_restore_` 开头；已存在活动 release 时必须进入维护状态。
此入口仅用于本次旧系统切换及隔离演练，不是日常同步工具；开放写入后不得用旧快照覆盖新库。服务器操作副本须显式设置 `TMS_RELEASE_DIR=/srv/tms/current`，并由受限的迁移环境加载器运行。

- 用户、密码哈希、账号状态、组、成员关系及稳定业务数据保留原主键。
- 奖惩、论坛、倒计时和反馈目录复用仓库历史迁移进行转换，只修改恢复副本。
- 权限以 `(app_label, model, codename)` 映射，不跨库复用数字 ID。将现有原生授权转为等价的显式授权，避免新版权限包展开后扩大权限。
- 缺少模块来源的179条 `assessments_score` 成绩完整归档，不虚构新版考核；200条旧后台操作日志也保留受限归档。原数据库完整备份保留原 ContentType 等解释信息。
- 逐表校验导入内容，报告记录数量、哈希、主键和权限映射；遇到字段不匹配或无等价权限时停止导入。
- 新库初始化默认目录使用 `bootstrap_tms` 普通模式，保留管理员已有配置，不使用 `--force`。

## 运行配置与验证

- Caddy 使用现有证书，`tms.itnsa.cn`、`outside.itnsa.cn` 通过正常 TLS 校验；acme.sh 续期使用受控的 `tms-deploy tls install` hook。
- `/etc/tms/deploy.conf` 设置 `TMS_DEPLOY_USER=demo`、`TMS_TLS_MODE=acme-sh`、`TMS_BASIC_AUTH_ENABLED=0`。服务器安装模板保留原 HTTPS 兜底路由、HTTP 301跳转及4 GiB请求体上限；主配置关闭自动签发，以 `default_sni`、`fallback_sni` 选择原证书。其他旧域名及IP仍保留原证书不匹配的限制，兼容性已在仅回环的测试端口验证。`fallback_sni` 是当前 Caddy 支持的实验选项，今后升级需保留配置校验和入口测试。
- 发布依赖安装显式使用 `--link-mode copy`。否则 uv 缓存的硬链接会随不可变 release 的 chown/chmod 一起变化，破坏下一次部署。已修复 TMS 专用缓存归属，并确认新候选依赖与缓存无共享 inode、缓存文件没有意外归 root。
- 维护检查与业务路由放在同一 `route` 内，固定执行顺序；修复旧模板的 `handle` 先于维护响应执行问题。隔离端口及正式入口均实测维护时返回503。
- `demo` 目录内误归 root 的 Git 私钥调整为 `demo:demo 0600`，未复制或生成密钥；已验证 demo 严格校验主机密钥的 Git 访问。
- 保留原 SECRET_KEY 以维持会话和加密兼容。`check --deploy` 的原密钥长度及 HSTS 警告已记录，未静默轮换密钥。
- 已完成恢复副本演练、重复转换、权限零漂移检查、119次页面请求检查及69个文件的存在性和运行用户读取检查。
- 本地全量测试608通过、32跳过；启用 Git Bash 后部署专项测试33通过、1跳过；转换入口保护测试3通过；Ruff、Django check 和迁移漂移检查通过。

## 故障恢复

开放写入之前失败，停止候选/Caddy，恢复备份的 Nginx 和旧 tms.service 配置，重新启动旧站及 Samba；源 `tmsdb` 和原文件路径仍在，不倒迁移。

开放写入之后失败，先创建 `/var/lib/tms/maintenance.flag` 并停止写入，保全新库和新增文件，优先前滚修复。不得直接回切旧库覆盖新数据；任何完整恢复都须先评估维护窗口后新增的数据。

完整命令日志、转换报告、恢复验证及最终验收结果保留在服务器 root-only 的 `/var/lib/tms/internal-upgrade/`。本文不包含凭据或个人数据。
最终转换明细为 `/var/backups/tms/internal-upgrade-20261028/final-conversion/report.json`，两个历史数据导出与其同目录；验收摘要为 `/var/lib/tms/internal-upgrade/final-summary.json`。

## 最终结果

- 2026-10-28 12:51:39（Asia/Shanghai）切换完成，最后一次维护窗口为12:51:22–12:51:39，约17秒。
- 两次前置验收触发保护回退：一次为恢复管道 SIGPIPE 误判，另一次为维护响应顺序错误。分别改用直接文件输入及固定路由顺序后通过；第二次时段只有15次本机 GET，没有外部请求。原库未迁移或清空。
- 13982个文件已生成 SHA-256；7个样本实际恢复，源文件、备份、恢复件的哈希一致，恢复件的所有者和 ACL 一致。最终归档校验全部通过。
- 新库保留21用户、4组、26成员关联、51组权限、25通知及32附件、25会议、43纪律记录、920术语、1230学习答题、99论坛帖子及99翻译。
- 新版服务为 `tms` 用户、回环8010；Caddy、PostgreSQL、Samba 均正常，Nginx 停止并禁用启动。`tms-deploy verify --json` 返回 `ok=true`。
- 对活动 release 的1039个受 Git 跟踪文件逐一计算 blob 哈希，全部匹配固定提交，无内容差异；服务重启次数为0。
- Windows 客户端对两个证书域名以指定源站IP验证 HTTPS，均返回200；Windows UNC 实际创建、读取、删除共享验证文件成功。公共文件通过 HTTPS 下载后的 SHA-256 与备份一致。
- 仅清理了本次创建的4个临时候选目录。原生产代码、原库、全部媒体和完整备份保留；未运行全机 `apt autoremove`，未删除 Nginx 软件包。
- 本机剩余空间约166 GiB；独立副本尚未制作。后续更新前需落实另一份完整备份的存储空间。
