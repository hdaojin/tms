# AGENTS.md

## 作用与权威边界

本文件是 TMS 仓库的**长期工程约束与架构边界**，是 Codex、Copilot 和其他编码 Agent 的项目级权威来源。

- `AGENTS.md`：规定稳定的工程规则、分层边界、验证要求和安全约束。
- `CONTEXT.md`：规定稳定的业务术语、领域语义和核心业务不变量。
- `docs/adr/`：记录已经做出的重要架构决策；涉及对应领域时必须遵循。
- `.codex/skills/*`：只描述某类任务的**专用、可复用执行工作流**，不得承载通用 TMS 开发规范，也不得复制本文件形成第二套项目规则。
- `.github/copilot-instructions.md`：只做入口提示，不维护第二套规则。

如果文档与当前代码明显漂移，先以实际代码、迁移和测试确认现状，再在同一变更中修正文档；不要继续传播过时约定。

所有面向用户的模型名、表单标签、校验错误、消息、页面文案和用户文档使用中文（`zh-hans`）。默认时区为 `Asia/Shanghai`。

## 当前项目形态

TMS 是基于 Django 6 / Python 3.13 的单体应用。主要前端与交互技术为 django-htmx、django-tables2、Tailwind CSS 4、DaisyUI 5、Alpine.js CSP build 和 Iconify Tailwind 4 插件。

当前 APP 按职责大致分为：

- 平台基础：`core`、`accounts`、`samba`。
- 领域主链路：`standards`、`assessments`、`scoring`、`evidence`、`training`。
- 业务扩展：`glossary`、`worldskills_forum`、`feedback`、`notes`、`meetings`、`notices`、`behaviors`、`event_countdown`。
- `demo` 仅在 `DEBUG=True` 时加载。

领域主链路应保持为：

`技术领域/WSOS -> 稳定 Skill -> Assessment/Evidence/TrainingTask -> ScoringResult/TaskExecution -> Skill 分析 -> 教练人工调整`

具体业务术语和不变量以 `CONTEXT.md` 为准。不要重新引入已经被替换的旧 APP/旧术语（例如旧 `assessments`、`competitions`、`skills`、`traininglogs` 链路）。

- `Skill` 是跨技能树版本稳定的业务本体；`SkillTreeNode` 只负责版本内组织，不把历史 Evidence、TrainingTask 或评分结果绑定到易变节点。
- `TechnicalDomain` 是训练组织和权限范围轴；跨领域 AssessmentModule/TrainingTask 必须通过显式教练分配授权整体编辑。
- 技能历史考查只统计已批准 Evidence 与已批准映射，技能表现从真实评分结果按当前映射动态反推；训练完成不命名为 mastery。
- 系统不自动生成或调整训练计划，分析结果只支持教练人工决策。

## 任务规模与最小修改原则

优先完成用户要求的**最小必要修改**。不要因为发现相邻问题、潜在重构机会、完整业务链路或 CI 中存在更多检查，就自行扩大实现、检查或验证范围。

- 简单任务保持简单：文案、注释、局部模板、单个样式或明确的小型 bug 修复，不执行完整 feature workflow，不机械追踪无关 APP，也不顺手重构邻近代码。
- 只有当修改实际跨越模型、权限、事务、多个 APP、公共组件、统计口径或外部数据流程时，才扩大到完整纵向切片分析。
- 不为“可能以后有用”预先增加抽象、service、selector、配置层或文档结构；先解决当前明确需求。
- 不因为看到旧写法或风格不一致，就在当前任务中统一重构；无关问题可在交付说明中指出，但默认不修改。
- 除非用户明确要求 review、审计或全面优化，不主动把局部修改升级为全仓 review。
- 输出说明与任务规模匹配。小修改用简洁结果说明，不重复复述整套架构、测试体系或项目规范。

`.codex/skills/` 仅用于真正独立、重复且多步骤的专用工作流。普通 TMS 编码、修 bug、模板调整、字段修改和常规 CRUD 不需要额外 skill；遵循本文件即可。

## 开始修改前

1. 先阅读本文件。
2. 涉及领域模型、跨 APP 流程、统计口径或业务术语时，再读 `CONTEXT.md`；有相关 ADR 时一并阅读。
3. 只检查与任务直接相关的实际代码链路。需要理解完整业务流程时，再按 `models.py`、`forms.py`、`services.py`、`selectors.py`、`views.py`、`tables.py`、`urls.py`、templates、tests 和 migrations 扩大范围；不存在的文件跳过。
4. 页面入口或导航变化时检查 `core/config/navigation.yml`。
5. 用户可见行为变化且现有用户文档确实需要同步时，更新 `docs/user-manual/` 对应文档；纯内部修改、小型修复或现有文档不受影响时无需机械更新。
6. 环境、安装、部署和命令细节以 `README.md` 为准。

