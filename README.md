# TMS 培训管理系统

TMS（Training Management System）是一个基于 Django 的培训与竞赛管理系统，用于统一管理训练过程、考核资料、会议记录、通知公告和用户角色权限。

## 技术栈

- Django 6
- Python 3.13
- django-htmx
- django-tables2
- Tailwind CSS 4
- DaisyUI 5
- Alpine.js
- Iconify

## 功能概览

- 用户、稳定角色与权限包管理
- 技能项目、能力领域与标准技能树版本
- 赛事、训练考核、试题与评分方案
- 评分结果、考点证据与技能映射覆盖统计
- 训练周期与训练日志
- 统一资料资产归档
- 通知公告、会议记录与笔记
- WorldSkills Forum 主题、翻译与附件归档
- Samba 集成、文章和站点公共内容

## 环境要求

- Python 3.13+
- uv
- Node.js 20+（仅开发环境或前端资源预构建时需要）
- npm（仅开发环境或前端资源预构建时需要）
- SQLite（开发环境）
- PostgreSQL 17（生产环境）

## 目录说明

- `static/`：项目静态资源目录，包含前端构建产物和随仓库分发的第三方静态文件
- `staticfiles/`：`collectstatic` 输出目录，供生产环境 Web 服务器直接提供
- `media/`：仅用于确实需要公开提供的上传文件
- `media-private/`：私有资料根目录，可通过 `PRIVATE_MEDIA_ROOT` 覆盖；`ArchiveAsset` 登记的训练日志附件、试题、评分表、评分脚本、结果包和其他归档资料，以及 Forum 私有附件，都使用私有存储

注意：

- 所有 Django 命令都必须在项目根目录执行。
- 如果 `.env` 中使用相对路径的 `DATABASE_URL=sqlite:///db.sqlite3`，从子目录运行脚本会连到错误的 SQLite 文件。
- `media-private/` 不得由 Nginx 直接暴露；私有资料必须通过带权限检查的 Django 下载 view 提供。
- `demo` 应用只在 `DEBUG=True` 时启用，生产环境不会加载。

## 开发约定

- 工程规则：`AGENTS.md`
- 领域语义：`CONTEXT.md`
- 架构决策：`docs/adr/`

## 开发环境快速开始

### 1. 克隆代码

```bash
git clone git@github.com:hdaojin/tms.git
cd tms
```

本项目已在 `pyproject.toml` 中把 uv 缓存固定到仓库内的 `.uv-cache/`，用于避开 Windows 上全局 uv 缓存目录权限不稳定的问题。平时仍然直接使用 `uv sync`、`uv run ...` 等命令即可，不需要手工设置 `UV_CACHE_DIR`。

### 2. 安装依赖

```bash
uv sync
npm install
```

CI 或需要可重复安装前端依赖时使用：

```bash
npm ci
```

### 3. 配置环境变量

Linux / macOS:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

默认 `.env.example` 使用 SQLite，本地开发可以直接使用。

### 4. 初始化数据库

```bash
uv run manage.py migrate
```

本版本已重构标准体系全链路，`migrate` 会自动清理旧标准链路表、contenttypes、permissions 和 migration records。升级已有环境前必须先备份数据库和上传文件目录。

仅适用于旧 `conduct` 或 `meeting` 内部标识切换的环境：

```bash
uv run manage.py reconcile_internal_app_cutovers
uv run manage.py reconcile_internal_app_cutovers --execute
uv run manage.py cutover_conduct_to_behaviors
uv run manage.py cutover_conduct_to_behaviors --execute
uv run manage.py cutover_meeting_to_meetings
uv run manage.py cutover_meeting_to_meetings --execute
```

说明：全新初始化数据库时通常只需要执行 `migrate`；旧标准体系数据不做迁移。

### 5. 导入基础数据

```bash
uv run manage.py loaddata core/default accounts/default behaviors/default
```

### 6. 创建超级管理员

```bash
uv run manage.py createsuperuser
```

### 7. 构建或监听前端样式

开发时建议开一个单独终端持续监听：

```bash
npm run watch:css
```

如果只需要手动构建一次样式：

```bash
npm run build:css
```

### 8. 启动开发服务器

```bash
uv run manage.py runserver
```

访问地址：

```text
http://127.0.0.1:8000/
```

## 常用开发命令

```bash
uv run ruff check .
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
uv run pytest
npm ci
npm run build:css
```

受影响范围较小时，优先运行聚焦测试：

```bash
uv run pytest knowledge
uv run pytest worldskills_forum
uv run pytest accounts core
uv run pytest archives
uv run pytest standards scoring
```

数据库与历史内部标识维护命令：

