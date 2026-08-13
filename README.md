# TMS 竞赛训练管理系统

TMS（Training Management System）是一个面向技能竞赛训练场景的 Django 单体应用，用于统一管理训练过程、竞赛与考核资料、技能标准、评分结果、知识点映射、会议记录、通知公告和用户角色权限。

项目当前围绕“标准—事件—试题/评分—考点—技能—训练分析”组织核心业务，长期目标是把历届竞赛与训练数据沉淀为可复用、可分析的训练知识体系。

## 核心业务链路

```text
技能项目 / 标准技能树
        ↓
赛事或考核事件
        ↓
试题 / 评分方案
        ↓
考点证据
        ↓
技能点映射
        ↓
评分结果
        ↓
训练分析与反馈
```

核心原则：

- 技能项目和标准技能树表达长期能力体系，不随某一届比赛或某个 A/B/C/D 模块变化而重复创建。
- 赛事、选拔赛、训练考核、模拟赛等统一抽象为“事件”。
- 原始试题、评分表、结果包、训练资料等统一通过资料资产进行登记和归档。
- 评分结果通过考点证据和技能映射反推技能表现，为后续训练重点、难点和查漏补缺提供数据基础。

更完整的领域术语和业务不变量见 [`CONTEXT.md`](CONTEXT.md)。

## 技术栈

### 后端

- Python 3.13+
- Django 6
- django-htmx
- django-tables2
- django-filter
- django-environ
- PostgreSQL / MySQL / SQLite
- Gunicorn

### 前端

- Tailwind CSS 4
- DaisyUI 5
- Alpine.js CSP build
- Iconify Tailwind 4
- HTMX
- Mermaid
- Prism

### 开发工具

- uv
- Ruff
- pytest / pytest-django
- npm
- Prettier

## 当前功能

### 平台基础

- **用户与权限**：基于 Django `auth.User`、Group、Permission 的账户与角色权限体系。
- **站点基础能力**：统一导航、主题、布局、上传限制、公共/私有文件存储等。
- **Samba 集成**：提供可选的 Samba 管理能力，默认关闭系统级集成和异步操作。

### 标准、竞赛与训练主链路

- **标准体系**：技能项目、能力领域、标准技能树版本和技能节点。
- **赛事与考核**：赛事系列、赛事级别、事件、事件模块和参与人员。
- **试题内容**：事件模块下的试题及结构化试题要求。
- **评分管理**：评分方案、评分表导入、评分点、参评对象和评分结果。
- **考点知识**：统一管理考点证据，以及考点与标准技能点之间的映射关系。
- **资料归档**：试题、评分表、结果包、训练资料等文件的统一资产登记与权限控制。
- **训练管理**：训练周期、训练日志和提交统计。

### 业务扩展

- **专业词库**：专业词库、词条提案、词汇学习会话和学习统计。
- **世赛论坛**：WorldSkills 论坛信息的中文翻译、主题归档、重要/官方/未读信息和翻译工作台。
- **教学笔记**：教学笔记仓库、Markdown 内容展示、代码高亮和 Mermaid 图形渲染。
- **会议记录**：会议资料与记录管理。
- **通知公告**：通知发布与浏览。
- **奖惩管理**：学生奖惩记录。
- **赛事倒计时**：用于 WorldSkills 等赛事或其他活动的通用倒计时页面。

当前主要 Django APP：

```text
core
accounts
samba
standards
archives
events
training
scoring
examcontent
knowledge
glossary
worldskills_forum
notes
meetings
notices
behaviors
event_countdown
```

`demo` 仅在 `DEBUG=True` 时加载。

## 环境要求

- Python 3.13+
- uv
- Node.js 与 npm（仅开发环境或前端资源构建时需要）

生产环境推荐使用 PostgreSQL 或 MySQL；SQLite 适合本地开发和轻量测试。

## 目录说明

