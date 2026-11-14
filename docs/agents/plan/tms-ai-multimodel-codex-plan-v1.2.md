# Codex 实施 Plan：TMS AI 多模型统一接入、前端优化与 `ai_models` → `ai` 彻底迁移 V1.2

> **用途**：供 Codex 在 `hdaojin/tms` 仓库直接阅读、分阶段实施、提交代码与测试的执行计划。  
> **设计依据**：同版《[TMS AI 多模型提供商接入与管理系统——前后端最终设计方案 V1.2](tms-ai-multimodel-design-v1.2.md)》。  
> **目标分支**：`develop`；生成计划时审阅的 Git tree：`2193b848ec59a90512453c60402e1a5c5b5f6252`。执行前必须重新检查 `develop` HEAD，不得假设路径、模型、迁移仍完全一致。  
> **日期**：2026-11-14  
> **实施方式**：代码与迁移脚本由 Codex 实现；测试、验证与报告由 Codex 完成；**不得自动连接生产数据库执行正式切换**。

---

## 0. Codex 执行指令（先读）

你正在 TMS Django 单体应用上实施多模型接入与 APP 全面更名。按本 Plan 开展真实代码修改，而非只给出建议。**不要**另建 Django APP 或独立 LiteLLM Proxy，不要引入 LangChain、Dify、Celery/Redis 等新依赖，不要通过删除重建数据表完成更名。遵守仓库 `AGENTS.md`、`CONTEXT.md` 及相关 ADR；当 AGENTS 旧文字与本次已确认的 `ai` 改名目标冲突时，完成对应规范更新。

**必须满足的结果**：

1. `ai_models` **彻底迁移**为 Django APP `ai`（Python 包名、`AppConfig.name`/`label`、迁移 graph、数据库表前缀、ContentType、权限、角色权限包编码、运行时导入、模板/URL namespace、文档）。
2. 既有数据库所有 AI 记录、API 密钥密文、默认模型、共享关系、训练日志生成任务外键、用户/角色授权及其 ID **零丢失**；同时全新数据库可从零正常迁移。
3. TMS 保持**两层技术架构、三个职责模块**：TMS AI 服务层（配置管理 + 调用/调度）和 LiteLLM Core 接入层。
4. 现有训练日志 DeepSeek 文本/JSON/思考/图片行为兼容；可新增常用厂商与自定义 OpenAI 兼容 API。
5. 模型列表、单页新增/编辑表单、详情/测试/共享和管理员提供商页面按设计方案完成；只复用 TMS 既有前端技术与组件。
6. 提供独立可审核的旧库升级预检、执行、验证与回滚文档和测试。**未经人工授权，不对生产数据库、生产部署或用户真实模型 API 发请求。**

**安全停机规则**：迁移前后，如发现新旧 schema、迁移历史、权限或主键冲突，必须报告阻断并停止，不得用 `--fake`、`--fake-initial`、删除旧表、清空迁移记录或临时放宽权限掩盖问题。若需要调整项目约束，优先给出最小可验证实施；不在生产环境强行推进。

## 1. 执行前审查与基线记录

