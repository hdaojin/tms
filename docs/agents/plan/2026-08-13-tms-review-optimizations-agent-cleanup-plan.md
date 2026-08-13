# TMS 代码 Review 优化与 Agent 指导收敛实施计划

> 目标仓库：`hdaojin/tms`  
> 基线分支：`develop`  
> 计划编写时已确认的 `develop` HEAD：`55a4b2195fb867d67d964944ec51ee1cd6445052`  
> 建议工作分支：`refactor/review-optimizations`  
> 日期：2026-08-13

## 0. Codex 执行指令

请直接执行本计划，不要把本计划重新改写成另一份计划，也不要仅给出建议。

执行前：

1. 从仓库根目录开始。
2. 基于**执行时最新的 `develop`** 开始；如果 `develop` 已经前进，不要 reset 到上面的基线 SHA，而是重新检查本计划涉及文件并适配最新代码。
3. 如果当前已经位于用户为本任务准备的 feature/refactor 分支，继续使用当前分支；否则从最新 `develop` 创建 `refactor/review-optimizations`。
4. 阅读仓库根目录：
   - `AGENTS.md`
   - `CONTEXT.md`
   - 与本计划涉及领域相关的 `docs/adr/`
5. **不要调用 `$tms-dev` skill。** 本计划会删除它；项目级开发规则统一以 `AGENTS.md` 为准。
6. 先运行基线验证并记录结果：
   ```bash
   uv sync
   uv run ruff check .
   uv run manage.py check
   uv run manage.py makemigrations --check --dry-run
   uv run pytest
   npm ci
   npm run build:css
   ```
7. 如果基线本身已有失败：
   - 记录失败；
   - 判断是否与本任务相关；
   - 不要为了让测试变绿而无关修改其他模块；
   - 本任务最终不得新增新的失败。
8. 本任务以**保持现有业务行为、提升一致性/并发安全/性能/可维护性**为原则，不做 UI 重设计，不重命名领域概念，不引入新的架构框架。

---

# 1. 总体目标

本次修改包含两大部分。

## 1.1 Agent 指导体系收敛

删除整个：

```text
.codex/skills/tms-dev/
```

将 `AGENTS.md` 作为 TMS 项目唯一的项目级开发指导文件。

最终职责应明确为：

- `AGENTS.md`
  - 项目长期工程规范；
  - 架构边界；
  - 默认开发流程；
  - 权限、安全、文件、前端、测试约束。
- `CONTEXT.md`
  - 领域术语；
  - 业务语义；
  - 领域不变量。
- `docs/adr/`
  - 已作出的重要架构决策。
- `.github/copilot-instructions.md`
  - 仅作为 Copilot 的简短入口；
  - 指向 `AGENTS.md` / `CONTEXT.md`；
  - 不维护第二套详细规范。
- `.codex/skills/`
  - 当前不保留 `tms-dev`；
  - 将来只有在出现真正“按需触发、专项且重复”的工作流时才新增 Skill；
  - Skill 不得重新复制 AGENTS。

## 1.2 落地 Code Review 已确认的 7 项优化

1. 优化技能树覆盖统计，消除递归查询/N+1 与重复遍历。
2. 为 WorldSkills Forum 来源标识增加数据库级唯一性保护。
3. 将角色判断从可变的 `Group.name` 迁移到稳定 codename/permission。
4. 避免 `ArchiveAsset` 普通保存时重复读取大文件计算 SHA256。
5. 统一模型校验与 service 写入边界，减少 `save() -> clean()` 的隐式副作用。
6. 将“当前技能树版本 / 默认评分解析器”等唯一状态切换改为明确、原子的业务操作。
7. 同步 README，使其与当前架构、私有文件体系和开发命令一致。

---

# 2. 约束与非目标

## 必须遵守

- Django 6 / Python 3.13。
- django-htmx、django-tables2、Tailwind CSS 4、DaisyUI 5、Alpine.js CSP build、Iconify 当前项目约定不得被破坏。
- 保持 Django 单体架构。
- 继续使用 Django 默认 `auth.User`。
- 复杂跨模型写操作放 service。
- 复杂可复用读取/统计放 selector。
- 数据库能可靠表达的并发不变量优先使用数据库约束。
- ModelForm 的用户友好校验与数据库最终一致性应同时存在，而不是二选一。
- 不允许因为本次重构降低 URL 直接访问时的权限保护。
- 不允许暴露 `media-private` 文件。

