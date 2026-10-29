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

- Python `>=3.13, <3.14`（开发、CI 与部署统一使用 3.13 系列）
- Django 6
- django-htmx
- django-tables2
- django-filter
- django-environ
- PostgreSQL / SQLite
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

- Python `>=3.13, <3.14`（`.python-version` 当前固定为 3.13）
- uv
- Node.js `>=22.12.0` 与 npm（仅开发环境或前端资源构建时需要）

当前生产基线使用 PostgreSQL 17，SQLite 用于本地开发和测试；不再支持 MySQL。

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

#### 开发环境完全重建默认数据

需要清空测试业务并验证最新初始化声明时，使用独立的开发命令：

```powershell
uv run manage.py rebuild_dev_database --dry-run
uv run manage.py rebuild_dev_database
uv run manage.py createsuperuser
```

`rebuild_dev_database` 仅允许在 `DEBUG=True` 的单数据库、无数据库路由配置下执行，支持 SQLite 和 PostgreSQL。先停止开发服务及其他数据库写入进程，再查看预览中的目标数据库、逐表记录数量及将重建的默认目录；输入完整的 `yes` 后执行。自动化测试可用 `--yes` 跳过询问，但仍显示预览；`--dry-run` 始终只读。

该命令清空全部应用表中的业务数据、账号（包括超级管理员）、会话及配置，保留表结构和迁移记录。随后恢复 Django 内容类型、权限、站点及当前 Bootstrap 声明的默认数据，不重放历史数据迁移，因此不会重新引入旧角色清单。清空和初始化在同一数据库事务内执行，初始化失败时整体回滚。存在未应用迁移或当前应用之外的表时拒绝执行；应先正常执行 `migrate` 并核实数据库范围。

上传文件保留，但对应附件记录会清空，文件不会自动重新关联。命令不创建任何账号或默认密码，完成后通过 `createsuperuser` 创建新管理员。它与保留既有业务数据的 `bootstrap_tms --force` 用途不同，不用于生产部署。

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
Caddy（外层 Basic Auth）
  ↓
Gunicorn（127.0.0.1:8010）
  ↓
Django
  ↓
PostgreSQL
```

生产服务器只需要 Python 3.13、uv、Caddy 和 PostgreSQL；不安装 Node/npm，前端构建产物必须已经提交。
正式拓扑采用 `/srv/tms/releases/<release-id>` 不可变 release、root 管理的 `/srv/tms/current` 原子链接，以及代码目录之外的共享上传目录。

### 自动化入口

```bash
sudo tms-deploy inspect
sudo tms-deploy plan --revision develop --first-install  # 仅首次部署
sudo tms-deploy plan --revision develop                  # 日常升级
sudo tms-deploy apply <plan-id> --confirm-sha <完整SHA>
sudo tms-deploy verify
sudo tms-deploy manage check
sudo tms-deploy manage bootstrap_tms --dry-run
```

支持 `TMS_TLS_MODE=automatic`（公网 Caddy 自动证书）和 `TMS_TLS_MODE=acme-sh`
（内网 DNS-01 证书，由 acme.sh 续期并通知 Caddy）。acme.sh 初始化、权限和续期 hook 见部署手册第 12 节。
日常代码更新可使用独立 `tms-update plan/apply/verify/status`；开发端依赖更新可运行
`uv run --locked --no-sync scripts/update_dependencies.py all --dry-run`，详见手册第 13 节。
升级默认完整备份；本次无需备份时，可在 `tms-deploy apply` 或 `tms-update apply` 后显式添加 `--skip-backup`，其余校验、迁移和验收照常执行。
可配置 `TMS_BASIC_AUTH_TRUSTED_CIDRS="10.21.57.0/24"` 让可信来源网段跳过 Caddy Basic Auth，其他客户端仍需认证；
默认值为空，要求全站认证。此设置不跳过 Django 登录和权限，适用的源地址判断与代理限制见手册第 7 节。

`plan` 可解析分支，但生成计划后固定完整 SHA；`apply` 不接受浮动分支。审查后的
[`scripts/deploy_tms.sh`](scripts/deploy_tms.sh) 应安装为 root 所有的 `/usr/local/sbin/tms-deploy`，
日常部署不得直接 `sudo` 执行浮动分支里的脚本。

生产管理命令使用 `sudo tms-deploy manage <命令> [参数...]`：自动固定当前发布目录、加载
`/etc/tms/tms.env` 并以 `tms` 运行现有 Python 3.13 虚拟环境，不自动同步依赖。
开发、CI 和部署统一使用 Python 3.13 系列；不要在生产发布目录执行普通 `uv run`，也不要在其中创建 `.env`。
`bootstrap_tms` 先用 `--dry-run` 查看预览，实际执行时保留命令自身的交互确认；数据库迁移继续走部署流程。

### 生产环境变量

运行配置位于 `/etc/tms/tms.env`，公共与私有上传均位于代码目录之外：

```env
SECRET_KEY=<由首次部署生成的强随机值>
DEBUG=False
ALLOWED_HOSTS=test.itnsa.cn,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://test.itnsa.cn
DATABASE_URL=postgres://tms_app:<运行期密码>@127.0.0.1:5432/tms
CACHE_TIMEOUT=300
UPLOAD_MAX_SIZE_MB=100
MEDIA_ROOT=/srv/tms/shared/media
PRIVATE_MEDIA_ROOT=/srv/tms/shared/media-private
NOTES_ROOT=/srv/tms/shared/media-private/notes
TRUST_X_FORWARDED_PROTO=True
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
SAMBA_INTEGRATION_ENABLED=False
SAMBA_ASYNC_OPERATIONS_ENABLED=False
```

生产首次只使用 `tms_migrator` 执行迁移，运行期 `tms_app` 只有 schema usage、表 DML 与序列权限。
`bootstrap_tms` 在首次部署时显式 dry-run 后执行，提供选手、教练、班务默认 Group 及权限组合；成员、教练技术领域和注册默认组仍由管理员显式配置。升级不会自动替换现有角色授权，详见用户与权限手册。

Caddy 只直接提供：

- `/static/` → 当前 release 的 `staticfiles/`
- `/media/` → `/srv/tms/shared/media/`

不要直接提供 `/srv/tms/shared/media-private/`。

安装稳定入口、首次部署、日常升级、权限模型、Basic Auth、备份恢复、回滚和 AI 确认边界见
[`docs/developer/deploy-tms-production.md`](docs/developer/deploy-tms-production.md)。

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
