# TMS 公网服务器首次部署操作指南

本文用于已登录公网服务器的 `ecs-user`，按顺序完成一次全新 TMS 部署。
示例域名为 `test.itnsa.cn`；如果实际域名不同，在配置步骤中替换。

适用条件：

- Debian 13 / systemd，Python 3.13、uv、PostgreSQL、Caddy 已安装。
- `ecs-user` 已配置 GitHub SSH 认证，可以访问 TMS 仓库，并可使用 sudo。
- 域名解析、云安全组和服务器网络已配置。
- 使用 `TMS_TLS_MODE=automatic`，由 Caddy 自动申请和续期公网证书。
- 全新部署，不处理 Nginx 向 Caddy 的切换。

完整架构、内网 acme.sh 模式、权限、备份恢复和回滚说明见
[TMS 生产自动化部署手册](deploy-tms-production.md)。

## 操作约定

除特别说明外，命令均在远端服务器上以 `ecs-user` 的 Bash 执行。
逐段执行，每一步成功后再继续；失败时保存命令和错误输出。

**部署前先确认：本次准备使用的脚本、模板、应用配置和前端构建产物已经审阅、提交并推送到 GitHub 的 `develop`。**
部署脚本的 `plan` 从远端 Git 仓库获取代码，本地未提交或未推送的文件不会进入发布版本。

下文 `<实际release_id>`、`<实际plan_id>` 和 `<完整40位SHA>` 是占位符，执行前须替换，不要原样粘贴。

## 1. 检查服务器前提

```bash
whoami
cat /etc/os-release
/usr/bin/python3.13 --version

sudo sh -c 'command -v uv && uv --version'
sudo caddy version
psql --version

sudo systemctl is-active postgresql
sudo systemctl is-active caddy
sudo ss -ltnp
df -h /srv
swapon --show
```

确认以下条件：

- 当前用户为 `ecs-user`，Python 3.13、uv、PostgreSQL 和 Caddy 均可用。
- **root 的命令搜索路径中也能找到 uv**，不能仅在 `ecs-user` 的交互式 shell 中可用。
- PostgreSQL 已启动；全新环境的 Caddy 若尚未启动，也应检查原因并确认服务配置可用。
- TCP 80/443 由 Caddy 使用，没有其他 Web 服务占用。
- 云安全组和服务器防火墙允许公网 TCP 80、443；8010 不需要对外开放。
- 域名的公网 A 记录指向服务器公网 IP；若存在 AAAA 记录，IPv6 也必须正确。
- `/srv` 有足够空间。脚本会在 plan/apply 以及备份前继续检查空间。

项目包含可能需要编译的 `mysqlclient` 依赖，即使生产数据库使用 PostgreSQL，也可能需要以下构建依赖。
如果尚未安装，在 Debian 上执行：

```bash
sudo apt-get update

sudo apt-get install --no-install-recommends \
  git curl ca-certificates openssl \
  build-essential pkg-config python3.13-dev \
  default-libmysqlclient-dev libpq5
```

服务器不需要安装 Node/npm。前端构建产物应在开发端生成并提交到仓库。

## 2. 获取已推送的代码

人工审查用的 checkout 放在 `ecs-user` 的工作目录中。不要直接 clone 到 `/srv/tms`，该目录由部署脚本管理。

```bash
mkdir -p "$HOME/src"

git -c core.sshCommand='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10' \
  clone --branch develop --single-branch \
  git@github.com:hdaojin/tms.git "$HOME/src/tms-deploy-review"

cd "$HOME/src/tms-deploy-review"

git log -1 --format='%H %s'
```

若目录已经存在，先进入目录检查 `git status`，不要重复 clone 或覆盖已有修改。
SSH 主机密钥校验失败时，核对已有 SSH 配置与可信主机记录，不要关闭严格校验。

确认文件齐全，并检查 Bash 语法：

```bash
ls -l \
  scripts/deploy_tms.sh \
  scripts/update_tms.sh \
  deploy/production/deploy.conf.example \
  deploy/production/tms.service \
  deploy/production/tms.caddy

bash -n scripts/deploy_tms.sh
bash -n scripts/update_tms.sh
```

## 3. 安装稳定部署入口

审阅源码后，将脚本和模板安装为 root 所有的稳定入口：

```bash
sudo install -d -m 0755 /usr/local/share/tms-deploy

sudo install -o root -g root -m 0755 \
  scripts/deploy_tms.sh /usr/local/sbin/tms-deploy

sudo install -o root -g root -m 0755 \
  scripts/update_tms.sh /usr/local/sbin/tms-update

sudo install -o root -g root -m 0644 \
  deploy/production/tms.service /usr/local/share/tms-deploy/tms.service

sudo install -o root -g root -m 0644 \
  deploy/production/tms.caddy /usr/local/share/tms-deploy/tms.caddy

sudo install -d -m 0750 /etc/tms
```

仅在首次部署且 `/etc/tms/deploy.conf` 尚不存在时执行以下命令，避免覆盖已有配置：

```bash
sudo install -o root -g root -m 0640 \
  deploy/production/deploy.conf.example /etc/tms/deploy.conf
```

后续部署使用 `/usr/local/sbin/tms-deploy`，不要直接 sudo 执行浮动分支 checkout 内的脚本。