## 非目标

本次不要：

- 新建新的业务 APP。
- 重做 TMS 领域模型。
- 重做页面视觉设计。
- 全仓库机械式重构所有 model `save()`。
- 引入 Pydantic、DRF、Celery 等新基础框架。
- 将所有旧兼容代码一次性删除。
- 改变评分、知识点、训练等业务统计口径。
- 修改与本计划无关的历史 migration。

---

# 3. Phase A：删除 `tms-dev` Skill，并收敛 AGENTS

## 3.1 删除整个 Skill

删除：

```text
.codex/skills/tms-dev/SKILL.md
.codex/skills/tms-dev/agents/openai.yaml
.codex/skills/tms-dev/references/project-overview.md
.codex/skills/tms-dev/references/feature-checklist.md
```

目录为空后无需保留 `.codex/skills/tms-dev/`。

不要把 `project-overview.md` 或 `feature-checklist.md` 原样搬到其他目录。

原因：

- `project-overview.md` 与 AGENTS/CONTEXT/实际代码重复，容易漂移。
- `feature-checklist.md` 本质属于所有开发任务的默认流程，应由 AGENTS 统一表达。
- `tms-dev` 没有明确的专项触发边界，属于“始终应该遵守”的项目规则，而不是 Skill。

## 3.2 调整 `AGENTS.md`

在保留现有高质量内容的基础上做**小幅收敛**，不要重新大写一遍。

至少确认或补充以下内容：

### 权威边界

明确：

```text
AGENTS.md = 唯一项目级开发指导
CONTEXT.md = 领域语义
docs/adr = 架构决策
Copilot instructions = 指针
```

将关于 `.codex/skills/*` 的描述调整为：

- 当前仓库不维护通用的 TMS 开发 Skill。
- 只有未来出现明确专项任务工作流时才允许增加 Skill。
- Skill 不得重复项目通用规范。

### 默认开发闭环

如果 AGENTS 现有内容尚未清晰覆盖，可增加一个**短小**章节，不复制原 `SKILL.md`：

```text
需求/权限/入口
    ↓
追踪实际纵向链路
    ↓
确定 model / form / service / selector / view / template 职责
    ↓
实现最小完整切片
    ↓
检查事务 / 幂等 / 并发 / N+1 / 文件副作用
    ↓
测试 + migration check + Ruff + CSS build
    ↓
同步用户文档/README（如行为发生变化）
```

## 3.3 检查 Copilot 指令

检查：

```text
.github/copilot-instructions.md
```

要求：

- 只保留极简入口；
- 指向 `AGENTS.md`；
- 涉及领域语义时指向 `CONTEXT.md`；
- 不出现 `$tms-dev`；
- 不复制 AGENTS 的完整规则。

## 3.4 全仓库清理引用

运行：

```bash
rg -n "tms-dev|project-overview\.md|feature-checklist\.md|\.codex/skills/tms-dev" .
```

除历史记录或明确说明“已移除”的文档外，不应再存在有效引用。

## 3.5 验收

- `.codex/skills/tms-dev/` 不再存在。
- Codex/Copilot 项目开发规范只有一个权威来源：`AGENTS.md`。
- AGENTS 没有因为整合而膨胀成原 Skill 的全文复制品。

---

# 4. Phase B：优化技能树覆盖统计

重点文件：

```text
knowledge/selectors.py
standards/models.py
knowledge/tests/...
```

当前问题：

`get_skill_tree_coverage_rows()` 已一次性读取技能节点，但对于每个非 SKILL 节点仍调用：

```python
node.get_descendants(active_only=True)
```

而 `SkillNode.get_descendants()` 内部继续执行：

```python
node.children.order_by(...).filter(...)
```

因此预取的 `children` 不能可靠消除递归查询，并且同一子树会被不同祖先反复遍历。

## 4.1 保持公共输出契约不变

`get_skill_tree_coverage_rows(tree_version)` 返回 row dict 的字段、含义和排序不得改变：

```text
node
direct_evidence_count
direct_weighted_mark
subtree_skill_count
subtree_evidence_count
subtree_weighted_mark
is_covered
parent
```

`get_skill_tree_coverage_summary()` 的统计口径也不得改变。

## 4.2 新实现

在 selector 中：

1. 一次加载该 `tree_version` 的全部节点。
2. 使用：
   ```python
   node_by_id
   children_by_parent_id
   ```
   在内存构建邻接关系。