- `tmsproject/`：Django 项目配置。
- `core/`：平台公共能力、导航、权限、上传、通用组件等。
- 各业务 APP：按领域划分模型、服务、查询、视图、表单、模板和测试。
- `templates/`：项目级布局与共享模板组件。
- `static/`：源码静态资源以及随仓库交付的前端构建产物。
- `staticfiles/`：`collectstatic` 输出目录。
- `media/`：可由 Web 服务器直接提供的公共上传文件。
- `media-private/`：需要经过 Django 权限检查后访问的私有文件。
- `docs/adr/`：重要架构决策记录。
- `docs/developer/`：开发文档。
- `docs/user-manual/`：用户手册。
- `AGENTS.md`：项目长期工程规范和 Agent 开发约束。
- `CONTEXT.md`：业务术语、领域语义和核心业务不变量。

> 所有 Django / uv 命令应从仓库根目录执行。若 `.env` 中使用相对 SQLite URL（例如 `sqlite:///db.sqlite3`），从子目录运行命令可能连接到错误的数据库文件。

## 开发环境快速开始

### 1. 克隆项目

```bash
git clone git@github.com:hdaojin/tms.git
cd tms
git switch develop
```

项目在 `pyproject.toml` 中将 uv 缓存固定到仓库内的 `.uv-cache/`，正常使用 `uv sync`、`uv run ...` 即可。

### 2. 安装依赖

```bash
uv sync
npm install
```

### 3. 配置环境变量

Linux / macOS：

```bash
cp .env.example .env
```

PowerShell：

```powershell
Copy-Item .env.example .env
```

`.env.example` 默认提供适合本地开发的 SQLite 配置。

### 4. 初始化数据库

```bash
uv run manage.py migrate
```

### 5. 导入基础数据

```bash
uv run manage.py loaddata core/default accounts/default behaviors/default
```

### 6. 创建超级管理员

```bash
uv run manage.py createsuperuser
```

### 7. 构建前端样式

开发时建议单独启动 Tailwind 监听：

```bash
npm run watch:css
```

只构建一次：

```bash
npm run build:css
```

### 8. 启动开发服务器

```bash
uv run manage.py runserver
```

默认访问地址：

```text
http://127.0.0.1:8000/
```

## 常用开发命令

```bash
# Django system check
uv run manage.py check

# 代码检查
uv run ruff check .

# 全量测试
uv run pytest

# 聚焦测试
uv run pytest <app-or-test-path>

# 检查是否遗漏 migration
uv run manage.py makemigrations --check --dry-run

# 创建并应用 migration
uv run manage.py makemigrations
uv run manage.py migrate

# 前端样式
npm run watch:css
npm run build:css
```

涉及模板或前端 class 变化时，应重新执行 `npm run build:css` 并提交 `static/css/output.css` 的实际变化。

## 前端静态资源交付

TMS 的生产服务器不要求安装 npm。前端资源应在开发机或 CI 中构建、更新，然后随代码或发布制品一起部署。

主要资源：

- `static/css/output.css`：Tailwind CSS 4 / DaisyUI / Iconify 构建产物。
- `static/js/alpinejs.min.js`：项目使用的 Alpine.js CSP build。
- `static/js/app.js`、`static/js/alpine-components.js`：项目公共前端逻辑。
- `static/css/prism.css`、`static/js/prism.js`：代码高亮资源。
- `static/js/mermaid.min.js`、`static/js/notes-mermaid.js`：教学笔记 Mermaid 渲染资源。
- HTMX 运行时由 `django-htmx` 提供，并在 `collectstatic` 时一并收集。

更新 Tailwind CSS、DaisyUI、Iconify 或模板中的相关 class 后，需要重新构建 CSS。更新 Alpine.js CSP、Mermaid、Prism 等前端依赖时，也应同步更新仓库中的对应静态文件和许可证文件。

## 文件与权限

项目区分公共和私有上传目录：

- `media/`：适合公开或无需对象级鉴权的资源，可由 Nginx 直接提供。
- `media-private/`：用于考核资料、竞赛资料、学习资料等私有内容，只允许通过具有权限检查的 Django view 提供访问。