## 4. 设置公网部署参数

```bash
sudo nano /etc/tms/deploy.conf
```

确认以下值，其余保留示例默认值：

```bash
TMS_DOMAIN=test.itnsa.cn
TMS_GIT_URL=git@github.com:hdaojin/tms.git
TMS_GIT_REVISION=develop
TMS_DEPLOY_USER=ecs-user

TMS_BIND=127.0.0.1:8010
TMS_WORKERS=2
TMS_SWAP_SIZE=2G

TMS_TLS_MODE=automatic
TMS_BASIC_AUTH_TRUSTED_CIDRS=""
```

第一次公网测试建议保留全站 Basic Auth。空的可信网段表示所有客户端均需外层认证。
`automatic` 模式不使用 `TMS_ACME_*` 配置，不需要执行 acme.sh 命令。

保存后执行只读检查：

```bash
sudo /usr/local/sbin/tms-deploy inspect
```

核对空间、软件版本、监听地址和现有部署状态。已有的其他 Caddy 站点应继续保留；
如服务器原本提供 `share.itnsa.cn`，不要删除或替换它的配置。

## 5. 创建 Basic Auth 用户

```bash
sudo /usr/local/sbin/tms-deploy auth add operator
sudo /usr/local/sbin/tms-deploy auth list
```

密码隐藏输入，至少 8 个字符。
这是网站外层认证账户，与稍后创建的 Django 管理员是两套不同账户。

## 6. 生成首次部署计划

```bash
sudo /usr/local/sbin/tms-deploy plan \
  --revision develop \
  --first-install
```

这一步会获取代码、固定完整 SHA、创建候选 release、安装 Python 依赖、检查迁移并收集静态文件。
尚未切换活动服务或修改业务数据库。

成功后记录实际输出：

```text
plan_id=plan-实际时间-实际SHA前12位
release_id=实际时间-实际SHA前12位
sha=完整40位SHA
tls_mode=automatic
basic_auth_trusted_cidrs=
```

按实际 release ID 查看检查报告：

```bash
sudo less /srv/tms/releases/<实际release_id>/.tms-check-deploy.txt
sudo less /srv/tms/releases/<实际release_id>/.tms-migration-plan.txt
```

首次计划使用临时配置预检，`check --deploy` 可能包含与临时配置有关的警告，应结合实际生产配置逐项判断。
出现依赖安装失败、迁移漂移或其他错误时先停止，不执行下一步。

## 7. 应用计划

将占位符替换为上一步输出的 plan ID 和完整 SHA：

```bash
sudo /usr/local/sbin/tms-deploy apply \
  <实际plan_id> \
  --confirm-sha <完整40位SHA>
```

该步骤会：

1. 校验计划、配置和模板哈希，以及候选 SHA、目录与可用空间。
2. 创建系统账户、共享目录、数据库角色和秘密配置；没有 swap 时创建 2 GiB swap。
3. 安装并校验 systemd/Caddy 配置，保留其他 Caddy 站点。
4. 进入维护状态，执行数据库迁移和首次业务初始化。
5. 原子切换 release，启动服务，检查本机应用和 HTTPS。

成功时输出 `TMS_DEPLOYMENT_COMPLETE`。

生成计划后不要修改部署入口、模板或配置。若有修改，重新 `plan`，使用新 plan ID 和对应 SHA。

## 8. 验证并创建应用管理员

```bash
sudo /usr/local/sbin/tms-deploy verify
sudo /usr/local/sbin/tms-deploy status

sudo /usr/local/sbin/tms-deploy admin create
```

最后在浏览器打开：

```text
https://test.itnsa.cn
```

依次检查：

1. 证书受信任，域名正确，没有证书警告。
2. 输入外层 Basic Auth 的 `operator` 账户。
3. 使用刚创建的 Django 管理员登录应用。
4. 页面样式、上传与下载正常。
5. HTTP 访问自动跳转到 HTTPS。

还可以从自己的电脑检查未认证响应：

```bash
curl -I https://test.itnsa.cn
```

全站 Basic Auth 配置下预期返回 `401`。不要添加 `-k` 跳过证书校验。

## 9. 部署失败时收集信息

```bash
sudo /usr/local/sbin/tms-deploy status
sudo journalctl -u tms.service -n 100 --no-pager
sudo journalctl -u caddy -n 100 --no-pager
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

保留失败命令、退出状态和相关错误输出。不要发送 `/etc/tms/*.env` 内容、数据库密码或私钥。
若数据库迁移已经执行，不要自行删除维护标志、切回旧代码或删除数据库重试，按完整手册选择前滚修复或完整恢复。

## 10. 后续日常更新入口

后续代码更新不再使用 `--first-install`：

```bash
sudo /usr/local/sbin/tms-update plan --revision develop
# 审阅新计划、完整 SHA 和迁移内容后执行
sudo /usr/local/sbin/tms-update apply <实际plan_id> --confirm-sha <完整40位SHA>
sudo /usr/local/sbin/tms-update verify
sudo /usr/local/sbin/tms-update status
```

日常更新会在活动变更前执行完整备份并验证。开发端 Python/npm 依赖升级与前端构建流程见
[完整手册第 13 节](deploy-tms-production.md#13-依赖和-tms-更新)。
