# TMS 测试部署环境实施计划（Codex 执行版）

> **目标**：将现有 Debian 13 云服务器 `test.itnsa.cn` 配置为 TMS
> 的独立测试部署环境。\
> **当前代码目录**：`/srv/tms-staging/tms`（已克隆 `hdaojin/tms` 的
> `develop` 分支）。\
> **现有服务**：服务器已有 SSH/root 访问权限，已安装 Caddy。\
> **实施原则**：先检查、再变更；不覆盖未知配置；不删除现有数据；所有配置变更可检查、可回滚。

------------------------------------------------------------------------

## 1. 本次任务范围

### 1.1 必须完成

1.  检查服务器、仓库、DNS、现有 Caddy 和防火墙状态。
2.  在 Debian 13 上准备 Python 3.13、uv、PostgreSQL 及 Python
    依赖编译所需的系统包。
3.  使用专用 Linux 服务账户运行 TMS，不以 root 运行 Django/Gunicorn。
4.  为测试环境创建独立 PostgreSQL 数据库和最小权限数据库账户。
5.  配置独立的 Django 环境变量、HTTPS 反向代理安全设置和文件目录权限。
6.  使用 Gunicorn + systemd 运行 Django，通过现有 Caddy 提供 HTTPS。
7.  正确提供 `/static/` 与公共 `/media/` 文件，确保 `media-private/`
    不被 Web 服务器直接公开。
8.  执行数据库迁移、初始化数据、Django 部署检查及浏览器访问验收。
9.  记录服务维护、日志查看、更新部署和回滚方法。

### 1.2 明确不在本次范围内

-   不建设远程开发服务器，不安装 Codex CLI、VS Code Server
    或其他开发代理。
-   不把 Codex 的开发工作目录与运行中的测试站点混用。
-   不安装 Docker、Nginx 或其他替代 Caddy 的 Web 服务器。
-   不在测试服务器上运行 Node.js/npm 构建流程；TMS
    的前端构建产物应来自仓库/已验证的构建结果。
-   不恢复生产环境数据库或生产用户上传文件，不复制生产密钥。
-   不改造 TMS 业务逻辑，不做无关重构。
-   未经用户明确批准，不启用自动部署、不开放新的非必要公网端口、不更改
    SSH 登录策略、不清理未知文件或数据库。

------------------------------------------------------------------------

## 2. 目标架构

``` text
浏览器
  │ HTTPS :443 / HTTP :80
  ▼
现有 Caddy
  ├── /static/*  → /srv/tms-staging/tms/staticfiles/
  ├── /media/*   → /srv/tms-staging/tms/media/
  └── 其他请求   → 127.0.0.1:8010
                       │
                       ▼
                Gunicorn / Django
                systemd: tms-staging.service
                       │
                       ▼
                PostgreSQL（本机）
                database: tms_staging
                role: tms_staging
```

建议的目录和身份：

  项目                     规划
  ------------------------ --------------------------------------------
  Git 工作目录             `/srv/tms-staging/tms`（保留现有克隆）
  Linux 服务账户           `tms-stage`，不授予 sudo，不用于日常登录
  systemd 服务             `tms-staging.service`
  Gunicorn 监听地址        `127.0.0.1:8010`，不得监听公网接口
  PostgreSQL 数据库        `tms_staging`
  PostgreSQL 用户          `tms_staging`，仅访问自己的数据库
  公共上传文件             `/srv/tms-staging/tms/media/`
  私有文件                 `/srv/tms-staging/media-private/`
  收集后的静态文件         `/srv/tms-staging/tms/staticfiles/`
  环境变量文件             `/srv/tms-staging/tms/.env`，禁止进入 Git
  服务器专用 Django 设置   `/etc/tms-staging/tms_staging_settings.py`
  运维说明                 `/srv/tms-staging/OPERATIONS.md`
  备份目录                 `/srv/tms-staging/backups/`

TMS 当前 `settings.py` 的 `MEDIA_ROOT` 是仓库下的 `media/`，而
`PRIVATE_MEDIA_ROOT`、`NOTES_ROOT`
可以通过环境变量配置。除非检查发现必须调整，否则保留这一现状，不为本次部署改造业务文件存储架构。

------------------------------------------------------------------------

## 3. 执行规则与安全门槛

Codex 必须遵守以下规则：