```bash
uv run manage.py makemigrations
uv run manage.py migrate
uv run manage.py reconcile_internal_app_cutovers
uv run manage.py cutover_conduct_to_behaviors
uv run manage.py cutover_meeting_to_meetings
npm run watch:css
```

## 前端静态资源交付规则

- 开发环境使用 npm 安装依赖并构建前端资源；生产服务器不安装 npm。
- `static/css/output.css`：由 `npm run build:css` 在开发机或 CI 生成，并随代码或发布制品一起部署到服务器。
- `static/js/alpinejs.min.js`：作为仓库内静态文件维护；升级 Alpine.js 时同步替换该文件。
- `static/css/prism.css` 与 `static/js/prism.js`：从 Prism 官网直接下载后纳入仓库；升级 Prism 时同步替换这两个文件。
- `static/js/mermaid.min.js`：从 `package.json` 锁定版本的 Mermaid npm 包复制并随仓库分发，仅供 notes 阅读页和打印页离线渲染图形；升级依赖时同步替换该文件与许可证文件。
- HTMX 运行时脚本由 `django-htmx` 模板标签提供，并在 `collectstatic` 时一并收集；生产环境不需要通过 npm 安装或手工复制 HTMX 脚本文件。

## 生产环境部署（TMS App）

下面给出一套适用于 Linux 服务器的常规部署方案：`Nginx + Gunicorn + Django`。该方案默认生产服务器不安装 npm，前端产物需在开发机或 CI 预先准备完成。

### 推荐部署架构

- Web 服务器：Nginx
- Python 应用服务：Gunicorn
- 数据库：PostgreSQL 17
- 静态文件：Nginx 直接提供 `staticfiles/`
- 明确公开的上传文件：Nginx 可按部署需要提供 `media/`
- 私有资料目录：应用进程可读写 `media-private/`，不要直接公开映射；私有下载由 Django 鉴权

### 1. 准备服务器环境

确保服务器已安装：

- Python 3.13+
- uv
- Nginx
- PostgreSQL 17

### 2. 拉取代码并安装 Python 依赖

```bash
git clone git@github.com:hdaojin/tms.git /srv/tms
cd /srv/tms

uv sync --frozen --no-dev
```

部署到生产服务器前，请先在开发机或 CI 完成前端资源准备，并确保以下文件已经包含在本次部署内容中：

- `static/css/output.css`
- `static/js/alpinejs.min.js`
- `static/css/prism.css`
- `static/js/prism.js`
- `static/js/mermaid.min.js`
- `static/js/mermaid.LICENSE.txt`
- `static/js/notes-mermaid.js`

### 3. 配置生产环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

建议至少修改为：

```env
SECRET_KEY=replace-with-a-strong-secret-key
DEBUG=False
ALLOWED_HOSTS=tms.example.com,127.0.0.1
DATABASE_URL=postgres://tms:password@127.0.0.1:5432/tms
CACHE_TIMEOUT=300
UPLOAD_MAX_SIZE_MB=100
PRIVATE_MEDIA_ROOT=/srv/tms/media-private
```

说明：

- 生产环境必须把 `DEBUG` 设为 `False`
- `ALLOWED_HOSTS` 填写真实域名或 IP
- 生产环境使用 PostgreSQL 17，不使用 SQLite
- 开发环境使用 SQLite；所有管理命令仍然必须在项目根目录执行，避免相对数据库路径指向错误文件
- `PRIVATE_MEDIA_ROOT` 指向私有上传文件根目录，不要在 Nginx 中直接暴露

### 4. 创建运行目录

```bash
mkdir -p /srv/tms/staticfiles
mkdir -p /srv/tms/media
mkdir -p /srv/tms/media-private
```

确保运行 Gunicorn 的用户对这些目录有读写权限。

### 5. 初始化数据库与基础数据

首次部署执行：

```bash
uv run manage.py migrate
uv run manage.py loaddata core/default accounts/default behaviors/default
uv run manage.py createsuperuser
```

如果不是首次部署，通常只需要执行：

```bash
uv run manage.py migrate
```

### 6. 收集静态资源

生产服务器不在本机安装 npm，也不在本机执行前端构建。确认部署内容已包含最新前端静态资源后，执行：

```bash
uv run manage.py collectstatic --noinput
```

说明：

- `collectstatic` 会收集项目 `static/` 目录中的文件，以及 `django-htmx` 等 Python 依赖自带的静态文件。
- 如果本次版本更新了 Alpine.js 或 Prism，请在部署前先同步更新仓库中的对应静态文件。
- 如果本次版本更新了 Tailwind/DaisyUI 样式，请在开发机或 CI 先重新生成 `static/css/output.css`。