- [ ] `git status --short`、当前 HEAD、`uv.lock`、`pyproject.toml`、Python/Django 版本、测试 DB、PostgreSQL 部署策略；保留用户未提交的改动，不用 `git reset --hard`。
- [ ] 阅读 `AGENTS.md`、`CONTEXT.md`、相关训练日志 ADR、最新 `ai_models/`、`training/log_generation.py`、`training/log_ai_forms.py`、`training/log_ai_views.py`、`training/models.py`、`core/permissions.py`、`core/config/{navigation,permission_bundles}.yml`、`accounts/models.py`、`tmsproject/{settings,urls}.py`。
- [ ] 全仓排查旧符号，输出文件与字段清单：`rg -n 'ai_models|AIModelsConfig|ai-models|DeepSeekProvider|PROVIDERS\[' .`（排除 `.venv`、`node_modules`、构建产物和无关备份）。
- [ ] 列出 `ai_models/migrations/0001...0005` 和跨 APP 迁移引用，特别注意 `training/migrations/0026_training_log_ai_workflow.py`：依赖 `('ai_models','0004_provider_model_defaults')`、FK `to='ai_models.aimodel'`。
- [ ] 盘点 `AIModel`、`AIModelPreference`、`AIProviderSettings`、`AIModelOption`、`AIModel.shared_users`、`AIModel.shared_groups` 当前表名/关系。**禁止仅从文件名猜测中间表名**；以历史 schema、Django ORM 元数据和 DB introspection 核实。
- [ ] 盘点 `accounts.UserProfile.selected_permission_bundles` 和 `accounts.GroupProfile.selected_permission_bundles`：目前有 `ai_models.manage_own`、`ai_models.use_shared`；这两个值属于持久化业务数据，必须迁移。
- [ ] 清点 `django_content_type` 中旧 APP 的所有记录、`auth_permission` 和 M2M 赋权关系；检查有无 `ai` label、`ai_*` 表、`ai` 权限和 `django_migrations.app='ai'` 既有冲突。
- [ ] 确认 `training_trainingloggeneration.model_id` 关联和历史记录、已保存的训练日志、Fernet `AI_MODEL_ENCRYPTION_KEY` 环境变量保持原值。
- [ ] 写下**预迁移基线**：各目标表行数、主键集合/最大值、密文字段样本哈希、M2M 关系数、权限记录 ID 和组/用户授权数、训练生成 FK 非空/有效记录数；禁止把密钥明文打印或写到报告。

> **审查后再实施**。若实际 HEAD 已更改迁移链（如增加 `0006`），用真实最新历史生成映射，并调整预检/测试，不能硬编码只支持 0001–0005。

## 2. 实施阶段 A：先完成“旧 APP → 新 APP”的无损迁移设计与测试

### A1. 迁移策略（两条路径同一代码库）

**新数据库路径**：安装的 APP 仅是 `ai.apps.AIConfig` 且 `label='ai'`。将历史 migration 放入 `ai/migrations/`，沿完整历史顺序把 `('ai_models', migration)` / `to='ai_models.xxx'` / 历史 `apps.get_model('ai_models', ...)` 等依赖与引用正确变为 `ai`，包括其他 APP 的历史 migrations；新库直接执行 `migrate` 创建 `ai_*` 表、`ai` ContentType 和权限。不得留下无法解析的旧迁移依赖。

**已有数据库路径**：基于旧库备份，执行**显式一次性升级命令**，在单一受控事务中原地完成以下必要操作，然后用新代码运行正常 `migrate`：

1. 先验证旧库旧 schema/迁移历史完整、旧 APP 迁移及相关业务迁移已经全部应用、数据库没有新 APP 冲突，旧 AI 实体行数/外键/权限完整。对于旧版本存在未执行迁移的 DB，直接停止并要求先用原版本完成旧迁移。
2. 将 `django_migrations` 中 `app='ai_models'` 的应用历史记录转成 `app='ai'`，保持 migration `name` 与已应用状态；迁移脚本须先确认新代码的历史文件/依赖映射与旧库记录一致。
3. 对 AI 实体表及 **M2M 中间表** 原地执行旧表名 → 新 `ai_*` 名的表重命名，不复制行、不重新生成 PK、不删除表。使用经数据库类型验证的 schema 操作，审计受影响索引/约束、序列、外键、触发器、视图；不擅自重建表。
4. 将 `django_content_type` 对应模型的 `app_label='ai_models'` 原地更正为 `ai`，**保留 ContentType.id**；保留 `auth_permission.id`/codename 与 auth user/group 的授权 M2M 行，不新建同义 Permission，不删除旧 ID。权限运行时字符串随 app label 改为 `ai.<codename>`。
5. 只转换 `accounts.UserProfile.selected_permission_bundles` 与 `accounts.GroupProfile.selected_permission_bundles` JSON 数组中两条旧业务权限包 code：`ai_models.manage_own → ai.manage_own`、`ai_models.use_shared → ai.use_shared`；保留其他 code、顺序及无关字段，不批量重置/同步所有角色权限。对冲突重复项去重并记录。
6. 对升级前后主键、各表行数、外键、密钥密文、ContentType ID、Permission ID、用户/组原生授权与角色包 JSON 做对照；任何异常触发当前事务回滚。
7. 成功后才运行新代码 `manage.py migrate`，检查无意外 `CreateModel/DeleteModel`，不出现两套 AI 表或重复 ContentType。

### A2. 升级命令与防误操作