3. 一次加载 approved mappings 并构建：
   ```python
   direct_stats_by_skill_id
   ```
4. 在内存中自底向上或使用**纯内存 DFS + memoization**计算每个节点的 subtree 汇总。
5. 不得在循环/DFS 中访问会触发 ORM 查询的：
   ```python
   node.children
   node.parent
   node.get_descendants()
   ```
6. 保持当前 inactive 语义：
   - SKILL 节点只有自身 `is_active=True` 时才计入 subtree；
   - 非 SKILL 节点只沿 active child 分支继续统计；
   - inactive child 及其下级不应通过该分支计入祖先结果；
   - 当前节点自身即使 inactive，也要保持现有 row 是否展示的行为。
7. 加入防御性 cycle 保护，避免异常脏数据导致无限递归；正常数据库不应出现环。

## 4.3 性能测试

新增 query-count 测试。

至少覆盖：

- CATEGORY -> TOPIC -> SKILL 多层树。
- 多个 sibling。
- inactive TOPIC / SKILL。
- 有映射和无映射技能点。
- 多个 evidence / weight。

建议使用 Django 的 query capture/assert 工具，验证：

- 增大节点数量不会线性增加 SQL 查询数量；
- `get_skill_tree_coverage_rows()` 查询数保持为固定小常数；
- 不对每个节点产生额外 children query。

不要只测试返回值，还必须测试查询数量。

## 4.4 验收

- 与原逻辑结果一致。
- 无递归 ORM 查询。
- 大树复杂度主要为 O(N + M)，N 为节点数，M 为映射数。

---

# 5. Phase C：WorldSkills Forum 数据库唯一性

重点文件：

```text
worldskills_forum/models.py
worldskills_forum/migrations/
worldskills_forum/tests/
```

当前业务规则：

### ForumTopic

- 非空 `source_topic_id` 全局唯一。
- `source_url` 全局唯一。

### ForumPost

- 同一 `topic` 下，非空 `source_post_id` 唯一。

当前主要由 `clean()` 中 `.exists()` 保护，存在并发竞态。

## 5.1 保留友好校验

不要简单删除现有 `clean()` 校验。

Model/Form 层仍应提供中文友好错误。

数据库约束作为并发条件下的最终兜底。

## 5.2 兼容 PostgreSQL / MySQL / SQLite

README 当前允许 PostgreSQL 或 MySQL，开发环境常用 SQLite，因此实现不能只考虑 PostgreSQL partial unique index。

对于：

```text
source_topic_id
source_post_id
```

优先采用 Django 对“`blank=True + unique` 字符串字段”的推荐思路：

- 将“无来源 ID”规范化为 `NULL`；
- 字段使用 `null=True, blank=True`；
- 数据 migration 把已有 `""` 转为 `NULL`；
- 再使用普通数据库唯一约束。

推荐目标：

### ForumTopic

```text
source_topic_id:
    nullable
    non-null value unique globally

source_url:
    unique globally
```

### ForumPost

```text
(topic, source_post_id):
    source_post_id 为 NULL 时允许多条
    非 NULL 时同一 topic 唯一
```

实现形式可使用字段 `unique=True` 或普通 `UniqueConstraint`，但要保证三个目标数据库后端的语义一致。

如果 Codex 经过当前 Django 6 官方文档和项目数据库配置验证，发现存在更简洁且三个后端均可靠的实现，可以采用等价方案；不要为了保持空字符串而依赖 MySQL 不支持的 partial unique 行为。

## 5.3 安全 migration

migration 必须处理既有数据。

顺序：

1. 检查已有重复的非空 `source_topic_id`。
2. 检查重复 `source_url`。
3. 检查同 topic 下重复的非空 `source_post_id`。
4. 如果存在无法自动判断应保留哪条的业务重复：
   - **禁止静默删除或合并**；
   - migration 应给出明确、可操作的错误；
   - 或在 schema migration 前提供明确的数据修复 migration/逻辑；
   - 不允许“随便保留第一条”。
5. 将空字符串来源 ID 正规化为 NULL。
6. 添加数据库唯一约束。

## 5.4 测试

测试：

- 两个空 `source_topic_id` 可以同时存在。
- 两个相同非空 `source_topic_id` 不允许。
- 两个相同 `source_url` 不允许。
- 不同 topic 可以拥有相同 `source_post_id`。
- 同 topic 相同非空 `source_post_id` 不允许。
- 多个空 `source_post_id` 可以存在。
- ModelForm/full_clean 能给出友好错误。
- 绕过 ModelForm 直接数据库写入时，数据库约束仍能阻止重复。