1.  **先只读检查**：在修改前检查 `/etc/caddy/Caddyfile`、systemd
    服务、PostgreSQL、目录权限、仓库状态和防火墙。
2.  **不覆盖现有配置**：Caddy 已有其他站点时，只添加或修改
    `test.itnsa.cn` 对应的站点块；不得用新模板覆盖整个 Caddyfile。
3.  **不丢弃 Git 修改**：检查
    `git status`。若有未提交修改、当前分支不符或存在无法解释的本地文件，先停止并报告，不得执行
    `git reset --hard`、`git clean -fd` 或重新克隆覆盖。
4.  **不删除未知数据**：若目标数据库、`.env`、媒体目录或服务已经存在，先检查并备份；不得默认重建、清空或覆盖。
5.  **凭据保密**：生成独立的 Django `SECRET_KEY`
    和数据库密码。不要在聊天输出、Git、命令历史或运维文档中泄露密码；`.env`
    权限应为 `0640` 或更严格。
6.  **公网访问确认**：在让站点对公网可访问之前，向用户确认是否使用 Caddy
    Basic Auth 作为额外入口保护。建议测试站点启用 Basic
    Auth；密码由用户提供或安全生成，Caddy
    配置只保存密码哈希。未经确认，不擅自公开测试站点。
7.  **防火墙谨慎操作**：检查云平台安全组与 Debian 防火墙。只确认
    SSH、HTTP、HTTPS 的必要连通性；不得在未确认 SSH
    放行规则前启用或重置防火墙。
8.  **数据库操作需可解释**：首次迁移前确认目标是新建的 `tms_staging`
    数据库。若已有数据，先执行备份并向用户报告；不得删除数据库或执行
    `flush`。
9.  **初始化数据先预览**：执行 `bootstrap_tms` 前先运行
    `--dry-run`，审阅输出后再初始化。不要使用 `--force`。
10. **分阶段验证**：每个阶段结束时检查结果；Caddy 配置校验失败时不得
    reload，Django 检查失败时不得将服务标记为部署成功。

遇到必须由用户决定的事项（例如站点是否加 Basic
Auth、已有数据库是否保留、检测到不一致的本地代码），暂停并清楚说明原因，不要自行猜测。

------------------------------------------------------------------------

## 4. 阶段一：只读检查与基线记录

### 4.1 检查系统资源与版本

记录以下结果：

-   `/etc/os-release`、内核版本、CPU、内存、磁盘空间。
-   `python3.13 --version`、`uv --version`、`psql --version`、`caddy version`。
-   `systemctl status caddy`。
-   `ss -lntp`，确认现有监听端口。
-   DNS A/AAAA 记录是否指向本机；80/443 是否能从公网访问。
-   Debian 防火墙和云平台安全组现状。

若磁盘空间不足、域名未解析到此服务器、80/443 被其他进程占用或 Caddy
当前异常，先报告，不要盲目继续。

### 4.2 检查仓库

在 `/srv/tms-staging/tms` 中：

-   阅读
    `AGENTS.md`、`README.md`、`.env.example`、`pyproject.toml`、`uv.lock`、`tmsproject/settings.py`
    和 CI workflow。
-   确认 remote 指向 `hdaojin/tms`，分支为 `develop`。
-   检查 `git status --short --branch` 和最近提交。
-   若工作区干净，获取远端 `develop` 信息并比较提交；只有确认可安全
    fast-forward 后才更新代码。
-   不得在服务器上重新构建 Tailwind CSS。检查仓库是否包含
    `static/css/output.css` 等所需的前端构建产物。
-   如果 `uv.lock` 与 `pyproject.toml`
    不一致，停止并报告；不得在部署机上自行重新生成锁文件。

### 4.3 检查现有服务配置

-   备份现有 `/etc/caddy/Caddyfile`，记录当前是否已有 `test.itnsa.cn`
    站点。
-   检查是否已有 `tms-staging.service`、Gunicorn 进程、PostgreSQL
    cluster、`tms_staging` 数据库或相关目录。
-   检查仓库是否已有 `.env`，以及
    `media/`、`staticfiles/`、`media-private/` 的内容与权限。
-   对现有文件先记录状态；不能因其不符合预期就直接覆盖。

阶段一完成后，向用户简要报告检查结果和需要确认的事项，再进入会产生系统变更的阶段。