- [ ] 实现专用 `manage.py migrate_ai_app_label --dry-run`（命名可适当调整）和需显式 `--apply` 的方式；默认只读，不修改数据库。命令可存在 `ai/management/commands/`，使用 DB transaction、目标表白名单和数据库 introspection；不调用业务 AI 模型 API。
- [ ] 运行环境限定为 PostgreSQL 正式部署和测试环境 SQLite（若本项目本地/CI 使用 SQLite）；**分别编写数据库级升级测试**，不能只测 SQLite 就声称 PostgreSQL 升级可靠。
- [ ] 预检打印清楚：旧/新迁移记录、旧/新表、M2M、ContentType/Permission 冲突、JSON 要转换的记录数、现有 PK/FK 检查、预计变更项；不输出 API Key 原值或密文。
- [ ] 实际写入在一个受控事务中完成；支持“未升级→升级”一次成功、“已完整升级→仅验证或明确无操作”两种状态；检测到“部分升级”必须阻断，不能静默补齐。
- [ ] PostgreSQL 表 rename、FK 引用、索引/约束名称（自动生成或显式指定）、序列、`schema` 搜索路径应由真实数据库 introspection 核实。对于业务不依赖旧名字的索引，不为了好看就危险地重建；但最终新旧库迁移 drift 需一致。
- [ ] SQLite 路径按 SQLite/Django 实际外键与表重命名机制单独覆盖测试，使用 Django 数据库 schema 工具或经过测试的 `ALTER TABLE`；不要在不支持的数据库上执行 PostgreSQL 原生 SQL。
- [ ] 在升级前确保无旧 Django 进程还在写数据；此变更不可在旧代码和新代码之间进行滚动混合部署。
- [ ] 建立 `docs/developer/ai-app-rename-migration.md`：旧库准备、备份密钥、只读预检、升级切换、验证、失败停机与**从备份恢复**的回滚流程；不要把未验证的自动逆迁移当生产回滚手段。

**重要技术约束**：Django 6 官方警告已应用迁移的 `AppConfig.label` 更改会破坏数据库/迁移对应关系；必须同时协调迁移 graph、`django_migrations`、表名、ContentType、Permission。绝不简单修改目录/label 后直接运行 `makemigrations`，更不能以 `CreateModel`+`DeleteModel` 或全量 fake 绕过已有数据。

### A3. Python 包与迁移历史改名

- [ ] `ai_models/` → `ai/`；`AIModelsConfig` → `AIConfig`，`name='ai'`、`label='ai'`、`verbose_name='AI 服务'`；修改 `INSTALLED_APPS`。
- [ ] `ai/migrations/` 保留历史序列与文件名，逐条检查 `dependencies`、FK `to=`、`apps.get_model(...)`、ContentType 文字条件、权限数据迁移、历史可序列化导入对象等；同样检查其他 APP 的历史迁移。特别审查原 `ai_models/migrations/0004_provider_model_defaults.py` 和 `0005_model_share_audience.py` 中 `RunPython`：新库必须按新标签运行正确，旧库已执行时不能重放产生破坏。
- [ ] 将所有运行时 `from ai_models ...` 改为 `from ai ...`；训练日志模型外键改为 `"ai.AIModel"`；管理菜单/权限包/URL namespace 改为 `ai`。
- [ ] 模板目录统一改为 `ai/templates/ai/`（可按 TMS 既有规范确定最终路径）并更新 `render` / `extends` / `{% include %}`、静态 JS 选择器及文档链接。
- [ ] `ai/urls.py` 使用 `app_name='ai'`，业务代码使用 `reverse('ai:...')`；外部 URL **可维持** `/ai-models/` 不变，保障用户书签。这是 URL 稳定策略，不是旧 APP 兼容层。若变更公开 URL 必须提供明确 301 redirect 测试，但本 Plan 优先不改 URL 路径。
- [ ] `core/config/permission_bundles.yml` 内业务权限包 code 和权限字符串改为 `ai.*`；`core/config/navigation.yml` 的菜单 key/permission/url name 同步。审计 `core/permissions.py` 权限包规范化和授权投影，不误删除已有用户/角色权限。
- [ ] 修改 `AGENTS.md`、`CONTEXT.md`、`README.md`、`docs/user-manual/...`、ADR/导入例子及测试；历史说明若属于迁移背景可明确写“旧称”，但新的业务运行时代码不得 import `ai_models`。