不要仅凭相邻 APP 的旧写法复制实现；先确认目标 APP 当前是否已经采用 service / selector / 新 layouts / 新导航体系。

## 分层与业务逻辑边界

TMS 继续保持 Django 单体，不为“分层”而引入额外框架；但复杂业务必须保持清晰职责。

### Models

模型负责持久化结构和**单个实体自身**的业务不变量。

- 能由数据库可靠表达的唯一性、条件唯一性和完整性优先使用 `UniqueConstraint`、`CheckConstraint`、字段约束等数据库机制。
- `Model.clean()` 适合实体内的跨字段校验以及需要被 ModelForm 展示的业务错误。
- 不要把跨多个模型的工作流、导入编排、外部副作用或复杂统计塞进 `save()`。
- 不要为新模型机械复制 `save() -> clean()`。Django 的 `save()` 不会自动执行 `full_clean()`；在非 ModelForm 写入边界需要完整模型校验时，应由调用方显式校验，或由 service 提供明确入口。保留既有模式时不要无关重构，触碰时必须用测试保护。
- 对并发下必须成立的业务唯一性，不能只依赖 `clean()` 中的 `.exists()` 检查；应尽可能有数据库约束兜底。

### 业务目录、Enum、Registry 与 Bootstrap

**业务目录数据用 Model；程序状态和语义用 Enum。默认业务目录通过 Bootstrap 初始化。**

**如果管理员合理地可以增加一个值，而程序无需因此增加代码，那么它就不应该是 `TextChoices`。**

**如果增加一个值以后程序必须知道“这个值意味着什么、应该怎么处理”，它就应该继续是 Enum 或代码 Registry。**

具体约束：

- 赛事系列、级别、业务类型、可配置角色、反馈分类、来源身份等可运营维护的目录数据使用具体业务 APP 自己的数据库 Model，不使用全局泛型“字典表”。常见字段可包括稳定 `code`、显示 `name`、`order`、`is_active` 以及该目录自身需要的业务属性；不要为了字段相似强行建立跨 APP 的通用目录模型。
- 目录项的 `code` 是机器身份和迁移映射键。已有记录引用后应保持稳定；管理员需要改展示文案时修改 `name`，需要停止新业务使用时优先设置 `is_active=False`，历史对象继续保留外键引用。涉及历史数据的外键通常优先 `PROTECT`，除非该领域已有更明确的删除语义。
- 生命周期状态、审核状态、协议类型、数据来源、结构关系角色（如 primary/related）、实现模式等有限且由程序理解的值域继续使用 `TextChoices` / Enum。新增这类值必须连同状态流转、校验、查询、统计、模板或外部协议处理一起评审，不通过后台“配置一个新值”绕过代码语义。
- Parser、主题、权限包等背后存在 Python 实现、模板/CSS/静态资源或 Django Permission 定义的能力使用代码 Registry/受版本控制的配置。数据库可以保存“启用、默认、显示名、排序”等运行时配置并以稳定 key 引用 Registry，但数据库不得创造代码中不存在的实现。
- `bootstrap_tms` 是生产/新环境默认业务数据的统一显式初始化入口。Bootstrap 必须幂等、可测试、不会覆盖已存在记录的管理员修改；默认使用稳定 key/code `get_or_create(..., defaults=...)` 创建缺失的出厂数据。不要在 request、selector、普通读取 service、`AppConfig.ready()` 或 signal 中通过 `get_or_create()` 隐式补种子。
- Bootstrap 只创建已经有明确业务依据的出厂数据；“模型可配置”不等于“必须预置默认行”。仓库没有权威默认值时保持空目录，由管理员按业务建立，不得由 Agent 自行发明。
- 正常部署不得自动反复执行 Bootstrap。README 的新环境初始化流程可以显式执行一次；后续如确需新增强制基础数据，应通过明确的数据迁移或发布说明处理，不能依靠每次启动时偷偷同步。
- 历史 `RunPython` 数据迁移继续作为迁移历史快照保留。数据迁移使用 `apps.get_model()` 的历史模型，不直接导入当前 bootstrap 定义；旧迁移里曾经写过的 seed 不代表今后继续以 migration 维护业务目录默认值。
- Fixture 可以用于测试、演示或显式数据交换，但不再作为生产默认业务数据的权威初始化机制。生产 README 不应要求通过多个 `loaddata .../default` 拼装系统初始状态。
- Django `auth.Group` / `GroupProfile` 本身就是数据库角色模型，不新增平行 Role Enum/Model。`core/config/permission_bundles.yml` 描述随代码版本发布的业务能力到 Django Permission 的映射，继续留在代码配置；Group 只是选择和组合这些能力。