### 7. 执行部署检查

```bash
uv run manage.py check --deploy
```

### 8. 启动 Gunicorn

先用前台命令验证服务能正常启动：

```bash
uv run gunicorn tmsproject.wsgi:application --bind 127.0.0.1:8000 --workers 4
```

说明：

- `workers` 数量可按 CPU 核数调整
- 默认只监听本机 `127.0.0.1:8000`，由 Nginx 反向代理对外提供服务

### 9. 配置 systemd（推荐）

示例服务文件 `/etc/systemd/system/tms.service`：

```ini
[Unit]
Description=TMS Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/tms
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/local/bin/uv run gunicorn tmsproject.wsgi:application --bind 127.0.0.1:8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

注意：

- `ExecStart` 中的 `uv` 路径请按服务器实际安装位置调整
- `User` / `Group` 请替换为实际运行用户

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable tms
sudo systemctl start tms
sudo systemctl status tms
```

### 10. 配置 Nginx

示例站点配置：

```nginx
server {
	listen 80;
	server_name tms.example.com;

	client_max_body_size 100m;

	location /static/ {
		alias /srv/tms/staticfiles/;
	}

	location /media/ {
		alias /srv/tms/media/;
	}

	location / {
		proxy_pass http://127.0.0.1:8000;
		proxy_set_header Host $host;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $scheme;
	}
}
```

注意：

- 不要直接暴露 `media-private/`
- `media-private/` 应仅作为应用进程读写目录保留
- 如果后续需要让 Nginx 接管部分私有文件下载，应再单独设计鉴权与转发方案

### 11. 部署完成后的检查项

- 可以正常访问首页与后台登录页
- 后台可正常登录
- `uv run manage.py check --deploy` 无阻塞性问题
- 静态资源样式加载正常
- 明确公开的上传文件能够访问
- 私有资料上传目录可由应用正常读写，且不能绕过 Django 权限直接访问

## 发布更新流程

### 本地升级依赖版本与静态文件同步

如果你要在本地主动升级 Python 或前端依赖版本，而不是单纯拉取最新代码，建议按下面顺序处理：

```bash
uv sync -U
npm outdated
```

Python 依赖如果需要提高 `pyproject.toml` 中声明的版本下限，可按需执行：

```bash
uv add <package>@latest
uv sync -U
```

npm 依赖如果需要升级到新版并同步写回 `package.json` / `package-lock.json`，可按需执行：

```bash
npm install <package>@latest
npm run build:css
```

升级完成后，请同步检查和更新仓库内维护的静态文件：

- 如果升级了 `@alpinejs/csp`，请运行 `npm run copy:alpine` 同步 `static/js/alpinejs.min.js`
- 如果升级了 Prism，请从 Prism 官网重新下载并覆盖 `static/css/prism.css` 和 `static/js/prism.js`
- 如果升级了 Tailwind CSS、DaisyUI 或其他会影响样式输出的前端依赖，请重新生成 `static/css/output.css`

```bash
npm run copy:alpine
```


完成依赖升级和静态文件同步后，建议执行基本验证：

```bash
uv run manage.py check
uv run ruff check .
uv run pytest <受影响的 app 或测试路径>
```

提交代码时，通常需要一并提交这些文件中的实际变更：

- `pyproject.toml`
- `uv.lock`
- `package.json`
- `package-lock.json`
- `static/css/output.css`
- `static/js/alpinejs.min.js`
- `static/css/prism.css`
- `static/js/prism.js`

如果这次升级同时包含项目代码或基础数据调整，再按需执行迁移和数据导入。例如：

```bash
uv run manage.py migrate
uv run manage.py loaddata core/default
```

### 生产环境更新流程

后续版本发布到生产服务器时，可按下面顺序执行：

发布到生产服务器前，请确认本次提交已经包含最新的 `static/css/output.css`，以及需要更新的 Alpine.js / Prism 静态文件。

```bash
cd /srv/tms
git pull
uv sync --frozen --no-dev
uv run manage.py migrate
uv run manage.py collectstatic --noinput
sudo systemctl restart tms
```

如果更新中包含基础数据变更，再按需执行对应 `loaddata`。例如：

```bash
uv run manage.py loaddata core/default
```

## 补充说明

- 本项目默认时区为 `Asia/Shanghai`
- 本项目默认语言为 `zh-hans`
- 训练日志、试题、评分表、结果包等主链路资料由 `ArchiveAsset` 统一登记并保存在 `media-private/`
- `media/` 只承载确实公开的上传文件，私有资料不得直接暴露
- 生产服务器默认不安装 npm；前端资源由开发机或 CI 预先构建或同步后随版本发布