### A4. 双路径数据库测试（本阶段交付阻断门槛）

- [ ] **Fresh DB**：新库运行全量 `migrate`；验证仅存在 `ai_*` 表，ContentType `ai`、权限 `ai.*`，`training` 相关迁移依赖正确；`makemigrations --check --dry-run` 不产生漂移。
- [ ] **Legacy DB**：在旧版代码使用旧 migrations 构造一个真实旧 schema（优先恢复脱敏的实际历史库副本），插入模型、长短密钥密文、全体/定向共享、默认模型、Permission、用户直接授权、Group 授权、UserProfile/GroupProfile bundle、训练生成 FK 数据；旧代码迁移到 HEAD 后运行只读预检→显式升级→新代码 `migrate`→一致性核对。
- [ ] 至少验证：`AIModel` 全部 PK 不变、`encrypted_api_key` bytes 一致、`revision` 不变、共享 M2M 行数/组合一致、默认 FK 保留、`TrainingLogGeneration.model_id` FK 可读、ContentType ID 与 auth Permission ID 均保持、用户/组权限关系不丢失、业务包 code 已改为 `ai.*`。
- [ ] 检验升级脚本二次运行、旧/新并存、部分状态、重复 ContentType、新同名表、迁移 history 缺失、JSON 异常、缺失加密密钥等中止路径；脚本执行失败后必须保证 DB 未局部改动。
- [ ] 进行备份恢复演练：恢复旧备份与原密钥后，旧版系统可重新启动；记录回滚用的旧 commit / DB dump / media / private media 和服务命令。

**在 A4 通过之前，不要把改名结果当成已安全可上线；允许后续功能开发在开发分支继续，但上线须等待此项验收。**

## 3. 实施阶段 B：引入 LiteLLM Core SDK，统一模型调用

### B1. 环境与依赖

- [ ] 优先 `uv add litellm-core`，检查当前 Python 3.13 / Django 6、`uv.lock` 和其他依赖的解析结果；不要同时安装 `litellm` 和 `litellm-core`（二者均导出 `litellm` Python 命名空间）。
- [ ] 若当前 LiteLLM Core 与项目已有依赖发生无法合理解决的冲突，记录具体冲突与可复现步骤，暂停新增 SDK，不偷偷改动全项目 Python/Django 版本；不得无依据换成 LiteLLM Proxy。
- [ ] 锁定可复现依赖；记录 LiteLLM 的 Python SDK 异常/超时/可选功能依赖行为；默认禁用/不配置跨用户共享的进程级全局 API key、callbacks、cache。

### B2. 后端职责边界

在 `ai` APP 内建最小调用层，可参考：

```text
ai/
  providers.py           # 系统可信 Provider 元数据与内部 LiteLLM 路由映射
  catalog.py             # 推荐模型目录
  services.py            # 模型 CRUD、密钥、权限、验证、共享
  dispatcher.py          # TMS 统一业务调用与调度
  llm/client.py          # LiteLLM SDK 调用与抽象响应
  llm/parameters.py      # TMS 请求语义 → LiteLLM 参数
  llm/exceptions.py      # 统一安全异常
```

- [ ] 将现有 `DeepSeekProvider` 的手写 urllib 调用迁移到 LiteLLM SDK；不要求业务 APP 引用 `litellm`。
- [ ] 保留当前 `generate_text(user, model_id, revision, payload)` 的业务调用行为或提供无破坏性 wrapper；如需要新 API，设计一个清晰的请求对象/调用入口，并迁移调用方测试。
- [ ] 选择用户显式模型或默认模型；在**真正发请求前**重新检查用户权限、所有者是否有效、共享范围/下架状态、`verified`、模型 `revision` 与 provider 启用状态。对任务快照要保留必要的历史引用。
- [ ] 每次请求专用 `model`、`api_base`、`api_key`、timeout 与参数；**严禁**使用 SDK 全局变量承载用户密钥；不得在业务层自动切换模型或 provider。
- [ ] 定义标准请求语义：`messages`、`thinking`、`reasoning_effort`、`max_output_tokens`、`response_mode`（text/json）、`images`、`timeout`；由接入层根据厂商和模型能力转换。原生不支持的“必需输出”不允许静默 drop。
- [ ] 区分认证失败、地址错误、模型不存在、余额不足、限流、网络故障、超时、响应无效、输出截断和结构校验失败；给前端安全且稳定的中文提示，严禁回显 API Key 或用户私有请求材料。
- [ ] V1 不写智能 Router、跨模型 fallback、自动重试高费用的生成请求、自动 Token 计费，也不改变训练生成任务队列/状态机。

