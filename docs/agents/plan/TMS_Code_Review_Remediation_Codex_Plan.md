# TMS 代码审阅整改实施 Plan（Codex 可执行）

> 状态：待执行  
> 仓库：`hdaojin/tms`  
> 基准分支：`develop`  
> 审阅基准提交：`81c4a673a1856cf19ed61f8af0d1114146de0fce`（2026-11-14）  
> 计划编制日期：2026-11-15  
> 适用环境：Django 6 / Python 3.13 / uv / PostgreSQL（生产）/ SQLite（开发与部分 CI）/ django-htmx / django-tables2 / Tailwind CSS 4 / DaisyUI 5 / Alpine.js CSP / Iconify  
> 性质：**修复和加固现有系统；不新增业务需求，不做全局重构**。

## 0. Codex 执行指令（优先阅读）

你正在 `hdaojin/tms` 仓库工作。**本文件就是实施任务清单，请直接执行可在代码仓库中完成的事项**，不要仅输出另一份实施建议。执行时遵守以下边界：

1. **先读** `AGENTS.md`；涉及训练业务时读 `CONTEXT.md` 和相关 ADR；涉及 AI 更名时读 `docs/developer/ai-app-rename-migration.md`。以开始执行时的实际代码、测试和迁移为准，不要盲从本计划中的历史行号。前端样式变更按项目已有技能/规范处理。
2. **开始前核对**当前分支、HEAD、工作区；若基准提交之后已修复某问题，核验后标记“已完成”，不得重复改动。保留用户现有的未提交修改。不要使用 `git reset --hard`、`git checkout --`，不要强行覆盖本地文件。
3. 按 **P0 → P1 → P2 → P3** 顺序实施。先复现，再最小修复；每个阶段完成后运行对应的聚焦测试。此任务是跨 APP 的集中整改，全部代码变更完成后应执行项目级 CI 等价验证（如本地能力允许）。
4. **不得为通过测试而无证据地改业务规则**，也不得简单删除、跳过、放宽现有测试；逐项判定旧断言、真实回归、环境差异、测试数据失效。需要业务决策时保持当前既定行为，写明冲突及待确认事项。
5. **安全修复必须保留原功能**：笔记权限、仓库相对路径、代码高亮、Mermaid、目录、折叠块、图片、下载、打印；AI 现有两层业务架构及 LiteLLM Core 接入、凭据与共享逻辑不因本计划改变。
6. **禁止**直接修改生产数据库、生产环境变量、真实服务配置、用户数据；不执行真实 Samba 管理命令；不访问/泄露生产密钥；不自动删除 GitHub 分支、关闭 Issue、修改分支保护或强制推送。需要管理员权限的动作只形成操作指引与核查清单。
7. 不为了本次整改把 `training` 拆分为多个 Django APP、不重写训练业务、不引入 Redis/Celery/其他基础设施，不升级 Django 或整个依赖树。可适度提取安全公共函数和添加测试。
8. 输出实际修改文件清单、测试结果、未通过项与原因、残余风险、**人工操作清单**。不自动提交或推送，除非用户在运行 Codex 时另行明确授权。

### 0.1 两份审阅结论的统一口径