对 `IntegrityError` 测试使用独立 `transaction.atomic()` savepoint，避免破坏整个测试事务。

---

# 6. Phase D：角色身份从 `Group.name` 迁移到稳定 codename

重点文件：

```text
accounts/models.py
accounts/fixtures/accounts/default.yaml
core/utils/mixins.py
core/permissions/
相关 tests
```

当前已存在稳定值：

```text
coach
competitor
assistant
```

它们来自 `GroupProfile.codename`。

当前 `CrossGroupAccessMixin` 仍通过：

```text
Group.name == "教练"
Group.name == "选手"
```

判断角色。

## 6.1 建立统一 role helper

在现有权限体系附近建立一个**很小的**统一 helper，优先放在：

```text
core/permissions/roles.py
```

或如果当前代码依赖关系显示更合适，可放：

```text
accounts/services/roles.py
```

但不要形成循环 import。

建议提供：

```python
ROLE_COACH = "coach"
ROLE_COMPETITOR = "competitor"

get_user_role_codenames(user) -> set[str]
user_has_role(user, codename) -> bool
```

要求：

- 未登录用户安全返回空集合/False。
- 无 GroupProfile 的历史 Group 不抛异常。
- 查询尽量一次完成，不逐 group N+1。
- 不通过 Group 显示名称推导 codename。

## 6.2 改造 `CrossGroupAccessMixin`

保持现有业务语义：

- superuser：可访问。
- owner 本人：可访问。
- competitor 可查看 coach。
- coach 可查看 competitor。
- 其他角色不自动获得该跨组权限。

但判断依据改为稳定 codename。

可以为了兼容保留旧方法名，但内部语义应明确为 role codename；如果改名，更新全部调用方和测试。

## 6.3 不扩大本次范围

本次不要把全仓库所有权限逻辑重写成 RBAC 框架。

只处理：

- 已发现的 `Group.name` 角色身份依赖；
- 与之直接关联的 helper / mixin / tests；
- 新代码遵循 permissions-first 原则。

运行：

```bash
rg -n "GROUP_COACH|GROUP_COMPETITOR|groups.*name|Group\.name|values_list\(['\"]name" .
```

逐项判断：

- 真正用于“显示”的代码可保留 name。
- 用于授权/业务身份判断的代码迁移到 codename/permission。

## 6.4 测试

关键回归测试：

1. `coach` / `competitor` 正常互访。
2. owner 正常访问。
3. superuser 正常访问。
4. 无 profile group 不导致异常。
5. 将 Group 的显示名称从“教练”改成任意文字后，`coach` 身份仍然有效。
6. 将“选手”显示名称改名后，`competitor` 身份仍然有效。

最后一项是本优化的核心验收条件。

---

# 7. Phase E：避免 ArchiveAsset 重复计算 SHA256

重点文件：

```text
archives/models.py
archives/services.py（如确有必要）
archives/tests/
调用 ArchiveAsset 的 scoring/training 等 tests
```

当前 `ArchiveAsset.save()` 只要 `self.file` 存在，就会重新完整读取文件并计算 SHA256。

对于大评分表、结果包、ZIP、试题文件，修改标题、metadata、锁定状态也会重复产生 I/O。

## 7.1 目标语义

只在以下场景计算 SHA256：

1. 新建 ArchiveAsset，存在文件。
2. `file_sha256` 缺失，需要补全。
3. 文件实际被替换/重新上传。

以下场景不得重新 hash：

- 修改 title。
- 修改 description。
- 修改 metadata。
- 修改 source 信息。
- 修改 `is_locked`。
- 其他不涉及 file 的 update。

## 7.2 实现要求

优先利用 Django `FieldFile` 的实际状态，以及 `_state.adding` / `update_fields` 等信息，避免为了判断“文件是否变化”每次额外读取数据库。

实现应清晰封装，例如：

```python
def _should_recalculate_hash(self, ...):
    ...
```

不要把复杂判断全部堆在 `save()` 内。

如果现有调用场景表明“ArchiveAsset 创建”已经由 service 承担，可以把文件 hash 的业务入口进一步收敛到 service；但不要为了此次优化强行重写所有 ArchiveAsset 创建调用方。

## 7.3 文件名语义