### B3. 多提供商注册与自定义 API

- [ ] 系统精选：DeepSeek、OpenAI、Anthropic、Gemini、阿里云百炼、OpenRouter、Ollama、自定义 OpenAI 兼容。先核实 LiteLLM Core 锁定版本的真实 provider 前缀、基础路径和模型请求参数；预置的模型 ID 必须是已核实的当前有效值或由管理员配置，不写未经核实的“必定可用”模型名。
- [ ] 预置提供商保留可信的默认 URL、推荐模型、认证类型和 enabled 状态；数据库 `AIProviderSettings` 只维护管理员配置，不创建动态 Python 实现。
- [ ] 自定义 API 使用通用 OpenAI 兼容方式、`base_url`、`model_id`、API Key，必要时允许受控的“无认证本地模型”模式；不允许用户任意指定 LiteLLM 后端 provider 前缀、任意 headers、任意代码脚本。
- [ ] 保留管理员模型选项目录和用户手动输入模型 ID；V1 不自动探测 `/models` 端点。

### B4. 兼容性与能力处理

- [ ] 当前 `ThinkingMode`、`ReasoningEffort` 为 DeepSeek 风格；前端按能力显示，后端按模型转换，不支持的选项返回字段错误或明示降级策略。
- [ ] 对 JSON 必需业务定义严肃的完整性保证：`response_format` 支持检查，必要时使用结构化提示词 + JSON 解析 + 结构校验；对不能满足输出结构的模型给出错误，不将未经校验的字符串写入日志。
- [ ] 图片仅对已明确支持的具体模型启用。保持现有 DeepSeek 支持读图的白名单语义，迁移后验证其图片 payload、MIME、大小限制与 LiteLLM 接口兼容。
- [ ] 对 SDK 缺少模型元数据的新模型采取保守策略。模型能力来源支持管理员声明，但声明不替代后端必要结果校验。

### B5. 安全：自定义 URL、并发、脱敏

- [ ] 审阅 `validate_base_url()` 当前行为：只校验格式并允许内网及本机地址。扩展后设计明确的 URL/网络 SSRF 策略，遵循“外部 HTTPS 默认允许经过安全校验，内网/本机仅受控可信主体或清单允许”；考虑 DNS 解析和重绑定、代理和 SDK 重定向、连接目标端口、IPv4/IPv6、云元数据地址。
- [ ] 若无法确认 LiteLLM Core 对自定义地址的最终连接 IP、重定向、代理行为满足 TMS SSRF 策略，**禁止把自定义任意目标地址作为默认开放功能**；先采用配置级允许列表/可信目标 + 受限网络出站策略，提供明确管理员配置。不能仅在表单检查一次域名就认为防护完成。
- [ ] 所有用户明文密钥只存在必要的内存局部变量；连接测试请求/模型回复与错误脱敏，限额/大小/并发/超时均有保护。
- [ ] 不添加未获授权的后台模型 API 自动测试；有费用的测试和生成只由明确用户行为发起。

## 4. 实施阶段 C：前端管理与交互优化

### C1. 三个导航入口（保持稳定）

1. 用户中心 → **我的 AI 模型**。
2. 系统管理 → **AI 模型提供商**。
3. 系统管理 → **共享 AI 模型管理**。

所有命名空间、权限字符串换为 `ai:*` / `ai.*`。外部 `/ai-models/` URL 保持稳定；不新增“LiteLLM 设置”“AI Gateway 管理”“独立连接管理”菜单。

### C2. 模型列表页

- [ ] 将当前 `ai_models/templates/ai_models/list.html` 升级成 TMS 统一 `django-tables2` 表格；按需新建 `ai/tables.py`、`ai/filters.py`。
- [ ] 搜索模型名称、provider、model_id；“全部 / 我的 / 共享”视图，状态和提供商筛选；排序、分页、移动端响应式。
- [ ] 列：模型名称（ID 为次行）、提供商、所有者、验证/最近测试结果、共享范围、默认模型标志和操作。
- [ ] 列表不能泄露密钥、私人测试内容和未授权配置；仅所有者拥有编辑、测试、共享、删除等入口；可使用共享模型的用户可设为默认。
- [ ] 保留 `AIModelPreference` 失效默认提示与现有 `usable_models()` 语义。