------------------------------------------------------------------------

## 5. 阶段二：安装系统依赖

仅安装缺失的软件包，不移除现有软件。Debian 13 优先使用发行版提供的
PostgreSQL 默认主版本；先核实版本，不要未经批准添加第三方 PostgreSQL
软件源。

预计需要的包包括：

``` text
postgresql
postgresql-contrib
python3.13
python3.13-venv
libpq5
```

项目使用 `psycopg` 连接 PostgreSQL，需要 `libpq5` 运行库，无需安装
MySQL 驱动及其编译依赖。本方案使用系统 Python 3.13。

安装并使用 uv。优先确保 uv 使用可被服务账户读取的系统 Python 3.13
创建虚拟环境，避免虚拟环境链接到 `/root` 私有目录下的 Python。可使用：

``` bash
uv sync --python /usr/bin/python3.13 --frozen --no-dev
```

如果系统 Python 路径不同，先确认实际路径再执行。不要使用
`uv lock`，也不要修改 `uv.lock`。

不要安装
npm/Node.js；若仓库缺少前端构建产物，应停止并报告，要求从开发机或 CI
生成并提交/交付正确的构建产物。

------------------------------------------------------------------------

## 6. 阶段三：建立专用运行账户、目录与权限

### 6.1 Linux 账户

创建专用系统账户 `tms-stage`，用于运行 Gunicorn/Django：

-   不授予 sudo。
-   不允许通过该账户进行日常交互式 SSH 登录。
-   不将其加入 `caddy` 组，除非检查后证明确有必要。
-   不让 Caddy 读取 `.env` 或私有媒体目录。

### 6.2 目录与权限

创建缺失的目录：

``` text
/srv/tms-staging/tms/media/
/srv/tms-staging/tms/staticfiles/
/srv/tms-staging/media-private/
/srv/tms-staging/media-private/notes/
/srv/tms-staging/backups/
/etc/tms-staging/
```

权限原则：

-   仓库代码、虚拟环境和 `.env` 不允许 Web 服务器写入。
-   `tms-stage`
    只对运行期确需写入的目录有写权限，包括公共上传目录和私有媒体目录。
-   `staticfiles/` 由部署步骤写入，Caddy 只读。
-   Caddy 可以遍历并读取 `staticfiles/`、公共 `media/`，但不得读取
    `.env`、备份目录或 `media-private/`。
-   `.env`
    与外部设置文件使用最小权限；备份目录仅授权管理员/指定备份账户访问。
-   检查公共媒体目录内不存在指向私有文件或其他敏感路径的符号链接。

不要为了省事将整个仓库 `chown -R tms-stage`，也不要对整个 `/srv`
使用宽松的 `777` 权限。

------------------------------------------------------------------------

## 7. 阶段四：配置 PostgreSQL

1.  确认 PostgreSQL 服务运行，记录实际主版本。
2.  创建独立数据库 `tms_staging` 和登录角色 `tms_staging`。
3.  数据库角色不得拥有超级用户、创建其他数据库或管理其他数据库的权限。
4.  数据库只接受本机连接；Gunicorn 和 PostgreSQL 均不应开放公网端口。
5.  使用随机生成的强数据库密码，并采用适当的安全方式写入
    `.env`；不要将密码放进 Git 或命令历史。
6.  如果同名数据库/角色已经存在，先检查归属和内容，不能直接删除或重建。
7.  连接验证成功后，再进行 Django 初始化。

测试环境数据库必须与任何生产数据库完全分离。不要从生产服务器复用数据库账号、密码或连接
URL。

------------------------------------------------------------------------

## 8. 阶段五：配置 Django 环境

### 8.1 创建 `.env`

若 `.env` 不存在，从 `.env.example`
复制后改为测试环境配置；若已存在，先备份并逐项审阅，禁止覆盖已有秘密。

至少配置：

``` dotenv
DEBUG=False
SECRET_KEY=<独立生成的随机密钥>
ALLOWED_HOSTS=test.itnsa.cn,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://test.itnsa.cn
DATABASE_URL=<本机 tms_staging 数据库连接 URL>
PRIVATE_MEDIA_ROOT=/srv/tms-staging/media-private
SAMBA_INTEGRATION_ENABLED=False
SAMBA_ASYNC_OPERATIONS_ENABLED=False
```

