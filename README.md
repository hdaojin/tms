# TMS 竞赛训练管理系统

TMS（Training Management System）是一个面向技能竞赛训练场景的 Django 单体应用，用于统一管理训练过程、竞赛与考核资料、技能标准、评分结果、考点证据、会议记录、通知公告和用户角色权限。

项目当前围绕“技术领域/WSOS—稳定 Skill—竞赛与考核/考点证据/训练任务—评分与执行结果—技能分析—教练人工调整”组织核心业务，长期目标是把历届竞赛与训练数据沉淀为可复用、可分析的训练知识体系。

## 核心业务链路

```text
TechnicalDomain / WSOS
        ↓
       Skill
      ↙    ↘
 Evidence  TrainingTask
    ↑          ↓
Assessment  TaskExecution
    ↓          ↓
 Scoring   TrainingLog
    ↓
Skill performance → Coach review → 人工调整后续计划
```

核心原则：

- `Skill` 是跨技能树版本稳定的能力本体；技能树节点只负责版本内组织，不承载历史评分或训练事实。
- `TechnicalDomain` 是训练组织和权限范围轴，WSOS 是标准映射轴；评测模块不是技术领域。
- 正式竞赛、选拔赛、交流赛、模拟赛和训练考核统一使用 `Assessment`，资料由所属业务 APP 管理，不使用全局泛型资料资产模型。
- 技能表现从真实评分结果经已批准 Evidence 和映射动态反推；训练完成不等于掌握度。
- 系统提供事实与分析，后续训练计划由教练人工判断和调整，不自动生成或改写。

更完整的领域术语和业务不变量见 [`CONTEXT.md`](CONTEXT.md)。

## 技术栈

### 后端

- Python `>=3.13, <3.15`（仓库默认使用 3.14）
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
- FilePond 5 beta

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

- **标准体系**：技能项目、技术领域、稳定技能、技能树版本和 WSOS 映射。
- **竞赛与考核**：竞赛与考核系列、级别、Assessment、评测模块、参与人员和私有业务资料。
- **评分管理**：评分方案、评分表导入、评分点和统一评分结果；参赛身份由竞赛与考核参与人员统一维护。
- **考点证据**：管理可审核 Evidence 及其与稳定 Skill 的加权映射。
- **训练管理**：训练周期、计划、任务、选手执行、教练反馈和正式训练日志。

```text
TechnicalDomain / WSOS
        ↓
       Skill
      ↙    ↘
 Evidence  TrainingTask
    ↑          ↓
Assessment  TaskExecution
    ↓          ↓
 Scoring   TrainingLog
    ↓
Skill performance → Coach review
```

### 业务扩展

- **专业词库**：专业词库、词条提案、词汇学习会话和学习统计。
- **世赛论坛**：WorldSkills 论坛信息的中文翻译、主题归档、重要/官方/未读信息和翻译工作台。
- **意见反馈**：提交 Bug、功能需求、意见建议和投诉，支持匿名、私密、附件和处理结果跟踪。
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
assessments
training
scoring
evidence
glossary
worldskills_forum
feedback
notes
meetings
notices
behaviors
event_countdown
```

`demo` 仅在 `DEBUG=True` 时加载。

## 环境要求

- Python `>=3.13, <3.15`（`.python-version` 当前固定为 3.14）
- uv
- Node.js `>=22.12.0` 与 npm（仅开发环境或前端资源构建时需要）

当前生产基线使用 PostgreSQL 17；项目也保留 MySQL 驱动，SQLite 用于本地开发和测试。

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
npm ci
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

### 5. 初始化默认业务目录

```bash
uv run manage.py bootstrap_tms --dry-run
uv run manage.py bootstrap_tms
```

该命令先执行只读预检并输出完整预览，确认后才创建新环境缺失的出厂业务目录；默认模式可安全重复执行，并保留管理员已经修改的名称、排序、启用状态或其他受管配置。`--dry-run` 只预览、不询问且不写数据库。正常部署不在应用启动时自动执行该命令。

需要明确恢复 Bootstrap 声明的出厂受管值时，可以先预览再执行强制覆盖：

```bash
uv run manage.py bootstrap_tms --force --dry-run
uv run manage.py bootstrap_tms --force
```

`--force` 仍会先输出预览并要求确认，只按稳定业务键更新声明字段，不删除数据库中的额外业务目录，也不改变记录主键或稳定代码。生产环境执行前应先备份数据库。自动化场景可附加 `--yes` 跳过确认，但不会跳过预览或预检。

### 6. 创建超级管理员

```bash
uv run manage.py createsuperuser
```

### 7. 构建前端资源

开发时建议单独启动 Tailwind 监听：

```bash
npm run watch:css
```

完整同步第三方浏览器资源并构建 CSS：

```bash
npm run build:frontend
```

只重新构建 CSS：

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

# 完整前端构建、测试和格式检查
npm run build:frontend
npm run test:frontend
npm run format:frontend:check
```