保持：

```text
original_filename
filename
file_sha256
```

现有对外行为不变。

替换文件时应重新计算：

- SHA256；
- 如果现有逻辑要求，正确维护 original filename。

不得因为优化造成旧 hash 对应新文件。

## 7.4 测试

通过 patch/mock `calculate_file_sha256` 或测试文件对象验证：

- 创建资产：调用 1 次。
- 只改 metadata 后 save：不再次调用。
- 只改 title：不再次调用。
- 文件替换：再调用 1 次。
- 数据库中 hash 为空时普通 save：可补算一次。
- hash 结果保持正确。

---

# 8. Phase F：统一 Model validation 与 Service 写入边界

这是本计划中最需要控制范围的一步。

目标不是“删除所有 `clean()`”，而是消除以下混乱：

```text
有的 ModelForm 会做模型验证
有的 model.save() 又隐式 self.clean()
有的 service 直接 objects.create()
有的跨模型规则藏在 save()
```

Django 6 的基本原则：

- `Model.full_clean()` 会执行字段、model、unique、constraint 验证。
- `Model.save()` 不会自动调用 `full_clean()`。
- ModelForm 会在自己的验证流程中执行模型验证。
- 并发一致性最终仍应由数据库约束/事务保证。

## 8.1 先盘点，不机械修改

运行：

```bash
rg -n "def save\(" --glob="*.py"
rg -n "self\.clean\(\)|full_clean\(" --glob="*.py"
rg -n "\.objects\.create\(|bulk_create\(" standards events examcontent scoring knowledge training archives
```

生成内部审计结论，将相关 model 分为：

### A. 只做派生字段/格式规范化

例如 slug、文件元信息等。

可继续在 save 中做轻量、局部、无跨模型副作用的处理。

### B. 实体自身业务校验

规则留在：

```python
clean()
```

让 ModelForm/admin 可以给用户友好错误。

不要默认把：

```python
self.clean()
```

机械塞进每一个 `save()`。

### C. 跨记录/跨模型业务动作

例如：

- 设为当前版本时取消其他当前版本；
- 设为默认解析器时取消其他默认；
- 导入一个评分方案同时生成多个关联对象。

必须迁移到 service/明确业务方法。

## 8.2 本次实际修改范围

至少处理本计划已经触及或已确认存在隐式 `save()->clean()` / 跨记录副作用的模型：

```text
standards.SkillTreeVersion
standards.SkillNode
scoring.ScoringScheme
scoring.ScoringParserConfig
```

并通过 `rg` 检查主链路是否还有同类明显问题。

要求：

- 跨记录副作用必须在 Phase G 移出普通 save。
- 对 `SkillNode` / `ScoringScheme` 这类实体校验：
  - 保留 `clean()`；
  - 检查所有非 ModelForm 写入口；
  - service/direct programmatic create 在需要时显式 `full_clean()`；
  - 只有确认全部写入口和测试覆盖后，才移除 `save()->clean()`。
- 如果某个现有模型的 `save()->clean()` 暂时承担大量兼容行为，且本次无法安全迁移所有调用方：
  - 可以暂时保留；
  - 在代码注释/测试中明确兼容原因；
  - 不要为了“风格统一”制造回归。

本阶段追求的是**边界清晰**，不是“所有模型代码长得一样”。

## 8.3 测试

覆盖：

- ModelForm 非法输入仍返回友好错误。
- service/direct write 非法数据不会被悄悄持久化。
- 数据库 constraint 仍是最终兜底。
- fixture、admin、现有导入流程不因 validation 调整失败。

---

# 9. Phase G：当前/默认状态切换改为原子业务操作

重点：

```text
standards.SkillTreeVersion.is_current
scoring.ScoringParserConfig.is_default
```

当前模式：

```text
save(target=True)
    ↓
UPDATE other rows => False
    ↓
SAVE target
```

这属于跨记录状态迁移，不应隐藏在普通 model `save()` 中。

## 9.1 SkillTreeVersion

新增明确 service，例如：

```python
standards.services.set_current_skill_tree_version(...)
```

或命名等价、符合仓库风格的业务函数。

要求：

1. `transaction.atomic()`。
2. 锁定该 `SkillProject` 或该项目相关版本，确保同一项目的切换串行化。
3. 将其他版本设为 `is_current=False`。
4. 将目标设为 `True`。
5. 保留现有：
   ```text
   uniq_current_skilltreeversion_per_project
   ```
   数据库约束。