数据库连接 URL 应使用实际密码。若密码含 URL
特殊字符，必须正确编码；可用随机十六进制密码避免该问题。

不要把生产环境的 `SECRET_KEY`、数据库凭据或真实用户数据复制到测试环境。

### 8.2 HTTPS 代理设置

当前 `tmsproject/settings.py` 需要核实是否配置了 HTTPS
反向代理相关设置。Caddy 负责 TLS，Gunicorn 仅监听 `127.0.0.1:8010`，因此
Django 必须正确识别来自可信 Caddy 的
`X-Forwarded-Proto: https`，否则可能出现 HTTPS 请求被识别为 HTTP、CSRF
校验失败或安全 Cookie 配置不正确的问题。

为避免把服务器专用设置写进正在部署的 Git 工作树，优先创建外部设置模块：

`/etc/tms-staging/tms_staging_settings.py`

示例结构：

``` python
from tmsproject.settings import *

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# 测试站点初次部署先不启用 HSTS，避免在确认 HTTPS 与域名配置前
# 让浏览器缓存长期的强制 HTTPS 策略。
SECURE_HSTS_SECONDS = 0
```

这是服务器专用设置，不应放入仓库，也不应覆盖
`tmsproject/settings.py`。通过 systemd 的 `PYTHONPATH` 和
`DJANGO_SETTINGS_MODULE` 指向它。执行 Django
管理命令时也必须使用相同的设置模块。

只有确认 Gunicorn 仅绑定回环地址、外部请求只能经由受控 Caddy
进入后，才可信任 `X-Forwarded-Proto`。

如果外部设置模块方式在当前项目结构下无法正确加载，先报告并提出最小替代方案；不要未经批准修改业务代码或在仓库内留下未提交的部署补丁。

### 8.3 检查与迁移命令

所有 Django 命令都从仓库根目录执行，并使用同一 Python 3.13
虚拟环境、同一 `.env` 和 `tms_staging_settings` 设置模块。

在迁移前执行：

``` bash
python manage.py check
python manage.py showmigrations
python manage.py migrate --plan
```

若数据库是新建空库，确认迁移计划合理后执行：

``` bash
python manage.py migrate --noinput
python manage.py bootstrap_tms --dry-run
```

审阅 Bootstrap
预览，确认目标数据库正确且只会初始化预期的业务目录后，再执行：

``` bash
python manage.py bootstrap_tms --yes
```

不得执行
`bootstrap_tms --force`。如果数据库不是空库，先备份并报告，不得按"新库"流程处理。

不要无条件执行 `reconcile_permission_assignments --apply` 或
`migrate_private_media --apply`。只有当前发布说明/迁移文档明确要求，且已审阅
dry-run 输出、备份数据并确认适用时，才执行相应的数据变更。

创建超级管理员时，不得编造或输出密码。运行交互式
`createsuperuser`，或暂停请用户完成该步骤。

------------------------------------------------------------------------

## 9. 阶段六：配置 Gunicorn 与 systemd

创建
`/etc/systemd/system/tms-staging.service`。建议以以下内容为起点，再根据实际目录和检查结果调整：

``` ini
[Unit]
Description=TMS Staging
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=tms-stage
Group=tms-stage
WorkingDirectory=/srv/tms-staging/tms
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONPATH=/etc/tms-staging:/srv/tms-staging/tms
Environment=DJANGO_SETTINGS_MODULE=tms_staging_settings
ExecStart=/srv/tms-staging/tms/.venv/bin/gunicorn tmsproject.wsgi:application --bind 127.0.0.1:8010 --workers 2 --access-logfile - --error-logfile -
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/tms-staging/tms/media /srv/tms-staging/media-private

[Install]
WantedBy=multi-user.target
```

执行前确认 `ProtectSystem=strict`
与实际运行期写入目录相容。若应用确有其他必要写入目录，应只增加该目录，不要取消全部安全限制来绕过权限问题。

然后：

``` bash
systemctl daemon-reload
systemctl enable --now tms-staging
systemctl status tms-staging
journalctl -u tms-staging -n 100 --no-pager
```

验证监听地址确实为 `127.0.0.1:8010`，而不是 `0.0.0.0:8010` 或公网地址。

------------------------------------------------------------------------