### Services

跨模型写操作、导入确认、状态迁移、文件归档联动和跨 APP 业务流程优先放到 `<app>/services.py` 或清晰命名的 service 模块。

- 多模型写操作需要原子性时使用 `transaction.atomic()`。
- service 应表达业务动作，例如“确认评分表导入”“从评分点生成考点证据”，而不是成为通用工具杂物箱。
- 复杂导入建议采用“解析/预览 -> 校验 -> 确认落库”的两阶段模式；保留原始快照和校验报告，避免解析器直接隐式修改正式数据。
- 需要幂等的导入/同步入口必须显式设计幂等键、覆盖策略和重复执行行为。

`scoring/services.py` 当前的评分表导入/确认流程可作为跨模型事务工作流的主要参考。

### Selectors / Query Logic

可复用的复杂读取、统计、报表和跨关系查询优先放在 `<app>/selectors.py`；简单 queryset 可以留在 view/model manager。

- 使用 `select_related()` / `prefetch_related()` 控制查询数。
- 对树、递归关系和统计汇总特别关注 N+1 与重复遍历；不要为了代码简短在循环中递归发查询。
- 统计口径必须复用统一 selector，而不是在多个页面分别重写。

`standards/selectors.py` 中的技能闭环统计可作为读取层拆分的参考，但新增统计仍需检查查询复杂度。

### Forms / Views / Templates

- Form 负责输入规范化和面向用户的校验反馈，复用 `StyledFormMixin`。
- View 负责 HTTP、权限、service/selector 调用和响应选择；尽量保持薄，不复制核心业务逻辑。
- 类视图复用 `TitleMixin`，设置 `title` 和 `title_icon`。
- 列表页优先复用 `BaseTable`、`BaseDateColumn`、`BaseDateTimeColumn`、`ActionsColumn` 和 django-tables2 `SingleTableView`/现有封装。
- 通用 CRUD 页面优先复用 `templates/common/` 与 `templates/components/` 现有组件，而不是复制整页模板。

## 用户、角色与权限

- 保持 Django 默认 `auth.User`；不要引入自定义 User 模型。
- 全局登录由 `LoginRequiredMiddleware` 强制；公开 view 必须显式使用 `login_not_required`。
- Django Permission 是运行时唯一授权事实来源；业务权限包只用于部署期授权配置与原生权限投影。
- Group 名称和 `GroupProfile.codename` 不用于业务授权；codename 只保留给 Samba 等技术集成。
- TechnicalDomain 是 Group 级对象范围；领域权限必须由同一个 Group 同时提供对应 Django Permission 与 `TechnicalDomainGroupScope`，不得把不同 Group 的权限和范围串联。
- superuser 是唯一可绕过 TechnicalDomain Group Scope 的全局管理员；普通用户的直接权限不能绕过 Group Scope。
- 对象范围统一由 selector/policy 收窄；基础 Permission 表示默认或本人范围，`*_all` 只扩大范围。
- 对象级访问复用 `OwnerRequiredMixin`、`PermissionRequiredMixin`、`SuperuserRequiredMixin`，或在 service/view 中实现更明确的权限入口。
- 模板与兼容层可显示 `user.display_name` / `user.full_info`；新增 Python 逻辑优先使用 `accounts.services.users.get_user_display_name()` / `get_user_full_info()`。

## 文件、归档与敏感数据