### C3. 新增/编辑模型表单

- [ ] 使用单页分区表单：①基础信息（名称、提供商）② API 连接（URL、Key）③模型选择（推荐或手动）④折叠高级选项（按模型能力决定思考模式和强度）。
- [ ] 内置提供商显示默认 URL 占位/说明；自定义 OpenAI 兼容类型强制 Base URL；认证类型决定 Key 是否必填；保存后仅显示遮罩。
- [ ] 提供商切换更新默认 URL、推荐模型、支持参数，不能静默覆盖已有用户输入；前端采用 Alpine.js/HTMX **单一 DOM 所有权**，后端继续拥有最终验证权。
- [ ] 新建时仅保存配置，之后跳转详情页；不自动消费 API。编辑时密钥留空保留，目标/凭据/模型/参数变化时 invalidates verification、暂停共享、版本更新。
- [ ] 基础表单显式提示“API 请求及数据将发送到此地址”；高级设置默认折叠，V1 不开放 Temperature/任意请求参数/费用预算/手工 max token。
- [ ] 用 Django Forms + TMS 现有 `components/field.html`、`components/form_errors.html` 和 `common/form.html`；遵循 DaisyUI 5/Tailwind 4 和响应式规范。

### C4. 详情、测试和共享

- [ ] 三块内容：模型概览（脱敏）、测试（固定短句、耗时、最近结果、脱敏请求/回复）、共享（私有、全体、指定用户或角色）。
- [ ] “测试中”禁用重复操作，保留现有 30 秒节流和 `revision` 防过期写回机制；被下架/未验证时禁止开启共享。
- [ ] 测试状态区分：已验证、最近测试失败、未验证，不要把某次暂时网络错误写成永久不可用。
- [ ] 共享模型费用由连接凭据所有者承担；向模型发送的数据接收方提醒必须清晰且用户可理解。

### C5. 提供商管理与共享监管

- [ ] 管理员提供商列表与详情增加接入类型、默认地址、默认模型、目录/能力预设、启用状态；管理员不能在数据库中定义可执行的厂商代码。
- [ ] 保留 `AIModelOption` 可编辑、隐藏、唯一默认选项和并发约束；保留 `moderated_models()`、`moderate_model()` 的原有授权和业务语义。
- [ ] 实现与现有导航、表格、表单一致的视觉设计，不引入新的 JS 框架；需要变更前端构建静态产物时按 AGENTS.md 构建并检查。

## 5. 实施阶段 D：训练日志兼容与业务隔离

- [ ] `training/log_generation.py` 不再 import 厂商 `PROVIDERS` / 自行判断 DeepSeek 模型图片，也不直接拼接 `thinking` 等厂商特定请求格式；改为向 `ai.dispatcher` 声明需要的能力，交由 `ai` 执行转换。
- [ ] 保持原来的确认预览、冻结模型 `revision`、提示词、网页资料安全读取、图片权限、日志文档快照、教练与选手角色范围逻辑。
- [ ] 对 JSON 回复和 `finish_reason` 做严格校验；保持不完整生成不提交、失败可重试但不静默另找模型。
- [ ] 继续限制图片大小、数量和类型，确保旧 DeepSeek 官方图像场景不退化；模型不支持图片时给出“仅生成正文”选择或明确错误。
- [ ] 更新 `training/test_log_ai.py`，覆盖教练/选手生成、不同权限模型选择、被下架/撤销共享、修改配置导致版本不匹配、JSON 解析失败、长响应截断和图片能力限制。

## 6. 自动化测试矩阵与发布门槛

### 6.1 最低自动化覆盖