## 10. 阶段七：配置现有 Caddy

### 10.1 修改原则

-   先备份 `/etc/caddy/Caddyfile`。
-   只新增或修改 `test.itnsa.cn` 对应的站点块，保留其他站点与全局设置。
-   检查 Caddy 当前版本支持的指令。
-   站点应提供自动 HTTPS，并把动态请求反向代理到 `127.0.0.1:8010`。
-   静态文件和公共媒体使用精确路径处理；不得设置 `/srv/tms-staging`
    为整个站点的通用文件根目录。

### 10.2 站点配置参考

根据现有 Caddyfile 结构合并，不能直接覆盖整个文件：

``` caddyfile
test.itnsa.cn {
    encode zstd gzip

    handle_path /static/* {
        root * /srv/tms-staging/tms/staticfiles
        file_server
    }

    handle_path /media/* {
        root * /srv/tms-staging/tms/media
        file_server
    }

    handle {
        reverse_proxy 127.0.0.1:8010
    }
}
```

`handle_path`
会移除匹配的路径前缀，因此静态目录和媒体目录应与上述路径对应。Caddy
只能直接提供公共媒体 `media/`，绝不能添加指向 `media-private/` 的路由。

如果用户确认需要额外入口保护，在站点块中按当前 Caddy 版本配置
`basic_auth`，并使用 `caddy hash-password`
生成密码哈希；不把明文密码写入 Caddyfile 或仓库。若用户选择不加 Basic
Auth，应明确告知站点将依赖 TMS 自身的登录和权限控制。

### 10.3 校验后再 reload

先执行 Caddyfile 格式/配置校验。校验通过后才 reload：

``` bash
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl reload caddy
systemctl status caddy
journalctl -u caddy -n 100 --no-pager
```

如果 DNS、证书签发、端口或 Caddy
配置存在问题，不得反复覆盖配置；保留诊断信息并修复具体原因。

------------------------------------------------------------------------

## 11. 阶段八：静态文件、部署检查与功能验收

### 11.1 静态文件

确认仓库已有前端构建产物后执行：

``` bash
python manage.py collectstatic --noinput
```

检查 `staticfiles/` 包含 Django admin 和项目 CSS/JS，且 Caddy
可以读取。不要把 `media-private/` 作为 `collectstatic` 或公共文件目录。

### 11.2 Django 检查

执行：

``` bash
python manage.py check
python manage.py check --deploy
python manage.py showmigrations
```

`check --deploy`
的所有警告都必须记录并逐项判断。测试环境可以有明确说明的非关键警告（例如初次部署暂不启用
HSTS），但不得忽略 DEBUG、SECRET_KEY、ALLOWED_HOSTS、HTTPS
代理识别、CSRF 或 Cookie 安全相关问题。

### 11.3 HTTP/HTTPS 验收

至少验证：

1.  `http://test.itnsa.cn` 会被重定向到 HTTPS。
2.  `https://test.itnsa.cn` 的证书有效且域名匹配。
3.  未登录访问 TMS 时出现符合预期的登录跳转或页面。
4.  登录页能正常加载，CSS/JS 请求成功且 MIME 类型正确。
5.  静态文件 URL 返回成功状态码。
6.  登录、CSRF 表单提交、退出登录等基本流程可用。
7.  上传一个非敏感测试文件，验证公共媒体路径行为符合设计；如涉及私有附件，验证只能通过
    Django 授权访问。
8.  `/media-private/`、`.env`、`.git/`、备份目录等路径不能被 Caddy
    直接读取。
9.  `ss -lntp` 确认 Gunicorn 与 PostgreSQL 没有意外监听公网接口。
10. 查看 `journalctl -u tms-staging` 和 Caddy 日志，没有持续的
    5xx、数据库连接失败或静态文件权限错误。

验收时不要输出密码、SECRET_KEY、数据库连接完整凭据或用户私密数据。

------------------------------------------------------------------------

## 12. 阶段九：备份、回滚与运维说明

### 12.1 备份

在任何可能影响已有数据库或上传文件的操作之前，先确认备份可用。首次部署成功后，至少完成一次测试环境基线备份，覆盖：

-   `tms_staging` PostgreSQL 数据库；
-   `/srv/tms-staging/tms/media/`；
-   `/srv/tms-staging/media-private/`。