- 共享上传限制、扩展名、路径和存储规则集中在 `core/constants.py` 与 `core/uploads.py`；不要在各 APP 重写一套临时 validator/storage。
- 前端文件上传统一复用 `templates/components/file_upload.html`；FilePond v5 作为通用上传组件的底层实现细节，业务 APP 不直接初始化或依赖其 API。服务端 `MultipleFileField` / `UploadSpec` 仍是上传校验的最终事实来源。详细约定见 `docs/developer/file-upload.md` 与 ADR 0004。
- 私有或敏感文件使用 `PrivateMediaStorage` / `settings.PRIVATE_MEDIA_ROOT`，必须经过有权限检查的 Django view 提供，不得由 Web 服务器直接暴露。
- 业务文件必须由其业务 APP 拥有；跨 APP 统一的是 storage、upload、validation、cleanup 等技术能力，不建立全局泛型文件资产模型。
- 多文件表单复用 `core.forms.fields.MultipleFileField` / `MultipleFileInput`。
- 文件模型按项目既有机制注册清理 signal；删除/替换行为必须有测试。
- `GenericForeignKey` 不能提供数据库外键完整性；新增泛型绑定时必须明确允许的目标类型，并在 service/model 校验业务归属一致性。
- 不读取、打印、记录或提交 `.env` 中的密钥和原始凭据；测试、日志、模板、异常信息和文档中也不得泄漏。

## URL、导航与模板布局

- APP URL 使用 `app_name` namespace，并由 `tmsproject/urls.py` `include()`。
- 导航的唯一配置入口是 `core/config/navigation.yml`；不要恢复旧 `core/config/menus/*.yml` / `menus.yml` 体系。
- 页面按用途扩展：`templates/layouts/app.html`、`minimal.html`、`auth.html`、`print.html`、`htmx.html`；`templates/base.html` 仅作为兼容/薄入口，不应成为新页面首选布局。
- 优先复用 `templates/components/`，尤其是表单、字段和表格包装组件。

## HTMX

- 使用 `django_htmx.middleware.HtmxMiddleware` 提供的 `request.htmx` 判断 HTMX 请求。
- 同一 URL 同时支持完整页和 fragment 时，明确区分模板响应，不在 view 中复制两套业务查询。
- 若响应内容因 `HX-Request` 不同而不同且经过缓存，必须把 `HX-Request` 纳入 `Vary`/缓存键。
- 复用项目现有 CSRF/HTMX 基础模板配置，不要为局部页面重复注入运行时脚本。
- HTMX 只是传输与局部刷新机制；权限、校验和业务不变量必须在服务器端同样执行。

## Tailwind CSS / DaisyUI / Alpine.js / Iconify

当前项目使用 Tailwind CSS 4 的 CSS-first 配置，入口为 `static/css/main.css`：

- 保持 `@import "tailwindcss"`、`@source`、`@plugin "daisyui"`、`@plugin "@iconify/tailwind4"` 的现有体系；不要回退到 Tailwind 3 风格配置来解决普通页面问题。
- Tailwind 4 按源码文本检测完整 class；模板/JS 中不要通过字符串拼接动态生成 Tailwind class。需要变体时映射到**完整静态 class 字符串**，必要时使用 `@source inline()` 等 Tailwind 4 机制。
- DaisyUI 组件优先使用语义化组件 class，再用 Tailwind utility 做局部布局和微调；保持现有主题体系。
- Iconify 使用完整静态形式，例如 `icon-[tabler--calendar]`；不要拼接 icon 名称。
- 项目继续使用 `@alpinejs/csp`，但脚本组织遵循“**默认外置、按需内联**”，不要把“零 inline JavaScript”当作目标。跨页面复用、较复杂、需要独立测试或持续维护的逻辑优先放入 `static/js/`；页面局部、一次性、很短且与当前模板强耦合的初始化、配置或事件逻辑，如果内联明显更清晰，可以使用 inline `<script>` / `<script type="module">`，简短 `onclick` / `x-on` 也可在确有理由时使用。不得为了形式上消除少量内联代码而制造不必要的全局状态、通用组件或 `data-*` 转发层。`javascript:` URL 仍禁止；若实际启用 HTTP CSP，则同时遵守真实 CSP 的 nonce、hash 和 source 限制。
- 新模板引入新的 Tailwind/Iconify class 后必须重新构建 CSS，并提交 `static/css/output.css` 的实际变化。

框架行为不确定时优先查当前上游官方文档：Django 6、django-htmx、django-tables2、Tailwind CSS 4、DaisyUI 5、Alpine.js CSP 与 Iconify Tailwind 4，而不是依据旧版本经验猜测。

## 常用命令

所有 Django/uv 命令从仓库根目录运行，因为 `.env` 可能使用相对 SQLite URL。

