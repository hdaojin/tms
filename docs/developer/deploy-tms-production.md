# TMS 生产自动化部署手册

已通过 `ecs-user` 登录公网服务器、需要逐步照着操作时，参见
[TMS 公网服务器首次部署操作指南](deploy-tms-public-first-install.md)。

本文描述公网和内网全新服务器上的人工审核式自动化部署。它不是“复制命令即无条件执行”的安装器：
只读检查、候选计划和实际变更是三个独立阶段，每个远程写操作仍须由运维人员单独确认。

仓库中的脚本和模板不会自动连接服务器。部署前必须在服务器重新执行 `inspect`，不能把本文记录的环境快照当作当前事实。

## 1. 已知环境与边界

方案设计时只读确认的远端环境为 Debian 13.7、2 核、约 1.6 GiB 内存、无 swap、约 25 GiB 可用空间，
并已安装 Python 3.13.5、uv 0.13.4、PostgreSQL 17.11 和 Caddy 2.11.7。
服务器尚无 TMS 账户、目录、数据库或服务。现有 Caddy 站点 `share.itnsa.cn` 必须保留。

生产入口通过 `TMS_DOMAIN` 配置（公网示例 `test.itnsa.cn`，内网示例 `tms.itnsa.cn`），站点外层启用 Caddy Basic Auth。发布来源通常为远端
`develop`，但 `plan` 会把它解析为完整 40 位 SHA，`apply` 只接受该精确 SHA。

本方案不使用 Docker，不在服务器构建前端，不自动删除备份，也不自动执行数据库逆向迁移。
只考虑全新部署，不处理 Nginx 的停机、迁移或端口交接。上述环境快照只属于原公网服务器，不能套用到新的内网主机。

## 2. 架构和信任边界

```text
Internet -> Caddy :443 -> Basic Auth
                         |-- /static/* -> /srv/tms/current/staticfiles
                         |-- /media/*  -> /srv/tms/shared/media
                         `-- other     -> 127.0.0.1:8010 -> Gunicorn/Django

PostgreSQL 127.0.0.1:5432
  tms_app      -> 运行期 DML，无 schema 修改权限
  tms_migrator -> 数据库/schema 所有者，只在部署迁移时使用