生产环境不要把 `media-private/` 直接映射为公开静态目录。

## 生产环境部署

推荐架构：

```text
Client
  ↓
Nginx
  ↓
Gunicorn
  ↓
Django
  ↓
PostgreSQL / MySQL
```

生产服务器通常只需要 Python、uv、Nginx、Gunicorn 和数据库服务；npm 构建应在部署前完成。

### 1. 拉取代码并安装依赖

```bash
git clone git@github.com:hdaojin/tms.git /srv/tms
cd /srv/tms

uv sync --frozen --no-dev
```

生产环境应部署经过确认的发布分支或 tag，而不是依赖服务器现场修改代码。

### 2. 配置环境变量

```bash
cp .env.example .env
```

生产环境至少需要确认：

```env
SECRET_KEY=replace-with-a-strong-secret-key
DEBUG=False
ALLOWED_HOSTS=tms.example.com,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://tms.example.com
DATABASE_URL=postgres://tms:password@127.0.0.1:5432/tms
CACHE_TIMEOUT=300
UPLOAD_MAX_SIZE_MB=100
PRIVATE_MEDIA_ROOT=/srv/tms/media-private
SAMBA_INTEGRATION_ENABLED=False
SAMBA_ASYNC_OPERATIONS_ENABLED=False
```

注意：

- `DEBUG=False` 时必须使用真实、强随机的 `SECRET_KEY`。
- `ALLOWED_HOSTS` 和 `CSRF_TRUSTED_ORIGINS` 应按实际域名配置。
- 推荐生产环境使用 PostgreSQL 或 MySQL。
- Samba 系统级集成默认关闭，只有在服务器已完成相应安全配置后才应启用。

### 3. 准备目录

```bash
mkdir -p /srv/tms/staticfiles
mkdir -p /srv/tms/media
mkdir -p /srv/tms/media-private
```

确保运行 Gunicorn 的用户拥有所需目录权限。

### 4. 初始化或升级数据库

首次部署：

```bash
uv run manage.py migrate
uv run manage.py loaddata core/default accounts/default behaviors/default
uv run manage.py createsuperuser
```

后续版本部署通常执行：

```bash
uv run manage.py migrate
```

数据库结构变更应通过 Django migration 管理；部署前应按实际环境做好数据库和上传文件备份。

### 5. 收集静态文件

确认部署包已经包含最新前端构建产物后执行：

```bash
uv run manage.py collectstatic --noinput
```

### 6. 执行部署检查

```bash
uv run manage.py check --deploy
```

### 7. 启动 Gunicorn

```bash
uv run gunicorn tmsproject.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 4
```

实际生产环境建议通过 systemd 或其他进程管理器托管 Gunicorn，再由 Nginx 进行反向代理。

Nginx 可以直接提供：

- `/static/` → `/srv/tms/staticfiles/`
- `/media/` → `/srv/tms/media/`

不要直接提供 `/srv/tms/media-private/`。

## 发布与验证建议

一般代码变更至少执行：

```bash
uv run manage.py check
uv run ruff check .
uv run pytest <受影响的 app 或测试路径>
```

涉及核心领域、跨 APP 流程、权限、统计口径或公共组件时，建议最终执行：

```bash
uv run pytest
uv run manage.py makemigrations --check --dry-run
```

涉及模板、Tailwind、DaisyUI 或 Iconify class 变更时还应执行：

```bash
npm run build:css
```

## 开发文档约定

项目长期工程规则以 [`AGENTS.md`](AGENTS.md) 为准；领域术语和业务不变量以 [`CONTEXT.md`](CONTEXT.md) 为准。重要架构选择记录在 [`docs/adr/`](docs/adr/) 中。

如果代码、迁移、测试和文档之间出现明显不一致，应以实际代码和测试确认当前行为，并在同一变更中修正文档，避免继续传播过时的阶段性说明。

## License

许可证信息见 [`LICENSE`](LICENSE)。