| 测试类别 | 必测条件 |
|---|---|
| 旧库迁移 | 所有表数据、PK、密钥密文、M2M、训练日志 FK、迁移记录、ContentType/Permission ID、JSON 权限包保留 |
| 新库迁移 | 新数据库 `migrate` 全通过，无旧 APP label / 表 / 依赖，无自动生成漂移 |
| 接入层 | DeepSeek、至少一个其他原生提供商、OpenAI 兼容；请求/响应、超时、认证失败、限流、错误脱敏 |
| 配置管理 | CRUD、默认地址、推荐选项、手动模型 ID、密钥保留/替换、版本失效 |
| 授权共享 | 本人/外人/消费者/superuser、角色实时成员、管理员下架、默认模型失效、越权安全 |
| 前端 | provider 联动、手动 ID、表单错误、按权限显示动作、过滤/分页/响应式、HTMX/Alpine 互操作 |
| 训练日志 | 文本/JSON/思考/图片、预览确认、资料引用、超时、历史任务一致性 |
| 安全 | SSRF 内外网策略、禁止重定向/跳过 DNS 校验、API Key 不进日志、无自动付费测试 |

所有无真实密钥的测试使用隔离的 LiteLLM mock/fake transport；**不能**让 CI 对真实厂商发请求或产生费用。对真实 API 的 smoke test 仅在管理员显式批准的隔离环境可选执行。

### 6.2 参考命令（从仓库根目录运行）

```bash
# 仅在受控本地/CI数据库执行，不是生产切换命令
uv sync
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
uv run manage.py showmigrations ai training
uv run manage.py migrate --plan
uv run manage.py migrate
uv run pytest ai training/test_log_ai.py accounts/test_migrations.py
uv run ruff check ai training accounts core tmsproject
npm run build:css
# 主要代码完成、准备合并时再运行：
uv run pytest
```

执行命令前按新代码的真实测试路径调整。若项目规定 `uv run manage.py` 与某平台不兼容，使用项目 AGENTS 指定的等价形式；**生产使用 `sudo tms-deploy manage ...` 发布流程，而不是直接在生产目录执行本地 uv 命令**。

### 6.3 完成验收的判定

- [ ] 本地/CI 全新 DB 的迁移历史自洽，`makemigrations --check --dry-run` 为零漂移。
- [ ] PostgreSQL 旧库副本升级经过完整验收；无旧 `ai_models` 内容类型、DB 表、迁移记录、权限字符串和运行时引用，迁移专用工具和历史文字例外有清晰标注。
- [ ] 用户/组曾经分配的“管理自己的模型”“使用共享模型”权限依旧生效；权限包 JSON 更新为新 code，模型共享对象关系和默认设置均保留。
- [ ] 所有历史 `TrainingLogGeneration` 指向的模型关联继续可读，相关生成任务/文档无损。
- [ ] 原 DeepSeek 回归与多提供商 mock 测试成功；无全局 API key 泄漏或 SSRF 安全退步。
- [ ] 完整功能、响应式 UI、技术文档和回滚演练记录可供人工审查。

## 7. 生产发布建议（仅提交 runbook，不自动执行）

1. 旧代码/旧 schema 的**最后一次备份**：PostgreSQL 全库备份 + `media` + `media-private` + 当前 `AI_MODEL_ENCRYPTION_KEY` 安全备份（不得写入备份脚本输出或计划文档）；记下对应 Git SHA。
2. 部署停机窗口停止旧 Gunicorn/后台任务和所有写入入口，确保不会出现新旧代码混跑；核对备份可恢复。
3. 新代码发布准备，**先执行 `migrate_ai_app_label --dry-run`** 生成只读检查报告；任何异常中止。
4. 授权人员在测试通过后显式执行 `migrate_ai_app_label --apply`，获取事务成功及数据一致性报告。
5. 再执行新代码正式 Django migrations（通过 `tms-deploy` 的部署能力），检查 `showmigrations`、`check`、Permission、默认模型和训练生成历史引用。
6. 启动服务并进行只读 smoke 测试；用户主动选择执行必要的单条受控 AI 请求，确认各模型仍能正常运行。
7. 保留旧备份直至验收后约定时间。若失败，停止新服务，**通过备份整体恢复旧 DB、密钥配置与旧代码版本**；不要在未知状态下切回旧应用或直接反向执行未经验证的 SQL。

> 此处只是 runbook 设计，不代表已在真实生产库运行。正式切换需要负责人单独授权和维护窗口。

## 8. 最终需交付的仓库改动与报告