备份放在 `/srv/tms-staging/backups/`，限制读取权限，并避免将 `.env`
或其他秘密不加保护地打包。不要从生产环境导入数据。

本阶段先保证可以手动完成备份和验证；是否增加定时备份，留待用户确认后实施。

### 12.2 回滚

-   修改 Caddyfile 或 systemd unit 前保存带时间戳的备份。
-   若新服务启动失败，先停止/禁用新建的 TMS
    服务并恢复对应配置备份，不要影响 Caddy 的其他站点。
-   不要自动删除 PostgreSQL 数据库。
-   不要自动回滚 Django
    migration；数据库迁移可能不可逆。需要回滚时先报告已应用的迁移、数据库状态与可行方案，等待用户确认。
-   不得使用 `git reset --hard` 或 `git clean` 作为部署回滚手段。

### 12.3 运维说明文件

创建 `/srv/tms-staging/OPERATIONS.md`，至少记录：

-   架构、目录和服务账户；
-   Caddy 与 systemd 配置文件位置；
-   启动、停止、重启、状态查询、日志查看命令；
-   手动更新 `develop` 的安全步骤；
-   数据库与媒体文件备份/恢复步骤；
-   环境变量文件位置（只记录路径和变量名称，不记录秘密值）；
-   访问保护方式；
-   已知警告和后续建议。

后续更新应采用"检查 Git 状态 → 备份 → 拉取已确认的提交 →
`uv sync --frozen --no-dev` → 迁移计划检查 → 数据库迁移 →
`collectstatic` → 重启服务 →
验收"的顺序。若仓库不干净或迁移风险不明确，应先停止并报告。

------------------------------------------------------------------------

## 13. 完成标准

只有全部满足以下条件，才能报告部署成功：

-   [ ] 使用现有 `/srv/tms-staging/tms` 仓库，没有覆盖本地文件或丢弃 Git
    修改。
-   [ ] TMS 以 `DEBUG=False` 运行，测试密钥和数据库凭据独立。
-   [ ] PostgreSQL 数据库和角色独立，未暴露公网端口。
-   [ ] Gunicorn 由 `tms-stage` 用户通过 systemd 管理，仅监听
    `127.0.0.1:8010`。
-   [ ] Caddy 配置通过校验，其他站点不受影响，HTTPS 证书有效。
-   [ ] `/static/` 与公共 `/media/` 可按预期访问。
-   [ ] `media-private/`、`.env`、`.git/` 和备份目录没有被公开。
-   [ ] Django migration、Bootstrap 初始化、超级管理员创建均有明确结果。
-   [ ] `check`、`check --deploy`、基本 HTTP/HTTPS
    与登录流程均已验证，遗留警告有记录。
-   [ ] 首次基线备份完成，`OPERATIONS.md` 已生成。
-   [ ]
    没有安装开发服务器工具，没有新增不必要的公网端口，没有启用自动部署。

------------------------------------------------------------------------

## 14. Codex 执行完成后的报告格式

Codex 最终应简洁报告：

1.  部署结果与访问 URL；
2.  当前部署的 Git 分支和 commit；
3.  Python、Django、PostgreSQL、Caddy 的实际版本；
4.  systemd 服务状态和 Gunicorn 监听地址；
5.  Django 检查与 HTTP/HTTPS 验收结果；
6.  数据库、媒体文件与私有文件路径；
7.  备份位置和恢复方式；
8.  `check --deploy` 遗留警告；
9.  仍需用户操作的事项（例如创建管理员、确认 Basic Auth）。

**不要在报告中输出任何密码、SECRET_KEY、完整数据库连接 URL
或其他秘密。**

------------------------------------------------------------------------

## 15. 官方参考文档

执行时应以当前安装版本的官方文档为准：

-   Django 6.0
    部署检查清单：<https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/>
-   Django 6.0
    安全设置：<https://docs.djangoproject.com/en/6.0/ref/settings/>
-   Caddy
    `reverse_proxy`：<https://caddyserver.com/docs/caddyfile/directives/reverse_proxy>
-   Caddy
    `handle_path`：<https://caddyserver.com/docs/caddyfile/directives/handle_path>
-   Caddy
    `file_server`：<https://caddyserver.com/docs/caddyfile/directives/file_server>
-   uv 文档：<https://docs.astral.sh/uv/>