```

关键路径：

| 路径 | 所有者/用途 |
| --- | --- |
| `/srv/tms/repository.git` | `ecs-user` 维护的裸仓库，复用其已有 GitHub SSH 权限 |
| `/srv/tms/releases/<UTC时间>-<SHA前12位>` | root 所有的不可变代码、`.venv` 和 `staticfiles` |
| `/srv/tms/current` | root 原子切换的活动 release 软链接 |
| `/srv/tms/shared/media` | `tms:caddy`，目录 setgid，应用写、Caddy 只读 |
| `/srv/tms/shared/media-private` | `tms:tms`，仅应用访问，绝不配置 Caddy 路由 |
| `/etc/tms/tms.env` | `root:tms 0640`，systemd 运行配置和应用数据库凭据 |
| `/etc/tms/migrate.env` | `root:root 0600`，迁移数据库凭据 |
| `/var/lib/tms` | 计划、维护标志和部署状态 |
| `/var/backups/tms` | root-only 完整备份；部署不会自动清理 |

Gunicorn 由无登录 shell、无 sudo 的系统用户 `tms` 运行，只监听 `127.0.0.1:8010`。
release 中的业务代码为 `root:tms`，运行用户只读；`staticfiles` 为 `root:caddy`，Caddy 只读。
公共上传目录使用 `0027` umask、目录 `2750`、文件 `0640`；私有上传目录为目录 `0750`、文件 `0640`。

`ecs-user` 继续作为人工和 AI 的 SSH 运维入口。本次不修改其已有 SSH 设置或 `NOPASSWD: ALL`。
后者权限很大，应作为独立安全改造收紧为经审核的命令白名单，不能夹带在首次部署中变更。

## 3. 稳定部署入口的安装

先检出并人工审查准备部署的代码。不要直接用 `sudo` 执行浮动 `develop` 中的脚本；将审查过的版本安装为 root 所有的稳定入口：

```bash
cd /path/to/reviewed/tms
sudo install -d -m 0755 /usr/local/share/tms-deploy
sudo install -m 0755 scripts/deploy_tms.sh /usr/local/sbin/tms-deploy
sudo install -m 0755 scripts/update_tms.sh /usr/local/sbin/tms-update
sudo install -m 0644 deploy/production/tms.service /usr/local/share/tms-deploy/tms.service
sudo install -m 0644 deploy/production/tms.caddy /usr/local/share/tms-deploy/tms.caddy
sudo install -d -m 0750 /etc/tms
sudo install -m 0640 deploy/production/deploy.conf.example /etc/tms/deploy.conf
sudo chown root:root /etc/tms/deploy.conf
```

审阅 `/etc/tms/deploy.conf`。它只能保存域名、仓库、账户名等非秘密拓扑参数；数据库密码和 Django `SECRET_KEY`
由首次 `apply` 生成，不能复制进部署配置、命令行、日志或版本库。

公网设置 `TMS_TLS_MODE=automatic`；内网设置 `TMS_TLS_MODE=acme-sh`。
内网必须先完成第 12 节的 acme.sh 初始化和证书安装，再运行首次 `plan`。
内网运维入口通常还需设置 `TMS_DEPLOY_USER=demo`；Git SSH 密钥使用该用户现有环境。

更新稳定入口时，重复人工审查和上面的 `install`。已有 plan 会绑定脚本、配置和两个模板的 SHA-256；
任一文件变化后旧 plan 都会被拒绝，必须重新生成。

## 4. 命令模型和退出行为

```text
tms-deploy inspect [--json]
tms-deploy plan [--revision develop] [--first-install] [--json]
tms-deploy apply <plan-id> --confirm-sha <完整SHA>
tms-deploy verify [--json]
tms-deploy status [--json]
tms-deploy rollback --to <release-id>
tms-deploy auth add|remove|list [用户名]
tms-deploy admin create
tms-deploy prune --keep 5 [--yes]
tms-deploy tls configure-acme|install|check
```

- `inspect` 严格只读，不创建目录，不加载会执行 shell 的部署配置。
- `plan` 会写裸仓库、候选 release 和 root-only 计划文件，因此仍是远程写操作，必须单独确认。
- `apply` 校验计划文件哈希、脚本/配置/模板哈希、候选 SHA、路径和空间；任何漂移立即停止。
- 正常结果退出码为 0，输入、校验或阶段失败为非 0；脚本使用 `set -Eeuo pipefail`，失败后不会继续后续阶段。
- `--json` 将最终机器可读结果写到标准输出，阶段日志写到标准错误，便于 AI 分离读取。

`plan` 执行：严格 SSH host key 检查并获取远端引用、固定 SHA、`git archive`、
`uv sync --locked --no-dev --python /usr/bin/python3.13`、前端产物存在性检查、Django check、
`check --deploy`、迁移漂移检查、迁移计划和 `collectstatic`。服务器不需要 Node/npm，`static/css/output.css`
与 `static/vendor/` 必须已经提交。

## 5. 首次部署

每个编号步骤都应先展示命令和影响，再取得明确确认。

1. 只读检查并保存输出：

   ```bash
   sudo tms-deploy inspect
   sudo tms-deploy inspect --json
   ```

   核对系统版本、空间、swap、Python、uv、PostgreSQL、Caddy、监听地址和现有站点。
   另行查看 `/etc/caddy/Caddyfile`，确认 `share.itnsa.cn` 仍存在且没有路径冲突。

2. 准备首次安装计划（会写候选目录，不会创建数据库、切换服务或修改 Caddy）：

   ```bash
   sudo tms-deploy plan --revision develop --first-install
   ```

   记录输出中的 `plan_id`、完整 `sha` 和 manifest 哈希。审阅候选 release 内的
   `.tms-check-deploy.txt` 与 `.tms-migration-plan.txt`；逐项判断 `check --deploy` 警告。

3. 在 TTY 中添加至少一个外层认证用户：

   ```bash
   sudo tms-deploy auth add operator
   sudo tms-deploy auth list
   ```

   密码隐藏读取，至少 8 个字符；脚本调用 `caddy hash-password --algorithm argon2id`，只保存用户名和哈希。

4. 再次确认实际变更后应用计划：

   ```bash
   sudo tms-deploy apply plan-YYYYMMDDTHHMMSSZ-aaaaaaaaaaaa \
     --confirm-sha aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
   ```

   首次 `apply` 会：在确认当前确实没有 swap 且 `/swapfile` 不冲突后创建 2 GiB swap；创建 `tms` 系统账户、
   共享目录和秘密；建立双 PostgreSQL 角色；只向 Caddy 主配置追加一次
   `import /etc/caddy/sites-enabled/*`（并先备份原文件）；验证 systemd/Caddy；进入维护；执行迁移；
   依次运行 `bootstrap_tms --dry-run` 与 `bootstrap_tms --yes`；原子切换 release；启动并做本机健康检查。

5. 验证，再人工创建 Django 超级管理员：

   ```bash
   sudo tms-deploy verify
   sudo tms-deploy admin create
   ```

   应用内业务角色继续使用 Django Group、权限包和 `TechnicalDomainGroupScope`。脚本不猜测业务组织、
   不自动创建 Group，也不把普通用户提升为超级管理员。

## 6. 日常升级

```bash
sudo tms-deploy inspect
sudo tms-deploy plan --revision develop
# 审核 plan_id、完整 SHA、check --deploy 和迁移计划
sudo tms-deploy apply <plan-id> --confirm-sha <完整SHA>
sudo tms-deploy verify
sudo tms-deploy status
```

非首次 `apply` 在任何活动变更前调用当前 release 的 `scripts/backup_tms.sh`，传入：

```text
PROJECT_DIR=/srv/tms/current
BACKUP_ROOT=/var/backups/tms
ENV_FILE=/etc/tms/tms.env
APP_OS_USER=tms
INCLUDE_GIT_BUNDLE=0
```

脚本要求新备份出现、`SHA256SUMS` 全部通过，并用 `pg_restore --list` 读取 PostgreSQL custom dump。
空间不足或验证失败时停止，不进入维护、不停止 Gunicorn。备份不会被自动删除。

随后创建维护标志、停止 Gunicorn、用 `tms_migrator` 迁移、重新投影现有表/序列权限、原子切换、启动和检查。
若没有待执行迁移且健康检查失败，自动恢复上一 `current` 链接；若检测到并执行了迁移，则保持维护状态，
不自动倒迁移、不切回旧代码、不恢复备份，只报告失败供前滚修复或完整恢复。

## 7. Basic Auth 管理

```bash
sudo tms-deploy auth add alice
sudo tms-deploy auth list
sudo tms-deploy auth remove alice
```

每次改动先重建独立 Caddy 片段，再 `caddy validate`，成功后才 reload。脚本禁止删除最后一个认证用户。
认证文件不含明文密码。不要把哈希粘贴到工单、聊天或版本库；哈希虽不是明文，仍属于认证数据。

### 按客户端来源网段决定是否需要 Basic Auth

默认 `TMS_BASIC_AUTH_TRUSTED_CIDRS=""`，所有客户端都需要 Basic Auth。
如服务器是 `10.21.57.72`，且经确认其可信局域网为 `/24`，可在 `/etc/tms/deploy.conf` 配置：

```bash
TMS_BASIC_AUTH_TRUSTED_CIDRS="10.21.57.0/24"
# 多个网段用空格分隔，也支持 IPv6，例如：
# TMS_BASIC_AUTH_TRUSTED_CIDRS="10.21.57.0/24 fd12:3456:789a::/64"
```

此时 `10.21.57.x` 跳过外层 Basic Auth，其他来源仍需认证。Django 登录、CSRF 和业务权限均保持生效。
不能仅根据服务器 IP 推断掩码：`10.21.57.72` 不一定属于 `/24`，应按实际网络和信任范围配置。
不会自动豁免所有私网、服务器所有接口网段或回环地址。单个客户端使用 `/32`（IPv4）或 `/128`（IPv6）。
非法 CIDR、带主机位的网络地址和配置注入字符会在计划阶段被拒绝。

Caddy 最终使用如下 matcher，认证用户名/哈希仍存放于独立文件：

```caddy
@tms_basic_auth not remote_ip 10.21.57.0/24
basic_auth @tms_basic_auth argon2id {
    # 用户名和密码哈希
}
```

判断依据是 Caddy 的 `remote_ip`，即直接连接的来源 IP，不根据客户端提交的 `X-Forwarded-For` 跳过认证。
适用于客户端直连 Caddy。若前置了 CDN、另一层反向代理或会改变源地址的 SNAT，Caddy 看到的可能是中间设备；
不要直接把其网段加入豁免列表，否则经该设备进入的外部请求也可能被豁免。
这种拓扑须另行设计可信代理与 `client_ip`，当前脚本不自动信任转发头。
官方说明：[remote_ip matcher](https://caddyserver.com/docs/caddyfile/matchers#remote-ip)。

修改配置后重新生成并审核 plan，再 apply，不能仅执行 `auth add` 来更新网段策略。
plan 会展示豁免网段，配置哈希变化会使旧计划失效。即使配置了可信网段，仍需至少保留一个 Basic Auth 用户。

验收应分别从可信网段和非可信网段访问：前者进入 Django 登录流程，后者未提供认证应返回 401；
非可信客户端伪造 `X-Forwarded-For: 10.21.57.1` 仍应返回 401。

## 8. 权限与数据库验收

`sudo tms-deploy verify` 覆盖基础服务、回环监听、目录隔离、Django check、数据库 schema 权限探测，
并以配置域名和 SNI 访问本机 Caddy，要求证书信任校验通过且响应符合来源网段策略。默认未认证返回 401；
若显式豁免了回环地址，则检查 Django 的 200/302，维护期间检查 503。不会使用 `--insecure`。
仍需人工完成公网功能验收：

1. `http://test.itnsa.cn` 自动跳转 HTTPS，证书域名匹配。
2. 非可信网段无 Basic Auth 返回 401；可信网段跳过 Basic Auth。认证后首页、登录页、CSS/JS 与一项公共媒体访问正常。
3. 私有附件只能经过 Django 权限检查，不存在 `/media-private/` 静态路由。
4. 完成登录、一个 CSRF POST、退出、公共上传和私有下载的最小冒烟测试。
5. `ss -ltnp` 证明 Gunicorn 仅监听回环 `8010`，PostgreSQL 仅监听回环 `5432`。
6. `tms` 不能修改 release；Caddy 可读取 static/public media，但不能读取 private media、环境文件和备份。
7. `tms_app` 的正常业务 DML 成功，`CREATE/ALTER TABLE` 失败；迁移命令使用 `tms_migrator` 成功。

“SSH 成功”或“service active”都不能单独作为验收成功。

## 9. 备份、恢复和回滚

手工备份可在维护窗口使用与自动升级相同的参数调用：

```bash
sudo env PROJECT_DIR=/srv/tms/current \
  BACKUP_ROOT=/var/backups/tms \
  ENV_FILE=/etc/tms/tms.env \
  APP_OS_USER=tms \
  INCLUDE_GIT_BUNDLE=0 \
  /srv/tms/current/scripts/backup_tms.sh
```

备份和恢复细节见 [backup-tms.md](backup-tms.md) 与
[TMS-backup-restore-drill.md](TMS-backup-restore-drill.md)。恢复前必须把备份复制到隔离环境演练，核对归档校验、
PostgreSQL 版本、环境文件、公共/私有媒体和恢复后的权限。生产完整恢复是独立破坏性操作，不由部署脚本自动执行。

只有当前部署状态明确记录“未执行迁移”时，才允许代码级回滚：

```bash
sudo tms-deploy rollback --to <release-id>
```

执行过迁移时必须选择前滚修复，或进入经审核的完整数据库/文件恢复流程。不要用旧代码连接已迁移数据库碰运气。

旧 release 默认保留至少 5 个。清理先展示候选，交互输入 `DELETE`，或在已审阅候选后显式使用 `--yes`：

```bash
sudo tms-deploy prune --keep 5
```

该命令不删除备份。

## 10. 故障处理

- **auth add 报 `ERROR EOF`**：旧入口向 `caddy hash-password` 传密码时缺少行末换行。
  更新已审阅的部署脚本并重新安装 `/usr/local/sbin/tms-deploy`，再执行 `auth add`；无需删除账户文件或重装 Caddy。
  如果已经生成 plan，更新入口后必须重新生成 plan，因为原计划绑定了旧脚本的哈希。

- **plan 报 SSH 或 host key 错误**：以 `ecs-user` 使用 BatchMode、StrictHostKeyChecking 和 10 秒超时单独验证 GitHub；
  不要临时关闭 host key 检查。
- **计划漂移**：脚本、配置、模板或候选 SHA 任一哈希变化都重新 `plan`，不要编辑 manifest 绕过。
- **Caddy validate 失败**：保留现有 `share.itnsa.cn`，检查独立站点和 Basic Auth 片段；验证成功前不 reload。
- **迁移后健康检查失败**：维护标志会保留。查看 `journalctl -u tms.service` 和迁移记录，优先前滚修复；需要恢复时走完整恢复演练。
- **无迁移但切换失败**：脚本会尝试恢复旧链接；仍须检查旧服务健康与外部 HTTPS。
- **空间不足**：清理应由独立人工决策完成。部署脚本不会删除备份；release 只通过 `prune` 删除。
- **swap 冲突**：已有 swap、`/swapfile` 已存在未启用或 `/etc/fstab` 校验失败时停止，先人工确认现状。
- **首次安装中断**：若两个环境文件、两个数据库角色和目标数据库都完整，重复同一 `apply` 会复用该恢复点；任何只完成一部分的状态都会停止。此时先离线核对数据库、文件权限和日志，不要直接删除角色、数据库或秘密后盲目重试。

HSTS 首发为 3600 秒，不含子域、不预加载。只有在 HTTPS、证书续期、所有必要子域和恢复流程稳定后，
才人工把 `SECURE_HSTS_SECONDS` 提升为 `31536000`；是否启用 includeSubDomains/preload 是独立高风险决策。

## 11. AI 执行协议

AI 可以读取本手册并组织命令，但授权必须逐阶段取得：

1. `inspect`：只读，可直接执行并分别报告连接、远端退出码和功能结果。
2. `plan`：先展示 revision、将写入的裸仓库/候选/计划路径，获得明确确认后执行。
3. `apply`：展示 plan id、完整 SHA、备份、swap/账户/数据库/Caddy/systemd/迁移/重启影响，再次明确确认。
4. `auth`、`admin`、`rollback`、`prune`：每类都属于独立写操作，不能沿用 `apply` 的授权。
5. 任何安装软件、写文件、建用户/数据库、迁移、reload、restart、swap 或权限变更都不能由一次旧确认无限扩张。

AI 不得读取、回显或记录 `/etc/tms/*.env` 的秘密值；不得把 Basic Auth 密码放在命令参数；不得关闭 SSH 严格主机密钥检查。

## 12. 公网和内网 HTTPS

### 12.1 公网：Caddy 自动签发和续期

`/etc/tms/deploy.conf`：

```bash
TMS_DOMAIN=test.itnsa.cn
TMS_TLS_MODE=automatic
```

域名的公网 A/AAAA 记录须正确指向服务器，公网 ACME 验证请求应能通过 80/443 到达 Caddy。
服务器还需要访问 ACME 服务。模板不指定证书文件，Caddy 使用 Automatic HTTPS 自动签发和续期。
NAT 场景需要配置相应端口转发。仅允许出站连接、或公网 DNS 直接解析为 `10.x`，不满足默认公网验证条件。

官方说明：[Automatic HTTPS](https://caddyserver.com/docs/automatic-https)。

### 12.2 内网：acme.sh DNS-01 + Caddy 加载公网可信证书

适用于 `tms.itnsa.cn` 解析到 `10.21.57.72`、服务器可以访问外网和阿里云 DNS API 的场景。
公网 CA 验证 DNS TXT 记录，不要求访问内网服务器；客户端使用域名访问，证书信任不依赖服务器是否有公网 IP。
本方案采用现有的 acme.sh，不需要给 Caddy 编译 DNS Provider 插件，也不使用 `tls internal`。

部署配置示例：

```bash
TMS_DOMAIN=tms.itnsa.cn
TMS_DEPLOY_USER=demo
TMS_TLS_MODE=acme-sh
TMS_ACME_USER=demo
TMS_ACME_HOME=/home/demo/.acme.sh
TMS_ACME_DOMAIN=tms.itnsa.cn
TMS_ACME_ECC=1
```

`TMS_ACME_DOMAIN` 是 acme.sh 保存订单的主域名，可以与站点域名不同，但证书 SAN 必须覆盖 `TMS_DOMAIN`。
ECDSA 证书设置 `TMS_ACME_ECC=1`；已有 RSA 证书设置为 `0`。
站点域名和证书模式应在首次部署前确定；现有部署更换域名还须单独同步运行环境的 `ALLOWED_HOSTS` 和 CSRF origins。

### 12.3 首次安装 acme.sh 和签发证书

以下命令由证书维护用户 `demo` 执行。若该用户已有可用 acme.sh 和订单，跳过安装与重新签发，直接配置安装 hook。
部署脚本不自动安装 acme.sh、不创建 DNS API 凭据、不自动发起首次签发。

```bash
# 在 demo 用户自己的工作目录中下载并审阅官方安装器，然后安装
umask 077
git clone --depth 1 https://github.com/acmesh-official/acme.sh.git acme.sh-source
cd acme.sh-source
./acme.sh --install -m <运维邮箱>
```

确认 `/home/demo/.acme.sh/acme.sh` 存在，并通过 `crontab -l` 确认安装器已经添加续期任务，不要重复添加。
服务器需要正确时间、CA 信任库和能访问 DNS API/ACME 服务的网络。

阿里云示例：先创建专用 RAM 用户及最小必要的 DNS 查询/记录维护权限，避免使用主账号 AccessKey。
具体权限以官方 dns_ali 文档和云服务商能力为准。用交互方式读取凭据，避免进入 shell history：

```bash
umask 077
read -r -s -p 'Ali_Key: ' Ali_Key; printf '\n'
read -r -s -p 'Ali_Secret: ' Ali_Secret; printf '\n'
export Ali_Key Ali_Secret
/home/demo/.acme.sh/acme.sh --issue --home /home/demo/.acme.sh \
  --server letsencrypt --dns dns_ali --keylength ec-256 -d tms.itnsa.cn
unset Ali_Key Ali_Secret
chmod 0700 /home/demo/.acme.sh
chmod 0600 /home/demo/.acme.sh/account.conf
```

acme.sh 会把 DNS 凭据保存到用户的账户配置，以便 cron 自动续期。这些文件必须由维护用户独占，
不可让 `tms` 或 `caddy` 读取，也不可放入仓库或部署日志。不要开启会打印凭据的 shell tracing。
如域名设置了 CAA，需要允许所选签发机构。

官方指引：

- [安装 acme.sh](https://github.com/acmesh-official/acme.sh/wiki/How-to-install)
- [DNS API / Aliyun dns_ali](https://github.com/acmesh-official/acme.sh/wiki/dnsapi#11-use-aliyun-domain-api-to-automatically-issue-cert)
- [选择 CA](https://github.com/acmesh-official/acme.sh/wiki/Server)
- [证书安装与 reload hook](https://github.com/acmesh-official/acme.sh#3-install-the-cert-to-apachenginx-etc)

### 12.4 安装证书与自动续期 hook

先按第 3 节安装 root 所有的稳定入口，设置好部署配置，并确认 `caddy` 用户/组已经由 Caddy 软件包创建。
然后执行：

```bash
sudo tms-deploy tls configure-acme
sudo tms-deploy tls check
sudo tms-deploy plan --revision develop --first-install
```

`configure-acme` 不发起签发。它调用已有订单的 `--install-cert`，设置完整证书链和私钥的安装路径，
并将 `sudo -n /usr/local/sbin/tms-deploy tls install` 保存为安装后的 reload hook。
它会安装一条经 `visudo` 校验的 sudoers 规则，只允许证书维护用户免密码执行该精确命令。
该命令只读取 root 管理的固定配置、从固定暂存路径复制证书、校验并重新加载 Caddy，不能由参数指定任意安装目标。

证书流转如下：

```text
acme.sh 订单（demo 独占，含 DNS 凭据）
  -> /var/lib/tms-acme/incoming/{fullchain.pem,privkey.pem}（demo 独占）
  -> root hook：复制后校验域名、至少 24h 有效期、密钥匹配、系统 CA 信任链
  -> /etc/caddy/certs/tms/cert-XXXXXXXX/（root:caddy，目录 0750、文件 0640）
  -> 原子切换 /etc/caddy/certs/tms/current
  -> caddy validate -> caddy reload --force
```

root hook 使用文件锁避免并发安装。校验失败不会替换现有证书；Caddy 校验/reload 失败时恢复原证书链接，
并输出错误供运维检查。版本目录保留作追溯，不能把包含私钥的目录发布或提交。
首次站点尚未配置时只安装证书，之后 `apply` 会验证并启动/reload Caddy。

Caddy 模板最终类似：

```caddy
tms.itnsa.cn {
    tls /etc/caddy/certs/tms/current/fullchain.pem /etc/caddy/certs/tms/current/privkey.pem
    # Basic Auth、静态文件与反向代理按生产模板配置
}
```

已有订单的 `--install-cert` 参数会被更新；本手册面向全新部署，不协调旧 Nginx 的安装路径或 reload hook。
不要直接让 Caddy读取 `/home/demo/.acme.sh`，也不要把私钥改成 everyone-readable。
不要在证书续期前后停止整个 Web 服务。

保留正常 cron，例如：

```bash
touch /home/demo/acme-renew.log
chmod 0600 /home/demo/acme-renew.log
```

```cron
4 20 * * * /home/demo/.acme.sh/acme.sh --cron --home /home/demo/.acme.sh >> /home/demo/acme-renew.log 2>&1
```

日志文件应为 `0600` 并配置轮转/告警。正常 `--cron` 只在需要时续期，成功后自动安装并调用 hook。
日常检查可手工运行同一 cron 命令并查看退出码；无需例行 `--force` 续期，以免触发 CA 频率限制。
部署脚本校验证书有效性，但不会替代续期失败告警；应监控到期时间和 cron 日志。

`tms-deploy tls install` 可重新导入已写好的暂存证书；`tls check` 只读校验已安装证书。
切换 TLS 模式、证书主域名或 acme.sh home 后应重新审查配置；`automatic` 模式不使用上述 hook。

## 13. 依赖和 TMS 更新

### 13.1 开发机更新 Python/npm 依赖

新增跨平台维护脚本 `scripts/update_dependencies.py`，用 uv 运行：

```bash
uv run --locked --no-sync scripts/update_dependencies.py python --dry-run
uv run --locked --no-sync scripts/update_dependencies.py npm --dry-run
uv run --locked --no-sync scripts/update_dependencies.py all --dry-run

# 在干净的开发工作区执行所需的一项
uv run --locked --no-sync scripts/update_dependencies.py python
uv run --locked --no-sync scripts/update_dependencies.py npm
uv run --locked --no-sync scripts/update_dependencies.py all
```

`--dry-run` 只显示命令，即使工作区不干净也可查看。实际更新要求没有未提交修改或未跟踪文件，
不能在生产 release 中运行；不提供自动 stash、reset、提交、推送或远程执行。
失败时停止并保留变更，供人工检查。

- Python：`uv lock --upgrade` 按 `pyproject.toml` 已声明的约束更新，再 `uv sync --locked`；
  随后执行锁文件、Ruff、Django、迁移漂移和完整 pytest 检查。
- npm：`npm update --package-lock-only --include=dev` 更新锁文件，`npm ci --include=dev` 按新锁文件安装，
  然后完整同步第三方资源、构建 CSS 并执行前端聚焦测试。
- 全部：先更新 Python 锁文件/环境，再更新 npm 和静态产物，最后执行后端检查。

更新范围由现有依赖声明决定。`>=` 这类没有上限的 Python 约束可能允许未来主版本升级；
脚本不会自动修改业务代码或生成迁移来掩盖兼容问题，也不自动提升 npm 的 semver 上限。
审阅 `uv.lock`、`package-lock.json`、可能变化的包元数据和静态产物，再人工提交/推送。
官方说明：[uv 更新依赖](https://docs.astral.sh/uv/concepts/projects/sync/#upgrading-locked-package-versions)、
[npm update](https://docs.npmjs.com/cli/commands/npm-update)、[npm ci](https://docs.npmjs.com/cli/commands/npm-ci)。

### 13.2 服务器更新 TMS 代码

独立入口 `/usr/local/sbin/tms-update` 是稳定部署命令的薄封装：

```bash
sudo tms-update plan --revision develop
sudo tms-update apply <plan-id> --confirm-sha <完整SHA>
sudo tms-update verify
sudo tms-update status
```

它只开放更新相关命令，不接受 `--first-install`。仍须人工审阅 SHA 和迁移计划；不会直接 `git pull` 当前代码。
新 release 自动按其 `uv.lock` 安装运行依赖，前端使用随代码提交的构建产物。
备份、维护、迁移、原子切换和失败处理全部复用 `tms-deploy`，两种 TLS 模式一致。