`format:frontend` / `format:frontend:check` 只覆盖前端构建配置和脚本，避免一次性改写尚未建立统一格式基线的历史模板。模板格式化应按实际变更范围显式执行，并单独检查模板差异。

涉及模板或前端 class 变化时，应重新执行 `npm run build:css` 并提交 `static/css/output.css` 的实际变化。

## 开发环境更新依赖

依赖升级只在开发环境进行。`pyproject.toml` / `uv.lock` 和 `package.json` / `package-lock.json` 必须成对审查并提交；不要手工编辑锁文件，也不要在生产服务器现场解析新版本。

### 更新 Python 包

先查看当前依赖树中可更新的包：

```bash
uv tree --outdated
```

只升级一个包时，优先保持其他包的锁定版本不变：

```bash
uv lock --upgrade-package <包名>
uv sync --locked
```

确认需要整体升级时再重新解析全部 Python 依赖：

```bash
uv lock --upgrade
uv sync --locked
```

新增或删除依赖仍通过 uv 管理：

```bash
# 运行时依赖
uv add <包名>
uv remove <包名>

# 开发依赖
uv add --dev <包名>
uv remove --dev <包名>
```

升级后检查 `pyproject.toml` 与 `uv.lock` 的实际变化，并按影响范围运行验证：

```bash
git diff -- pyproject.toml uv.lock
uv lock --check
uv run manage.py check
uv run ruff check .
uv run pytest <受影响的 app 或测试路径>
```

跨多个核心依赖或升级 Django 时，应运行全量 `uv run pytest` 和 migration drift 检查。生产部署使用 `uv sync --locked --no-dev`，确保声明与锁文件一致且不安装开发依赖。

### 更新前端组件

先查看已安装、版本范围内可更新和上游最新版本：

```bash
npm outdated
```

在现有 `package.json` 版本范围内更新 lockfile 可使用：

```bash
npm update
```

升级指定组件或跨主版本时，应显式更新开发依赖声明。项目所有 npm 包都是开发或构建依赖：

```bash
npm install --save-dev <包名>@<版本>

# FilePond 按项目约定继续跟随 v5 beta channel
npm install --save-dev filepond@beta
```

依赖更新后必须同步随仓库部署的浏览器资源、重建 CSS 并检查资源一致性：

```bash
npm run build:frontend
npm run test:frontend
npm run format:frontend:check
npm audit
npm audit --omit=dev
```

然后检查依赖声明、锁文件和生成资源的差异：

```bash
git diff -- package.json package-lock.json static/css/output.css static/js static/vendor/filepond
```

`npm ci` 只按 `package-lock.json` 做可复现安装，不用于升级依赖。`npm audit` 检查包括构建工具在内的完整依赖树；`npm audit --omit=dev` 单独确认生产交付边界。不要为消除报告而直接执行破坏性的 `npm audit fix --force`，应先确认上游修复和兼容性。Alpine.js CSP、Mermaid、Mermaid 许可证和 FilePond 由 `npm run build:frontend` 自动同步；Prism 当前仍是仓库内维护的 vendored 资源，不在 npm 同步脚本范围内，升级时需要单独核对下载配置、许可证和实际页面效果。

## 前端静态资源交付

TMS 的生产服务器不要求安装 npm。前端资源应在开发机或 CI 中构建、更新，然后随代码或发布制品一起部署。

主要资源：