6. 查找并修改所有“设为当前版本”的调用方，必须走 service。
7. 普通保存名称/描述不得意外触发跨记录更新。

如果 UI 是通过编辑表单直接勾选 `is_current`：

- 不要让 ModelForm.save() 隐式承担跨记录事务；
- view/form_valid 应明确调用 service；
- 或将“设为当前版本”改为独立业务 action；
- 优先最小化 UI 改动。

## 9.2 ScoringParserConfig

新增明确 service，例如：

```python
scoring.services.set_default_parser_config(...)
```

要求：

1. `transaction.atomic()`。
2. 尽可能使用 `select_for_update()` 锁定当前配置集合。
3. 先取消其他默认值，再设目标为默认。
4. 保留：
   ```text
   默认解析器必须 enabled
   ```
   的实体校验。
5. 普通编辑 display name / alias / description 不执行跨记录状态迁移。
6. 查找所有设置默认解析器入口并改用 service。

## 9.3 并发与约束

不要只依赖：

```python
if not exists():
    ...
```

数据库已有唯一约束的继续保留。

如果当前某个 conditional unique constraint 在 MySQL 上不能完全提供同等保护：

- 不要在本任务中悄悄声称数据库已跨后端完全保证；
- 以 service transaction + 当前 backend 可用 constraint 为主；
- 如果要改变 schema 以获得真正跨后端唯一性，必须有迁移和专项测试，且不得顺带扩大重构范围。

## 9.4 测试

至少：

- 同项目切换 current 后仅一个 current。
- 不同 SkillProject 可各自有 current。
- 切换过程中发生异常时事务完整回滚。
- 默认 parser 切换后仅一个 default。
- disabled parser 不能成为 default。
- 普通保存目标对象不改变其他记录。
- service 可重复调用且最终状态一致。

如果测试环境和数据库能力允许，增加 `TransactionTestCase` 覆盖并发切换；否则至少测试原子回滚与数据库唯一约束。

---

# 10. Phase H：同步 README

重点文件：

```text
README.md
```

README 只描述当前事实，不再保留已被架构替换的说明。

## 10.1 功能概览

根据当前 APP/主链路更新，至少体现：

- 用户/角色/权限；
- 技能项目与标准技能树；
- 赛事/考核；
- 试题与评分方案；
- 考点证据/技能映射；
- 训练周期与训练记录；
- 统一资料归档；
- 通知、会议、笔记；
- WorldSkills Forum 翻译归档。

保持 README 简洁，不复制 CONTEXT。

## 10.2 文件目录说明

修正当前类似：

```text
media/：公共上传目录，例如训练日志...
```

的过时表述。

当前领域主链路资料，尤其：

- 训练日志附件/资料；
- 试题；
- 评分表；
- 结果包；
- 评分脚本；
- 归档附件；

应按实际代码说明 `ArchiveAsset` / `PrivateMediaStorage` / `media-private`。

明确：

- `media/` 仅用于确实公开的上传；
- 私有资料不得由 Nginx 直接暴露；
- 私有文件通过有权限检查的 Django view 提供。

## 10.3 开发命令

与 CI/AGENTS 对齐，至少确认：

```bash
uv run ruff check .
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
uv run pytest
npm ci
npm run build:css
```

本地开发初次安装仍可使用 `npm install`；CI/可重复构建使用 `npm ci`。

## 10.4 Agent 文档说明

可增加一小段“开发约定”：

```text
工程规则：AGENTS.md
领域语义：CONTEXT.md
架构决策：docs/adr/
```

不要在 README 再复制具体规范。

---

# 11. 全局测试与质量要求

## 11.1 每个 Phase 后做聚焦测试

示例：

```bash
uv run pytest knowledge
uv run pytest worldskills_forum
uv run pytest accounts core
uv run pytest archives
uv run pytest standards scoring
```

按实际测试目录调整。

## 11.2 Migration 检查

涉及 model 后：

```bash
uv run manage.py makemigrations
```

检查生成 migration，只保留本计划要求的 schema 变化。

然后：

```bash
uv run manage.py makemigrations --check --dry-run
uv run manage.py migrate
```

不要手工修改旧 migration；新增 migration。

## 11.3 最终全量验证

必须执行：

```bash
uv run ruff check .
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
uv run pytest
npm run build:css
```

如果 `package-lock.json` 没有变化，不要无故更新 npm 依赖。