- 上传的 `tms-review.md` 指出：**静态安全审阅未确认阻断级漏洞**，但 `notes` 有两项纵深防御缺口。这不等于可以忽略 CI 状态。
- 另一份审阅实查最新 GitHub Actions：`81c4a67` 的 CI **失败**。Django 测试为 **19 failed、1186 passed、8 skipped、7 deselected**；前端 **53/53** 项通过，但构建后 `static/css/output.css` 出现变化导致一致性检查失败；Debian 13 PDF Job 成功。
- 因此本计划以 **P0：恢复可发布质量门禁** 为第一优先级，以 **P1：安全纵深防御** 为第二优先级，其他均属质量提升，不把未证实风险描述为已经发生的攻击或数据泄漏。
- 最近提交/CI 链接：
  - [`develop` 基准提交](https://github.com/hdaojin/tms/commit/81c4a673a1856cf19ed61f8af0d1114146de0fce)
  - [对应失败的 CI Run](https://github.com/hdaojin/tms/actions/runs/43575203618)
- 复查时必须识别 CI 中旧代码与当前代码的差异，不引用旧的统计数字冒充新执行结果。

## 1. 工作阶段与交付范围

| 阶段 | 级别 | 工作项 | 主要输出 |
| --- | --- | --- | --- |
| A | 准备 | 基线复核、失败分类、工作区保护 | 基线记录与失败定位 |
| B | P0 | Python 19 项测试回归修复；CSS 产物漂移 | 通过的 Django/Frontend CI |
| C | P1 | 笔记附件下载响应加固；笔记 HTML 清洗 | 安全代码与正反向回归测试 |
| D | P2 | Markdown 异常可观测；配置文档同步；依赖兼容范围 | 代码、配置、文档与测试 |
| E | P2 | CI 部署安全检查、Python 依赖审计、PostgreSQL 验证、依赖更新管理 | 工作流与检测记录 |
| F | P2/P3 | AI 并发限制说明与必要防护；训练状态机文档/决策表测试；Samba 参数校验 | 聚焦改善，不改变业务模型 |
| G | P3/人工 | 分支保护、旧分支、Issue 整理建议 | 人工操作清单，不直接修改远端 |
| H | 交付 | 回归、差异审阅、报告 | 可审计的交付总结 |

如果本地不能联网、不能运行 PostgreSQL 或外部漏洞数据库审计，**完成可实施的其余工作**，如实报告未验证事项，禁止假报通过；不要改动生产环境来补齐本地依赖。

---

## 2. 阶段 A：建立可靠基线

### A1. 审阅与记录

- [ ] 核查 `git status --short`、`git branch --show-current`、`git rev-parse HEAD`。记录已有未提交文件及是否与任务冲突。
- [ ] 阅读 `AGENTS.md`，相关 `CONTEXT.md`、`docs/adr/`；核对 `pyproject.toml`、`uv.lock`、`package.json`、`package-lock.json`、`.github/workflows/ci.yml`。
- [ ] 获取/检查现有 CI 失败日志，按“行为改变但旧测试未更新 / 实际功能回归 / 测试夹具无效 / 平台差异”分类，并确认问题在当前代码是否仍存在。
- [ ] 建立 **改动范围清单**；不引入新的业务需求，不碰与问题无关的模型/迁移。

### A2. 本地验证基线

可用时执行（失败先记录，不立即大范围重构）：

```bash
uv sync --frozen
uv run ruff check .
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
npm ci
npm run build:frontend
npm run test:frontend
```

Python 全套测试在 **B 阶段聚焦修复后**执行，避免每修复一个断言就重复运行十余分钟的全量测试。前端构建会修改生成产物，先检查差异来源，再决定提交哪些生成文件。

**阶段验收**：对每一个整改目标已确认当前存在与否、复现路径、预期行为及相关测试；没有改动用户的非本任务工作区文件。

---

## 3. 阶段 B（P0）：恢复 CI 稳定性

### B1. Python 测试失败分类与修复

已观察到的 19 项失败分布如下；**数量来自基准 CI，不一定是执行时最新状态**：

| 领域 | 已知失败 | 处理重点 |
| --- | ---: | --- |
| `accounts/tests.py` | 6 | 用户展示名规范变更；用户名不再作为姓名搜索/显示依据；旧列表测试 |
| `assessments/tests.py` | 1 | 日期/时区渲染断言，核对 `Asia/Shanghai` 与 UI 日期格式 |
| `core/tests.py` | 2 | 旧移动导航“新增训练日志”入口断言，与当前导航规则对齐 |
| `feedback/tests/test_views.py` | 2 | 统一列表自动筛选 HTMX 属性；反馈处理人名称显示 |
| `training/test_cycle_details.py` | 1 | 成员可见性/私有姓名展示断言 |
| `training/test_cycle_members.py` | 2 | 批量添加成员旧两步交互与当前流程是否一致；302/200、预览 token |
| `training/test_entry_refinement.py` | 1 | 教练显示名格式从 `姓名(username)` 变化 |
| `training/test_log_workflow.py` | 1 | PDF 预览相关按钮/入口断言与当前功能 |
| `training/test_plan_people.py` | 2 | 候选人检索改按姓名/拼音；无真实姓名的测试夹具；表单提交 |
| `worldskills_forum/tests/test_search_and_unread.py` | 1 | 统一筛选栏 `hx-trigger` 属性断言 |
| **合计** | **19** | 逐项处理，不能把所有失败当作“测试过时” |

实施要求：

1. [ ] `accounts/services/users.py` 与 `accounts/tests.py`：先核对**当前既定的人名展示/同名备注规则**。若业务设计明确不显示用户名，重写旧预期并完善真实姓名、同名区分备注的测试夹具；不得为了旧测试恢复“用户名兜底”，也不得破坏同名人员禁止误选的校验。
2. [ ] `training/plan_people.py`、人员选择 Form 和 `training/test_plan_people.py`：明确搜索只支持姓名、拼音、首字母或其他 **当前正式支持的字段**。测试中的 `staff-candidate-*` 如仅为用户名，应改成符合新规则的人员姓名/拼音测试数据；另测空姓名、同名/备注缺失和分页行为。若真实选人交互无法提交，修复实际流程而非只调整断言。
3. [ ] `training/test_cycle_members.py`：核对当前成员管理页面是否仍保留原 token/预览两步流程。若业务已合规调整，按真实页面动作重建测试；若提交失败属于回归，修复权限、校验、事务及导航。保留“批量操作其中一项失败则整批回滚”的有效测试。
4. [ ] `accounts`、`feedback`、`training` 中其他姓名显示相关断言与权限范围一致，严禁因测试失败而放宽对象级授权。
5. [ ] `core/tests.py`、`feedback/tests/test_views.py`、`worldskills_forum/tests/test_search_and_unread.py`：依现有 `core/config/navigation.yml` 和统一筛选栏组件的实际行为更新测试，保留对未授权入口不可见、HTMX 筛选能正确触发、查询参数正确传递的**行为级**验证，不只做脆弱的字符串精确匹配。
6. [ ] `assessments` 日期断言：优先使用 timezone-aware 断言/项目统一日期格式，不以冻结当前时刻或系统本地时区作为假设。
7. [ ] 训练日志 PDF 预览：检查真实入口是否存在，覆盖有权限/无权限、可预览/不可预览文件，不以旧文案本身作为功能证明。
8. [ ] 每修复一组运行该测试文件，直到全部 19 项有明确结论；补足因本轮修复发现的真实回归测试。

聚焦验证示例：

```bash
uv run pytest accounts/tests.py training/test_cycle_members.py training/test_plan_people.py
uv run pytest core/tests.py feedback/tests/test_views.py worldskills_forum/tests/test_search_and_unread.py
uv run pytest assessments/tests.py training/test_cycle_details.py training/test_entry_refinement.py training/test_log_workflow.py
```

### B2. 前端生成产物一致性

CI 显示 `npm run build:frontend` 和 53 项前端测试通过，但随后 `static/css/output.css` 为 modified。

- [ ] 在干净或可追踪的工作区执行 `npm ci && npm run build:frontend && npm run test:frontend`。
- [ ] 检查 `static/css/main.css`、Tailwind/DaisyUI/Iconify 配置、前端依赖锁文件、生成产物差异。确认是否只是上次提交遗漏了 CSS 构建输出。
- [ ] 如果生成结果符合现有源码与 lockfile，**提交对应的 `static/css/output.css` 变更**（Codex 本轮仅保留文件修改，不自动 git commit）。不要手动编辑 minified CSS。
- [ ] 再次构建，检查预期静态产物没有二次漂移；不得为绿灯删除 CI 的静态产物一致性检查。

### B3. P0 验收门槛

- [ ] `uv run ruff check .` 通过。
- [ ] `uv run manage.py check`、`uv run manage.py makemigrations --check --dry-run` 通过。
- [ ] `uv run pytest -m "not document_pdf_native"` 全量通过（仅保留项目现有明确跳过/排除项）。
- [ ] `npm run build:frontend`、`npm run test:frontend` 通过，前端已跟踪生成产物无漂移。
- [ ] 更新失败分类：每项注明“调整测试/修复代码/环境问题”，确保无未解释的失败。

**如 P0 未全部通过**：继续可安全进行的局部整改，但在交付报告醒目标注“不能判定适合部署”；不允许以忽略失败的方式宣布 P0 完成。

---

## 4. 阶段 C（P1）：笔记安全纵深防御

### C1. 笔记附件响应统一安全策略

目标：修复 `notes/views.py::note_asset_view` 目前仅以 `mimetypes.guess_type` 推断 MIME 且默认内联的行为，复用 `core/file_preview.py` 的私有响应策略。

- [ ] 保持现有**登录、业务权限、可访问仓库、路径穿越/符号链接逃逸**验证不变。
- [ ] 核对 `core/file_preview.py` 中 `build_inline_preview_response()`、`build_download_response()`、`_apply_private_file_headers()` 可否安全复用。可提取**小型公共 helper**，但不要复制另一套不一致的安全实现，也不要让 `notes` 依赖未稳定的私有方法签名。
- [ ] 只允许内容签名验证合格的 PDF、常见图片类型内联；其余（尤其 HTML/SVG/XML/未知二进制）强制 `Content-Disposition: attachment`，并使用安全的 `Content-Type`。可按扩展名先初筛，但不可仅依赖扩展名或请求提供的 MIME。
- [ ] 无论内联/下载，都设置 `X-Content-Type-Options: nosniff`、`Cache-Control: private, no-store`；PDF 内联继续保持必要的 iframe/frame 安全策略。
- [ ] 对无效签名、空文件、不存在、无权限、目录和越界路径设置正确结果（下载回退或 404 依项目既有策略），不得泄露服务器实际路径。
- [ ] 注意原 `notes/tests.py` 中可能存在使用假图片字节做访问测试的数据：若新逻辑检验文件头，更新测试夹具为**真实最小合法图片**，并保留权限断言。

**测试矩阵**：授权/未授权；PDF/PNG/JPEG/WebP/GIF；`html`/`svg`/`xml`；扩展名与魔数不一致；无扩展名；目录穿越/软链接；`Content-Disposition`、安全头与缓存头。测试必须覆盖真实 `note_asset_view` 响应。

### C2. 笔记 Markdown 输出的 HTML 白名单清洗

目标：避免笔记库 Markdown 中的原始 HTML 或同步导入内容在同源页面未经清洗输出；但笔记系统**与通用 PDF 文档不同**，不能直接照搬 `core/documents/content.py` 的 `CLEANER` 以致破坏现有功能。

- [ ] 先梳理 `notes/utils.py::render_note_markdown` → details 提取/替换 → `_postprocess_note_html` → 相对链接重写 → 页面/打印模板使用 `|safe` 的完整链路，以及 Mermaid、代码高亮、H2–H4 目录、`<details>/<summary>`、DaisyUI 的 class/data 标记。**先加正向行为测试再改 sanitizer**。
- [ ] 使用现有 `nh3` 构建**笔记专用**、最小权限的 HTML 清洗策略，保留确有需要的 Markdown HTML 标签、表格、代码、标题锚点、图片、details/summary、Mermaid 与样式类标记；严格限制允许的属性/协议和可保留的 class/data 属性范围，禁止任意 `on*` 事件、脚本、iframe、危险协议和不受控内嵌内容。尽量复用公共白名单思想而非直接套用 PDF 的严格标签集。
- [ ] 清洗应作用于**最终用户可见 HTML**，包括经 details 替换和 URL 重写形成的片段；要防止先清洗再由后处理重新引入不可信 HTML。`meta`、目录（TOC）、打印页和普通详情页也需保持安全。
- [ ] 复查 `rewrite_relative_urls()` 对 `data:`、`//`、`javascript:`、恶意 URL 编码的处理。在安全不破坏必要功能的前提下缩小协议白名单；仅在有明确需求时允许受限的 `data:image/...`，不要允许 `data:text/html` 等执行性内容。
- [ ] 确认笔记仓库来源的权限边界；在 `AGENTS.md` 或 `docs/developer/` 简洁记录“仓库文件不是天然可信 HTML”，避免把仅管理员维护等同于不必清洗。
- [ ] 清理 DOM 后仍可正常显示和操作 Mermaid、折叠块与图片；在确需更改结构时同步受影响的 JS/CSS 与回归测试。

**恶意输入用例**：`<script>`、`<img onerror=...>`、`<a href="javascript:...">`、`<svg onload=...>`、`<iframe>`、带危险 URL 的图片、混合大小写/实体编码协议、嵌套 details。  
**功能回归用例**：代码围栏、语法高亮、Mermaid、目录锚点、相对图片/跨笔记链接、表格、提示块、折叠块、打印页。

### C3. P1 验收门槛

- [ ] 私有笔记附件全部具备安全头；非白名单资源不在同源中直接渲染。
- [ ] 笔记危险 HTML 及协议不能形成可执行内容；**Mermaid、折叠块和原有链接/排版功能没有倒退**。
- [ ] `uv run pytest notes`（按仓库实际测试收集方式运行）及相关 `core` 文件预览、Markdown 测试通过。
- [ ] 证明测试既覆盖**攻击性样本**，也覆盖**正常教学笔记**。

---

## 5. 阶段 D（P2）：稳定性、配置与文档

### D1. Markdown 渲染异常不再无声消失

当前 `core/utils/markdown.py::render_markdown_text()` 在 `strict=False` 时对所有异常吞掉并返回空正文。

- [ ] 在非 strict 分支增加标准 `logging` 告警/异常信息，优先记录错误类型与有限的安全上下文；**不要打印用户 Markdown 原文、隐私信息、AI 密钥**。
- [ ] 对**确实需要可见错误**的页面（优先笔记，涉及 `training/log_sources.py` / `training/log_ai_views.py` 时分别审阅）做聚焦处理：严格模式捕获异常后渲染安全错误提示，或保留非 strict 模式并提供用户可见的兜底状态。不要不加区分地把全站调用一律切成 `strict=True`。
- [ ] 原 PDF 生成 `strict=True` 的语义保持不变。
- [ ] 增加 mock 解析失败、日志仅一次、用户页面显示可控提示、敏感内容不进入日志的测试。

### D2. 环境变量和文档保持一致

- [ ] `.env.example`：删除「生产 PostgreSQL 或 MySQL」及 MySQL URL 示例；保留 SQLite 开发示例与 PostgreSQL 生产示例。
- [ ] `.env.example`、`README.md` 生产环境变量章节：补充 `AI_TRUSTED_ENDPOINTS` 用法（默认空，精确 scheme/hostname/port，只有管理员明确允许时填写；网络防火墙仍须隔离内网/元数据地址），用脱敏示例说明 Ollama 内网场景；检查其他涉及 AI 更名、加密密钥的文档是否一致。
- [ ] 将根目录 `AI_Optimization_suggestions.md` **归档**到合适的既有文档归档目录（若不存在则创建最小目录），标记为历史分析，不再作为现行架构规范；修订引用链接，保留可追溯内容。不要误删长期资料。
- [ ] `README.md`、`AGENTS.md`、`CONTEXT.md` 只在对应内容实际变化时同步，避免重复定义规则。

### D3. 关键依赖的版本边界

- [ ] 审查 `pyproject.toml` 的核心框架依赖约束，为**已明确兼容主版本**的关键依赖设置合理上界，例如 Django 6 系列 `django>=6.0,<7`，LiteLLM Core 与其他高风险库按**实际发布版本语义**确定合适边界；不能臆测其他库的下一个 major 一定兼容。
- [ ] 保持 Python `>=3.13,<3.14` 与实际部署一致；不执行无关包的大规模升级。
- [ ] 必要时更新 `uv.lock` 并使用 `uv sync --frozen` 复核；说明锁文件变化的原因。如果需要查询实际新版本兼容性而无网络，保留当前锁定版本并记录未验证点。
- [ ] 新增/更新少量校验，保证 `uv lock` 不意外引入未审核的大版本升级；不要强制所有小依赖都加无意义上界。

---

## 6. 阶段 E（P2）：CI 与依赖治理

### E1. 增加 PostgreSQL 验证路径

当前主要 Django CI 用 SQLite，而生产是 PostgreSQL。

- [ ] 在 `.github/workflows/ci.yml` 使用独立 PostgreSQL 服务容器/Job（临时 CI 数据库，**禁止接入生产**）。设置合适的 `DATABASE_URL`、健康检查与最低所需权限。
- [ ] 保留现有 SQLite 主 Job 的快速反馈。PostgreSQL Job 至少运行 migration 检查、`migrate` 和**高风险测试集合**：用户授权/密码重置、AI 旧库更名与迁移、事务回滚、训练任务发布/选手分配与锁定；如完整全量开销可接受，可扩大覆盖。
- [ ] 对“旧版 `ai_models` → 新版 `ai`”增加或复用真实数据库版本模拟，覆盖预检、转换、幂等、失败回滚、外键关系、权限记录、加密密钥校验；尊重已有 `ai/test_app_rename.py`，不重复开发另一套迁移系统。
- [ ] 检查 PostgreSQL 相关测试是否对数据库版本、锁、数据保留作了错误假设；保留现有迁移历史保护。

### E2. 部署安全检查

- [ ] 增加 `manage.py check --deploy` CI 检查，提供**仅供 CI 使用**、明确安全模拟的 SECRET_KEY、ALLOWED_HOSTS、HTTPS/安全 Cookie/HSTS 等配置；不要为了让检查安静而改变普通开发默认设置。
- [ ] 分类实际警告：可配置项、反向代理/部署入口已承担的安全职责与真正缺口，给出可复核说明；不能简单屏蔽所有警告。
- [ ] 若已有 `scripts/deploy_tms.sh` 在发布时执行 `check --deploy`，应与 CI 复用同一安全基线，不改坏 `plan/apply` 维护流程。

### E3. Python 依赖审计与自动更新元信息

- [ ] 选择**一种**适合 `uv.lock` 的 Python 依赖漏洞扫描方式（如 OSV 或 pip-audit），确保检查针对**锁定的真实依赖**，可重复执行，密钥/私有包信息不暴露；不要给每个 PR 增加无必要的重复扫描。
- [ ] 如适合 GitHub Actions，创建独立审计 Job 或工作流，明确联网依赖、失败策略、误报记录和忽略规则到期机制。已经存在的 `npm audit --omit=dev` 保持。
- [ ] 为 `uv`、npm、GitHub Actions 配置 Dependabot 或当前 GitHub 支持的等效依赖更新机制。采用受控更新频率、更新分组与 PR 上限，避免短时间产生大量打扰。
- [ ] 校验配置语法及工具命令存在；不可在没有实际运行的情况下写“漏洞审计通过”。

---

## 7. 阶段 F（P2/P3）：有限范围的稳定性/可维护性改进

### F1. AI 调用并发与限速边界

已知 `ai/llm/client.py` 中 `BoundedSemaphore(4)` 为**单 Python 进程**范围；`ai/views.py` 模型发现的 Django cache 限速如采用默认 LocMemCache 也不能跨 Gunicorn/worker 统一生效。

- [ ] 检查实际 Gunicorn worker 数、后台训练日志 worker 结构、模型发现限速；明确当前限制是单进程还是跨进程。测试至少验证单进程上限、异常释放信号量、超时/失败安全行为。
- [ ] 将现有限制的适用范围写进开发/运维说明；若存在可证实的资源滥用风险，优先做**最小**请求预算/审计记录或数据库级轻量保护（需要证明事务正确性），不因单一风险推测引入 Redis 或新的消息队列。
- [ ] 不重做 `ai/dispatcher.py`、`ai/services.py`、`ai/llm` 分层，不更改用户模型共享、隐私或 API Key 行为。

### F2. 训练业务状态机可视化与决策表测试（**不拆 APP**）

- [ ] 结合 `AGENTS.md`、`CONTEXT.md`、`docs/adr/` 与真实 `training` 代码，总结训练计划、排班、任务的保存/发布/撤回、审批、锁定、补录、选手快照等已实现规则；**以代码验证为准，冲突点只记录，不自行更改业务语义**。
- [ ] 在 `docs/design/` 或相关 ADR 下形成一份简洁的状态转换表（可附 Mermaid 状态图），展示状态、执行者、前置条件、转移、拒绝原因与是否需要审批。
- [ ] 只针对已存在的核心业务不变量补**少量高价值**的参数化/决策表测试：无权限、时段结束后锁定、任务分配快照、并发修改/审批、发布预览与提交之间数据变化、事务中途失败回滚。
- [ ] 不做 `training` 包级目录重排、模型迁移或多个 APP 拆分。对 `models.py`/`scheduling.py` 大文件的问题，仅形成未来可维护性建议。

### F3. Samba 外部命令的参数边界

- [ ] 在 `samba/samba_sync.py` 真正调用系统命令的入口，统一校验 OS 用户名和组 codename，不接受以 `-` 开头、控制字符、空值或其他可能被命令解释为选项的输入；校验应兼容现有合法命名，不私自改数据库中的用户名。
- [ ] 不仅依赖 Django Model 的 `full_clean()`，因为历史数据、外部调用可能绕过它。
- [ ] 保持 argv 列表执行方式、不使用 `shell=True`；若需要 `--` 分隔符，应确认每个目标 Linux 命令的实际支持情况，而不是想当然追加。
- [ ] 补 mock `subprocess.run` 测试：非法参数在系统命令调用前即失败；合法参数 argv 正确；不执行真实 `sudo`、`useradd`、`usermod` 或 `smbpasswd`。
- [ ] 默认 `SAMBA_INTEGRATION_ENABLED=False` 保持不变；运维说明补充 sudoers 最小权限检查项。

---

## 8. 阶段 G（P3）：GitHub 项目治理（**只给人工指引**）

Codex **不要**在未经单独授权时自动调用 GitHub 管理 API、删除分支、批量关闭 Issue 或修改保护规则。需输出可以由仓库所有者手动完成的 checklist。

- [ ] 建议 `develop` 开启必需 status checks，至少包含 Django、Frontend、Document PDF 以及新增的 PostgreSQL Job（以实际上报的 **Job 名称** 为准）。基准 GitHub API 返回 `protected: false`，Rulesets 列表为空；执行时再复核现状。
- [ ] 建议采用功能分支 + PR 合并，减少直接推送默认分支。**若项目主要由单人维护，不建议机械强制“必须由他人批准 PR”而使自己无法合并**；选择适合真实协作规模的合并门禁。
- [ ] 输出长期未合并分支的**候选清理列表**和各分支最后活动时间/是否包含唯一提交，不直接删除任何远端分支。
- [ ] 输出旧 Issue 建议“保留 / 合并 / 关闭 / 设里程碑”的清单，逐条依据当前实际功能，不自动关闭。
- [ ] 若需要调整 CI 保护门槛，需**先让本轮整改后的 CI 通过**再开启必需状态检查，避免锁住开发流程。

---

## 9. 统一验证策略与验收标准

### 9.1 修改期间按风险增量验证

| 修改类型 | 最小验证 |
| --- | --- |
| Python 业务/工具代码 | 相关测试 + `uv run ruff check <paths>` |
| 跨 APP 安全、权限、Markdown 公共组件 | 相关 APP 组合测试 + Django check，最终全量 pytest |
| 配置与依赖 | `uv sync --frozen`、`uv run manage.py check`、迁移漂移检查；对应 CI 配置验证 |
| 前端 CSS/组件/锁文件 | `npm ci`、`npm run build:frontend`、`npm run test:frontend`、产物一致性 |
| 纯文档 | 人工校对路径、引用、命令，不机械执行全量测试 |

### 9.2 最终总体验证（有对应环境时）

```bash
# Python / Django
uv sync --frozen
uv run ruff check .
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
uv run pytest -m "not document_pdf_native"

# 前端
npm ci
npm run build:frontend
npm run test:frontend
npm run format:frontend:check

# 生成产物：核对 diff，不得存在未解释的构建后漂移
git status --short
```

此外：

- [ ] Debian 13 上运行既有 `document-pdf` CI Job 或等价聚焦测试；不能在 Windows 环境假定 WeasyPrint/Linux 本地 PDF 子进程可用。
- [ ] PostgreSQL 新 Job 成功；如本地无环境，用实际 GitHub Actions 结果验证，不能以 SQLite 通过代替。
- [ ] 部署检查与依赖审计结果写入交付报告，明确哪些为网络/CI 权限限制未执行。
- [ ] **安全测试必须正反向均覆盖**，包括权限拒绝、危险 Markdown、附件 MIME/魔数不匹配、Samba 参数等。
- [ ] 现有 AI 模型配置、凭据、旧库迁移、训练日志与 PDF 输出不得出现回归。
- [ ] 默认不产生新数据库 migration；如确实发生 schema 变化，应说明必要性及兼容/回滚方案，单独审查。
- [ ] 不出现无关自动格式化、全仓重排或未解释的锁文件升级。

### 9.3 可交付的“完成”定义

1. **P0 必须**：最新执行环境的 Python CI 无失败；前端构建和资源一致性检查通过；失败分类有可追溯记录。
2. **P1 必须**：笔记的私有附件响应安全策略和 Markdown 清洗均有测试证明，且教学笔记核心功能保持。
3. **P2 完成判据**：异常日志、部署配置、CI PostgreSQL/依赖治理、AI 限流说明、训练状态机测试和 Samba 参数安全均有对应结果；不可用环境说明事实与后续复核命令。
4. **P3 完成判据**：生成**人工管理操作清单**，不要求自动变更仓库设置或 Issue。
5. 如果任何一项代码任务未完成，报告具体原因、影响、现有测试结果与建议，不得将其算作“完成”。

---

## 10. 交付报告格式（执行结束时输出）

建议在 Codex 最终答复按以下结构简洁报告，不要求另建大型文档：

```text
## 基线
- 初始/最终 HEAD：...
- 工作区已有修改：...

## 已完成
- P0：...
- P1：...
- P2：...
- P3 人工操作指引：...

## 主要修改文件
- 路径：修改目的

## 测试结果
- Ruff / Django check / migration check：...
- pytest：... passed / ... failed / ... skipped
- 前端构建与产物一致性：...
- PostgreSQL / PDF / 安全回归 / 依赖审计：...

## 未完成与风险
- 事项 + 原因 + 用户需采取的动作

## GitHub 人工操作清单
- 开启必需 CI 检查
- 检查陈旧分支候选
- 分拣旧 Issue
```

## 11. 推荐实施拆分（便于追踪，不要求自动提交）

1. **批次 1：P0 CI 修复** —— 修测试与前端产物，不混入安全重构。
2. **批次 2：P1 笔记安全加固** —— 先正常功能测试、后负面安全测试，再最小修复。
3. **批次 3：P2 Markdown 日志/配置/文档/依赖界限**。
4. **批次 4：P2 CI PostgreSQL/部署审计/依赖安全**。
5. **批次 5：P2/P3 AI 限流说明、训练状态机测试、Samba 参数校验和人工治理清单**。

**执行最终原则：以“恢复绿灯 + 封堵真实边界 + 保持现有行为”为成功标准，不以代码修改行数、增加抽象层数量或全仓重构规模作为成果。**