- `static/css/output.css`：Tailwind CSS 4 / DaisyUI / Iconify 构建产物。
- `static/js/alpinejs.min.js`：项目使用的 Alpine.js CSP build。
- `static/js/app.js`、`static/js/alpine-components.js`：项目公共前端逻辑。
- `static/css/prism.css`、`static/js/prism.js`：代码高亮资源。
- `static/js/mermaid.min.js`、`static/js/notes-mermaid.js`：教学笔记 Mermaid 渲染资源。
- HTMX 运行时由 `django-htmx` 提供，并在 `collectstatic` 时一并收集。

更新 Tailwind CSS、DaisyUI、Iconify 或模板中的相关 class 后，需要重新构建 CSS。更新 Alpine.js CSP、Mermaid 或 FilePond 后，也应通过统一脚本同步仓库中的对应静态文件和许可证文件。

所有 npm 包均为开发或构建依赖，生产服务器不从 `node_modules/` 提供资源。执行 `npm run build:frontend` 会统一同步 Alpine.js CSP、Mermaid、Mermaid 许可证和 FilePond，并生成 `static/css/output.css`；`npm run test:frontend` 会检查仓库静态资源与 lockfile 安装结果是否一致。

## 文件与权限

项目区分公共和私有上传目录：

- `media/`：适合公开或无需对象级鉴权的资源，可由 Nginx、Caddy 等 Web 服务器直接提供。
- `media-private/`：用于考核资料、竞赛资料、学习资料等私有内容，只允许通过具有权限检查的 Django view 提供访问。

生产环境不要把 `media-private/` 直接映射为公开静态目录。

## 生产环境部署

推荐架构：

```text
Client
  ↓
Nginx / Caddy
  ↓
Gunicorn
  ↓
Django
  ↓
PostgreSQL / MySQL
```

生产服务器通常只需要 Python、uv、反向代理/Web 服务器、Gunicorn 和数据库服务；npm 构建应在部署前完成。

### 1. 拉取代码并安装依赖

```bash
git clone git@github.com:hdaojin/tms.git /srv/tms
cd /srv/tms

uv sync --locked --no-dev
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
uv run manage.py bootstrap_tms
uv run manage.py createsuperuser
```

后续版本部署通常执行：

```bash
uv run manage.py migrate
```

`bootstrap_tms` 主要用于新环境初始化。命令会先预览并确认；默认模式不覆盖已有目录项的管理员配置，也不删除额外数据。后续版本只有在发布说明明确要求补充出厂目录时才需要再次显式执行。

如需恢复 Bootstrap 声明的受管出厂值，先备份数据库并执行：

```bash
uv run manage.py bootstrap_tms --force --dry-run
uv run manage.py bootstrap_tms --force
```

自动化部署可使用 `--yes`，但该选项只跳过人工确认，不跳过完整预览和预检。

数据库结构变更应通过 Django migration 管理；部署前应按实际环境做好数据库和上传文件备份。

权限包定义发生变化后，先检查原生权限投影差异，确认后再应用：

```bash
uv run manage.py reconcile_permission_assignments
uv run manage.py reconcile_permission_assignments --apply
```

对账命令默认只报告差异；确认输出后才执行 `--apply`。权限包定义位于 `core/config/permission_bundles.yml`。`migrate_private_media` 等历史切换命令不是常规部署步骤，只有发布说明明确要求时才按“先预检、后应用”的方式执行。

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

实际生产环境建议通过 systemd 或其他进程管理器托管 Gunicorn，再由 Nginx、Caddy 等 Web 服务器进行反向代理。

Web 服务器可以直接提供：

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

升级 Alpine.js、Mermaid、FilePond 或其他 npm 前端依赖时执行：

```bash
npm run build:frontend
npm run test:frontend
```

## 开发文档约定

项目长期工程规则以 [`AGENTS.md`](AGENTS.md) 为准；领域术语和业务不变量以 [`CONTEXT.md`](CONTEXT.md) 为准。重要架构选择记录在 [`docs/adr/`](docs/adr/) 中。

如果代码、迁移、测试和文档之间出现明显不一致，应以实际代码和测试确认当前行为，并在同一变更中修正文档，避免继续传播过时的阶段性说明。

## License

许可证信息见 [`LICENSE`](LICENSE)。