本计划没有前端视觉功能改动，理论上 `static/css/output.css` 不应出现无关变化；如果 build 产生变化，检查原因。

---

# 12. 建议测试清单

至少新增或强化以下测试。

## knowledge

- coverage rows 结果保持一致。
- inactive 分支语义。
- query count 为固定小常数。
- 大量节点不会产生 N+1。

## worldskills_forum

- topic ID 唯一。
- topic URL 唯一。
- post ID 在 topic 内唯一。
- NULL/空来源 ID 可重复。
- DB-level IntegrityError。
- model/form 友好 ValidationError。

## accounts / core permissions

- coach / competitor codename。
- 改 Group 显示名不影响角色身份。
- 无 GroupProfile 安全处理。
- CrossGroupAccessMixin 原行为回归。

## archives

- 新文件 hash。
- metadata update 不 rehash。
- title update 不 rehash。
- replace file 会 rehash。
- missing hash 可补算。

## standards

- current version 切换。
- 不同 skill project 相互独立。
- service transaction rollback。
- SkillNode validation 回归。

## scoring

- default parser 切换。
- disabled parser 不可 default。
- transaction rollback。
- ScoringScheme validation 回归。
- 评分表导入现有 service 流程继续通过。

---

# 13. 建议提交粒度

如果执行环境允许提交，建议按逻辑拆分，避免一个巨大 commit：

1. `docs: remove tms-dev skill and consolidate agent guidance`
2. `perf: optimize skill tree coverage aggregation`
3. `fix: enforce forum source uniqueness`
4. `refactor: use stable role codenames for cross-group access`
5. `perf: avoid redundant archive asset hashing`
6. `refactor: clarify model validation boundaries`
7. `fix: make current and default transitions atomic`
8. `docs: sync README with current architecture`

如果中间两项高度耦合，可以合理合并，但不要把全部内容压成一个难以 review 的超大提交。

---

# 14. 最终验收标准

完成后必须同时满足：

- [ ] `.codex/skills/tms-dev/` 已完全删除。
- [ ] `AGENTS.md` 是唯一项目级开发规范。
- [ ] `.github/copilot-instructions.md` 不再形成第二套规范。
- [ ] 全仓库无有效 `$tms-dev` 引用。
- [ ] 技能树 coverage 不再递归查询数据库。
- [ ] coverage 结果与现有业务口径一致。
- [ ] Forum 的关键来源唯一性有数据库保护。
- [ ] Forum 空来源 ID 仍允许存在多条记录。
- [ ] CrossGroupAccess 不再依赖“教练/选手”显示名称。
- [ ] 修改 Group.name 不影响 `coach` / `competitor` 身份。
- [ ] ArchiveAsset 修改元数据不会重复计算文件 SHA256。
- [ ] 替换 ArchiveAsset 文件会正确重新计算 SHA256。
- [ ] 跨记录状态迁移不再隐藏在普通 `save()` 中。
- [ ] 当前技能树版本切换是明确、原子的 service 操作。
- [ ] 默认评分解析器切换是明确、原子的 service 操作。
- [ ] ModelForm 用户友好校验没有退化。
- [ ] 非表单写入口的关键业务校验没有丢失。
- [ ] README 与当前 APP、ArchiveAsset、private media、测试命令一致。
- [ ] `uv run ruff check .` 通过。
- [ ] `uv run manage.py check` 通过。
- [ ] `uv run manage.py makemigrations --check --dry-run` 通过。
- [ ] `uv run pytest` 全量通过。
- [ ] `npm run build:css` 通过。
- [ ] 没有无关代码格式化、依赖升级或 UI 改动。

---

# 15. Codex 最终输出要求

实施结束后，请输出：

1. 实际修改的文件列表。
2. 每项优化对应的实现摘要。
3. 新增 migration 名称及其数据影响。
4. 新增/修改测试摘要。
5. 性能优化前后的 SQL query 数量对比（针对 skill tree coverage）。
6. 是否发现历史重复 Forum 数据；如有，说明处理结果。
7. 是否还存在基于 `Group.name` 的**授权/身份判断**；如果保留，说明原因。
8. 是否仍有主链路 model 使用 `save()->clean()`；如果保留，逐项说明为何本次没有迁移。
9. 最终运行的验证命令及结果。
10. 本计划范围内尚未解决、需要后续单独处理的问题。

不要只回答“已完成”；必须给出可 review 的实施结果。