- [ ] `ai` 完整 APP、LiteLLM Core 依赖、统一调用/配置服务、前端模板/列表/脚本、训练日志调用迁移和相关测试。
- [ ] 可在新库迁移的完整 `ai/migrations/` 历史，跨 APP 引用和数据库 upgrade 管理命令；旧库升级演练自动化测试。
- [ ] `docs/developer/ai-app-rename-migration.md` 生产安全迁移与恢复手册。
- [ ] 更新 `AGENTS.md`、`CONTEXT.md`、`README.md`、用户手册、导航/权限包等项目规范；将设计文档归档为 `docs/design/tms-ai-multimodel-design-v1.2.md`（可依仓库目录规范调整）。
- [ ] 完成后总结：修改的文件和重要设计决策、数据库转换清单、跑过的测试及结果、无法验证或剩余风险、需要管理员在生产执行的明确步骤。

## 9. 禁止事项与非目标

- 禁止为改名执行 `DROP TABLE` / `DeleteModel` + `CreateModel`、`flush`、重建原用户 AI 模型或重发 API Key。
- 禁止不经审计地 `--fake` / `--fake-initial`，或用人工删除 `django_migrations`、`django_content_type`、`auth_permission` 的方式“清理旧表”。
- 禁止把 `AppConfig.label='ai_models'` 作为最终方案；用户要求**彻底迁移**。
- 禁止为“模型三层”建立三个 Django APP、三个 HTTP 服务或独立网关。最终仍是两层技术架构、三个职责模块。
- 禁止在调用失败后未经用户确认自动换到不同服务商；V1 无 Router 负载均衡、自动模型发现、复杂计费、AI Agent 架构。
- 禁止在旧库切换失败时继续执行后续迁移，更不能自动开始真实生产操作。

## 10. 参考文档

- 同版设计方案：`tms-ai-multimodel-design-v1.2.md`。
- TMS 源码：<https://github.com/hdaojin/tms/tree/develop>
- Django 6 AppConfig / 警告：<https://docs.djangoproject.com/en/6.0/ref/applications/>
- Django 6 migrations：<https://docs.djangoproject.com/en/6.0/topics/migrations/>
- Django 6 migration operations：<https://docs.djangoproject.com/en/6.0/ref/migration-operations/>
- Django 6 ContentTypes：<https://docs.djangoproject.com/en/6.0/ref/contrib/contenttypes/>
- Django 6 权限系统：<https://docs.djangoproject.com/en/6.0/topics/auth/default/>
- LiteLLM Core：<https://docs.litellm.ai/docs/litellm_core>
- LiteLLM Python SDK：<https://docs.litellm.ai/docs/python_sdk>
- HTMX：<https://htmx.org/docs/>；Alpine.js：<https://alpinejs.dev/start-here>；Tailwind CSS 4：<https://tailwindcss.com/docs/installation>；DaisyUI 5：<https://daisyui.com/docs/install/>

---

## 建议直接交给 Codex 的执行提示词

```text
请在 hdaojin/tms 仓库的 develop 分支上实施附件《tms-ai-multimodel-codex-plan-v1.2.md》，并以《tms-ai-multimodel-design-v1.2.md》作为业务和界面设计依据。

先读取仓库 AGENTS.md、CONTEXT.md 与相关 ADR，重新审查当前 develop HEAD，再依照 Plan 的 A→B→C→D 阶段实施，不能跳过彻底更名带来的历史迁移、数据库表、ContentType、Permission、UserProfile/GroupProfile 权限包和 TrainingLogGeneration 外键处理。

此次是 ai_models → ai 的完全迁移，不接受仅改 Python 包名、保留旧 app_label 的折中方案。新数据库初始化与旧 PostgreSQL 数据库升级两条路径必须都有自动化演练；严禁通过删表重建、盲目 fake 迁移或重置权限实现更名。

架构保持两层技术架构、三个职责模块；使用 LiteLLM Core SDK 而非独立 Proxy；V1 不开发 Router/Agent/复杂计费。前端复用现有 Django Forms、django-tables2、django-filter、HTMX、Alpine.js、Tailwind CSS 4、DaisyUI 5 和 Iconify 组件。

不操作生产环境、不使用用户真实 API Key、不向真实模型自动发起请求。执行代码、必要迁移/测试与文档更新；最后输出逐阶段结果、关键文件、验证命令和仍需人工执行的生产迁移 runbook。
```