- 安装/同步 Python 依赖：`uv sync`
- 新增 Python 依赖：`uv add <package>`
- Django system check：`uv run manage.py check`
- Ruff：`uv run ruff check .`
- 创建迁移：`uv run manage.py makemigrations`
- 检查是否遗漏迁移：`uv run manage.py makemigrations --check --dry-run`
- 应用迁移：`uv run manage.py migrate`
- 全量测试：`uv run pytest`
- 聚焦测试：`uv run pytest <app-or-test-path>`
- 构建 CSS：`npm run build:css`
- 监听 CSS：`npm run watch:css`

项目 uv cache 固定在 `.uv-cache/`；正常从仓库根目录运行 uv 即可。

## 验证策略

验证必须与改动风险和实际影响范围成比例。**不要因为仓库存在完整 CI 流程，就在每个小修改后机械执行完整 CI。** 优先选择能直接证明本次修改正确的最小验证集合；只有风险升高或局部验证无法建立足够信心时才扩大范围。

- 纯文案、注释、Markdown 文档修改：通常无需运行 pytest、Django check 或全量 Ruff；只检查内容本身和必要的格式/链接。
- 单个模板的纯展示修改：优先做模板相关的最小检查；没有 Python 行为变化时不默认运行 pytest。若新增或修改 Tailwind/Iconify class，则运行 `npm run build:css`。
- 小范围 Python 改动：运行受影响测试 + `uv run ruff check <affected-paths>`；不默认运行全量 pytest。
- Form/View/局部业务行为修改：运行目标 APP 或相关测试；只有需要时再运行 `uv run manage.py check`。
- Model/迁移改动：增加或修改相关测试，并运行 `uv run manage.py makemigrations --check --dry-run`；确需 schema 变化时生成并检查 migration。
- 跨 APP service、权限、公共核心组件、关键统计口径或高风险数据流程改动：运行相关 APP 测试，并根据影响范围决定是否运行全量 `uv run pytest`。只有确有跨仓回归风险时才默认升级为全量测试。
- 仅当修改涉及 Django 项目配置、URL 装配、AppConfig、中间件或 system check 可发现的问题，或准备提交重要改动时，才需要 `uv run manage.py check`；普通局部修改不机械执行。
- 当本次变更涉及模板中的 Tailwind/Iconify class、CSS 源码、Alpine 前端代码、Tailwind/DaisyUI/Iconify 配置或前端依赖时，运行 `npm run build:css` 并检查 `static/css/output.css`；纯 Python、后端配置或文档修改不为 push 机械执行 CSS 构建。

验证失败时先判断失败是否由本次修改引起。不要为了让无关历史失败通过而扩大修改范围。

CI 的基准流程仍为 Ruff -> Django check -> migration drift check -> migrate -> pytest，以及独立的前端 `npm ci` -> `npm run build:css`。CI 是合并级安全网，不等于每次本地小修改都必须完整重放。

## 性能与可维护性检查

仅在改动涉及对应读取/写入路径，或任务本身要求 review/优化时进行以下检查；不要把它机械应用到纯文案、样式或无关的小修改。

- 列表/详情页是否出现可预见的 N+1。
- 树形/递归统计是否在循环中反复查询或重复遍历。
- 大文件是否在无文件变化的普通 `save()` 中被重复读取/哈希。
- 导入是否能安全重复执行，失败是否完整回滚。
- GenericForeignKey 是否出现“对象存在但业务归属不一致”的悬空关系。
- 权限是否只在模板隐藏而没有后端校验。
- 同一业务规则是否被复制到 model/form/view/service 多处并开始漂移。

先做有证据的优化；不要顺手重构与当前任务无关的模块。

## 文档同步

- 用户可见功能变化且已有用户文档受影响：更新 `docs/user-manual/`。
- 纯内部重构、小型 bug 修复、文案或样式调整，如果用户文档没有因此失真，无需为了“流程完整”机械更新文档。
- 核心领域术语、统计口径或业务不变量变化：更新 `CONTEXT.md`。
- 重要架构决策或长期权衡变化：新增/更新 `docs/adr/`。
- APP、导航、布局或标准开发路径发生变化：同步本文件；只有存在对应专用 skill 时才同步其 reference，不创建通用开发 skill 的重复副本。

## Git 与工作区安全

- 工作区可能存在用户尚未提交的修改；不要回滚或覆盖不是你创建的变更。
- 除非用户明确要求，不使用 `git reset --hard`、`git checkout --` 等破坏性命令。
- migrations、`uv.lock`、`package-lock.json`、`static/css/output.css` 等生成文件在相关源码变化需要它们时视为有意变更。
- 修改范围保持聚焦；不要为了“统一风格”顺便重构无关 APP。
