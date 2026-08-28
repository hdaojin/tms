# TMS `bootstrap_tms` v2：可读声明、预览确认与强制覆盖实施 Plan

> **文档性质**：可供 Codex 直接执行的工程实施计划  
> **目标仓库**：`hdaojin/tms`  
> **目标分支**：`codex/assessment-refactor`  
> **编制日期**：2026-08-28  
> **基线 HEAD**：`df0f28b28d24de088b76d559265aec546fdd136d`（`bootstrap_tms v1`）  
> **任务范围**：只重构 Bootstrap 默认业务数据声明、预览/确认/覆盖执行机制及其测试、README、AGENTS/ADR；不要借机扩展到无关业务重构。

---

# 0. 执行契约

本 Plan 基于对 `codex/assessment-refactor@df0f28b2` 的实际代码 Review，以及已经确认的新 Bootstrap 目标行为编制。

以下结论视为已经确认，不再重新讨论：

1. `bootstrap.py` 首先服务于**人类阅读和人工自定义**。默认数据必须使用普通 Python `list[dict]` / `dict`，字段名完整可见；不得继续以位置元组作为主要编辑界面。
2. 每个 APP 的 `bootstrap.py` 应尽量成为**纯声明文件**：允许常量、普通字典/列表、必要的轻量数据生成函数，但不得在 import 时访问数据库；通用 ORM 执行逻辑不得散落在各 APP。
3. `bootstrap_tms` 必须采用“**读取/校验/生成计划 → 输出预览 → 确认 → 原子执行**”的模式。
4. 普通模式：
   - 缺失默认项：`CREATE`；
   - 已有且完全相同：`UNCHANGED`；
   - 已有但声明字段不同：`SKIP`，不得覆盖管理员修改；
   - 数据库额外存在、但 Bootstrap 未声明的数据：`UNMANAGED` / 忽略，不删除。
5. `--force` 模式：
   - 缺失默认项：`CREATE`；
   - 已有且完全相同：`UNCHANGED`；
   - 已有但声明字段不同：`UPDATE`，只覆盖 Bootstrap 明确声明为受管字段的值；
   - 数据库额外数据仍不删除。
6. `--force` **不等于** `--yes`；强制覆盖仍必须先输出完整预览。
7. `--dry-run` 永远不写数据库；允许与 `--force` 组合，用于预览强制覆盖会发生什么。
8. `--yes` 仅跳过人工确认，不跳过预览、不改变覆盖策略。
9. Apply 阶段必须由一个外层 `transaction.atomic()` 保证全站要么全部成功、要么全部回滚。
10. 强制覆盖只能按稳定业务键定位并 `UPDATE`，不得通过删除后重建实现；不得改变稳定 `code` / `slug` / Registry key 等机器身份。
11. 本次将前一版讨论中已经接受的竞赛与考核基础默认目录补入可读声明：
    - `AssessmentLevel`：至少预置 `world / national / provincial`（世界级 / 国家级 / 省级），默认 `weight=1.00`，排序 10/20/30；
    - `AssessmentSeries`：预置 `worldskills / 世界技能大赛`；
    - 后续用户可以直接编辑 `assessments/bootstrap.py` 自定义或补充。
12. `core/config/permission_bundles.yml`、代码 Registry、Enum 本身仍不是普通业务 Bootstrap 数据；不要把它们复制成第二份人工目录。Registry 对应的数据库运行时配置可以由 Bootstrap 初始化。
13. 历史 migration 不回写、不重写。此次无 schema 需求时不得生成 migration。

---

# 1. Review 结论：当前 v1 存在的问题

## P0：命令没有 Preview / Confirm，调用即写库

当前 `core/management/commands/bootstrap_tms.py` 进入 `handle()` 后直接打开事务并依次执行各 APP `bootstrap_defaults()`。

问题：

- 用户在真正写入前看不到将创建什么；
- 已有系统无法知道哪些数据会被认为“existing”；
- 不符合已经确认的“先预览、再确认”流程；
- 没有 `--dry-run`、`--force`、`--yes`。

必须重构为 Plan / Apply 两阶段。

## P0：没有强制恢复出厂值的能力

当前所有业务目录基本使用：

```python
get_or_create(stable_key=..., defaults=...)
```

因此管理员修改后永远保留，没有受控方式恢复默认值。

这对生产默认模式是正确的，但对测试环境反复验证不够。必须增加 `--force`，且强制覆盖仍经预览、确认和单一事务。

## P0：`bootstrap.py` 的用户可读性不足

当前多个 APP 使用位置元组：

```python
("competition", "正式竞赛", 10)
("bug", "Bug反馈", False, 10)
```

`behaviors/bootstrap.py` 更存在 5～6 个位置字段；`worldskills_forum/bootstrap.py` 还通过 `enumerate()` 隐式生成排序。

这导致：

- 字段含义必须跳到执行代码里猜；
- 修改一个值容易错位；
- 新增模型字段后很难判断 Bootstrap 是否应该管理；
- 排序值不是声明的一部分，不便人工定制。

所有人工维护的默认目录改为字段完整的 `list[dict]`。

## P0：当前统计把“相同”和“不同”混在 `existing`

v1 只有：

```text
created=N, existing=N
```

但“数据库与声明完全一致”和“管理员已经改了 5 个字段”被视为同一种状态。

必须改成逐记录、逐字段 Diff，并至少统计：

```text
CREATE
UPDATE          # 仅 force
SKIP            # 普通模式下存在差异
UNCHANGED
ERROR
```

可选显示 `UNMANAGED/WARNING`，但不能把数据库额外数据当作待删除项。

## P1：各 APP 同时承担“默认数据声明”和“ORM 执行器”

当前：

- `assessments/bootstrap.py`
- `feedback/bootstrap.py`
- `worldskills_forum/bootstrap.py`
- `behaviors/bootstrap.py`
- `event_countdown/bootstrap.py`
- `scoring/bootstrap.py`
- `core/bootstrap.py`

都自己实现 `get_or_create()`、统计、冲突检查。

后果是相同规则重复实现，未来 Preview / Force 必须再复制 7 套逻辑，行为很容易不一致。

应把通用 Plan / Diff / Apply 能力集中到 `core`，APP 文件只描述“有哪些数据、稳定键是什么、哪些字段受管、FK 如何按自然键解析”。

## P1：冲突校验发生在写入过程中，而不是完整 Preflight

v1 虽然有外层事务，后续 APP 冲突会回滚前面的写入，但用户只有在真正进入 Apply 后才知道冲突。

v2 必须在确认前完成只读 Preflight：

- Bootstrap 声明重复稳定键；
- 字段名不存在；
- 必填受管字段缺失；
- FK 自然键引用不存在或在计划中也不存在；
- 同一声明内的冲突；
- 已知的名称/组合唯一冲突；
- Registry 默认 key 不存在；
- Registry DB 配置引用不存在实现等。

发现 `ERROR` 时不得进入确认和 Apply。

## P1：异常边界不适合 management command

各 APP 当前直接抛 `ValidationError`，命令本身没有转换。

在 management command 边界应将可预期的 Bootstrap 配置/冲突错误整理后抛 `CommandError`，让 CLI 得到简洁错误，而不是默认把业务校验异常当成未处理异常。

内部可以定义 `BootstrapConfigurationError` / `BootstrapPlanError`，但不要建立庞大异常体系。

## P1：`core` FlatPage 已有记录的 Site 关系不会被检查

当前 `core/bootstrap.py` 仅在 FlatPage **新建时**执行：

```python
page.sites.add(site)
```

如果 `/about/site/` 已经存在但未绑定 `settings.SITE_ID`，Bootstrap 会把它统计为 `existing`，既不提示也不修复。

v2 必须把“当前 Site 绑定”纳入预览：

- 普通模式：显示差异并 `SKIP`；
- `--force`：显示并补齐当前 Site 关系；
- 不删除该 FlatPage 已有的其他 Site 关系。

不要为了这一处需求建立通用大型 M2M 框架；允许使用一个小型 `core` 专用 adapter/hook。

## P1：`scoring` Registry 与数据库漂移目前不会被发现

`scoring/bootstrap.py` 只遍历当前 `PARSER_DEFINITIONS`，而读取路径 `enabled_parser_configs()` 会直接返回数据库里所有启用配置。

如果数据库遗留了已经从 Registry 删除的 `parser_key`，v1 Bootstrap 会忽略它，但运行时仍可能把它作为可选解析器暴露，随后在获取实现时失败。

v2 Preflight 至少应报告 Registry 漂移：

- 数据库存在、Registry 不存在的 `ScoringParserConfig`：不得静默当正常；
- 默认建议：作为 `ERROR` 阻止 Apply，提示通过明确数据迁移/人工处理恢复 Registry 不变量；
- Bootstrap 不自动删除该记录。

## P1：Force 的“出厂值”目前定义不完整

许多声明没有显式写出：

- `description`；
- `is_active`；
- 部分默认布尔字段；
- `worldskills_forum` 的明确 `sort_order`。

普通 `get_or_create(defaults=...)` 可以依赖 Model 默认值，但 `--force` 要回答“恢复成什么”，就必须有明确受管值。

人工目录声明中应把希望 `--force` 恢复的字段全部写清楚。不要覆盖审计时间、PK 等非 Bootstrap 字段。

## P1：有条件唯一约束的数据不能天真逐条 Force Update

`behaviors.ConductSeverityRule` 每个 `nature` 只能有一个 `is_default=True`；`ScoringParserConfig` 也只有一个默认解析器。

如果管理员把默认项改到另一条记录，Force 直接按列表顺序把目标行先设成 `True`，可能在旧默认行尚未清理前触发唯一约束。

Apply 必须处理这类“默认项切换”：

- 在同一外层事务中；
- 先把受影响集合的旧 `is_default` 清为 False；
- 再设置声明中的目标默认项；
- 预览仍只展示最终状态，不展示内部临时操作。

只为确实存在的条件唯一约束做小型专用 apply hook，不构造通用工作流引擎。

## P2：当前 v1 测试锁死了旧语义

`core/test_bootstrap.py` 当前明确测试“重复 Bootstrap 永远保留管理员修改”；这个测试只能覆盖普通模式，不再能代表所有模式。

需要改成：

- 普通模式仍保留管理员修改；
- `--force` 恢复受管字段；
- `--force` 不删除额外数据；
- `--dry-run` 零写入；
- 取消确认零写入；
- 任一 Apply 失败全局回滚。

---

# 2. 目标 CLI 契约

最终只提供必要的四种组合，不增加 `--sync`、`--prune`、`--reset`、`--app` 等本次没有需求的选项。

## 2.1 普通交互模式

```bash
uv run manage.py bootstrap_tms
```

流程：

```text
只读 Preflight
  ↓
生成普通模式计划
  ↓
打印完整预览
  ↓
ERROR? ── yes → 退出，零写入
  ↓ no
是否存在 CREATE? ── no → 输出“无需修改”，退出
  ↓ yes
确认 [y/N]
  ↓
transaction.atomic()
  ↓
Apply CREATE
```

普通模式下差异记录显示为 `SKIP`，不写入。

## 2.2 强制覆盖模式

```bash
uv run manage.py bootstrap_tms --force
```

流程相同，但已有不同记录显示为 `UPDATE`，确认后恢复声明的受管字段。

输出开头必须有醒目标识：

```text
强制覆盖模式：将覆盖 Bootstrap 已声明记录的受管字段；不会删除额外数据库数据。
```

## 2.3 Dry-run

```bash
uv run manage.py bootstrap_tms --dry-run
uv run manage.py bootstrap_tms --force --dry-run
```

要求：

- 输出与对应真实模式相同的计划；
- 不询问确认；
- 不进入 Apply；
- 数据库零写入。

## 2.4 自动确认

```bash
uv run manage.py bootstrap_tms --yes
uv run manage.py bootstrap_tms --force --yes
```

要求：

- 仍输出完整预览；
- 不读取人工输入；
- 有 `ERROR` 仍失败，不得因 `--yes` 绕过校验。

## 2.5 取消与非交互输入

确认提示默认值必须为 No：

```text
是否执行以上修改？ [y/N]:
```

只有 `y` / `yes`（大小写不敏感）执行，其余输入都取消。

如果输入流 EOF 且未传 `--yes` / `--dry-run`，转换为清晰 `CommandError`，提示自动化场景使用 `--yes` 或 `--dry-run`，不得静默执行。

---

# 3. Bootstrap 声明格式

## 3.1 核心原则

用户打开任何业务 APP 的 `bootstrap.py`，应首先看到普通数据，而不是 ORM 或框架对象。

不要采用以下主要编辑形式：

```python
BootstrapSpec(...)
Dataset(...)
("code", "name", True, 10)
```

允许执行器内部使用 dataclass，但**不要要求维护默认数据的人实例化这些类**。

## 3.2 `assessments/bootstrap.py` 目标示例

采用类似：

```python
ASSESSMENT_LEVELS = [
    {
        "code": "world",
        "name": "世界级",
        "weight": "1.00",
        "order": 10,
        "is_active": True,
    },
    {
        "code": "national",
        "name": "国家级",
        "weight": "1.00",
        "order": 20,
        "is_active": True,
    },
    {
        "code": "provincial",
        "name": "省级",
        "weight": "1.00",
        "order": 30,
        "is_active": True,
    },
]

ASSESSMENT_SERIES = [
    {
        "code": "worldskills",
        "name": "世界技能大赛",
        "description": "",
        "order": 10,
        "is_active": True,
    },
]

ASSESSMENT_TYPES = [
    {
        "code": "competition",
        "name": "正式竞赛",
        "description": "",
        "order": 10,
        "is_active": True,
    },
    # ...
]

COMPETITION_ROLES = [
    {
        "code": "project_manager",
        "name": "项目经理",
        "category": "official",
        "description": "",
        "order": 10,
        "is_active": True,
    },
    # ...
]
```

然后在文件末尾提供非常轻量的元数据：

```python
BOOTSTRAP_DATA = [
    {
        "label": "竞赛与考核级别",
        "model": "assessments.AssessmentLevel",
        "key_fields": ("code",),
        "collision_fields": (("name",),),
        "records": ASSESSMENT_LEVELS,
    },
    # ...
]
```

维护默认值时原则上只需要编辑上面的 `list[dict]`。

## 3.3 所有人工业务目录统一改为具名字段

至少覆盖：

- `assessments`：AssessmentLevel、AssessmentSeries、AssessmentType、CompetitionRole；
- `feedback`：FeedbackCategory；
- `worldskills_forum`：ForumCategory、ForumModule、ForumSourceRole、ForumPostType；
- `event_countdown`：CountdownEventType；
- `behaviors`：ConductSeverity、ConductSeverityRule、ConductCategory、ConductItem；
- `core`：SiteConfig、默认 FlatPage。

排序字段必须显式写出 10/20/30...，不再依赖 `enumerate()` 作为人工目录的权威顺序。

## 3.4 关系字段使用自然键，不使用数据库 PK

例如 `behaviors`：

```python
CONDUCT_SEVERITY_RULES = [
    {
        "nature": "REWARD",
        "severity": "MINOR",
        "label": "鼓励",
        "multiplier": "0.00",
        "order": 10,
        "is_default": False,
    },
]

CONDUCT_ITEMS = [
    {
        "category": "attendance",
        "code": "late",
        "name": "迟到",
        "default_score": "-1.00",
        "description": "考勤类惩罚事项：迟到。",
        "is_active": True,
    },
]
```

Dataset 元数据声明：

- `severity` 解析为 `ConductSeverity.code`；
- `category` 解析为 `ConductCategory.code`。

不要在数据声明中出现 `severity_id=3`、`category_id=5`。

## 3.5 `scoring` 是允许的 Registry 派生例外

`ScoringParserConfig` 的实现来源必须仍是 `PARSER_DEFINITIONS`，不要为了追求 `list[dict]` 而手工复制一份 Parser Registry。

允许 `scoring/bootstrap.py` 提供一个小型、无数据库副作用的数据构造函数，将 Registry 转成统一的 Bootstrap records。

规则：

- 普通模式 + 全空配置表：生成与“新环境”一致的默认状态；当前 Registry 中实现默认启用，`default_parser_key()` 对应项为默认；
- 普通模式 + 已存在配置表：新增 Registry 项沿用 v1 的安全策略，创建为禁用、非默认；已有项不同则 `SKIP`；
- `--force`：恢复为新环境的 Registry 出厂状态，即当前 Registry 实现按出厂策略启用，并只保留 `default_parser_key()` 为默认；
- 不删除数据库额外 parser config；但 Registry 已不存在的 key 必须在 Preflight 报错，避免运行时暴露无实现配置。

---

# 4. 通用 Plan / Diff / Apply 结构

## 4.1 新增一个小型 Bootstrap engine

建议新增：

```text
core/bootstrap_engine.py
```

不要把它拆成多层 package，除非实现过程中单文件已经明显失控。

职责只包括：

1. 读取各 APP 的 dataset 声明；
2. 校验声明结构；
3. 根据稳定键读取数据库；
4. 生成记录级和字段级计划；
5. 格式化计划需要的数据；
6. Apply 通用 CREATE / UPDATE；
7. 支持少量明确的专用 hook。

可以内部使用 dataclass，例如：

```text
BootstrapDataset
BootstrapRecordPlan
BootstrapFieldDiff
BootstrapPlan
```

但这些类型是 engine 内部实现细节，不应污染各 APP 的默认数据声明。

## 4.2 Action 语义

建议内部枚举/常量：

```text
CREATE
UPDATE
SKIP
UNCHANGED
ERROR
WARNING
```

其中：

- 普通模式已有差异 → `SKIP`；
- force 模式同一差异 → `UPDATE`；
- DB 额外记录默认不创建 plan item；必要时 Registry 专用检查可产生 WARNING/ERROR。

## 4.3 Diff 只比较受管字段

稳定键用于定位，不作为 UPDATE 目标。

例如：

```python
{
    "code": "national",       # key
    "name": "国家级",         # managed
    "weight": "1.00",        # managed
    "order": 20,              # managed
    "is_active": True,        # managed
}
```

`--force` 只能更新：

```text
name / weight / order / is_active
```

不得更新：

```text
pk / created_at / updated_at / 其他未在声明中的字段
```

## 4.4 值规范化

为了避免字符串 Decimal 与数据库 Decimal 产生假 Diff：

- 使用 Django Model field 的 `to_python()` / 正常字段转换能力统一比较；
- FK 比较稳定自然键，不直接比较 PK；
- Boolean / Integer / Decimal 应输出稳定的人类可读值；
- 不要把 `repr(model_instance)` 当作 Diff 文案。

## 4.5 Preflight 不写数据库

Plan 阶段严禁：

- `save()`；
- `create()`；
- `update()`；
- `get_or_create()`；
- `update_or_create()`；
- M2M `.add()` / `.set()`。

只允许查询和纯 Python 校验。

Plan 阶段至少检查：

- dataset 必需键；
- 模型 label 可解析；
- key field 存在；
- record 字段都属于模型或明确关系声明；
- 同 dataset 稳定键不重复；
- 自然键 FK 能指向数据库现有对象或更早 dataset 中的计划对象；
- collision_fields 不与另一稳定 key 冲突；
- Registry 配置合法；
- 声明默认项等 APP 专属规则。

最终 Apply 时仍应在保存前调用适当模型校验，并由数据库约束兜底。任何异常必须让外层事务整体回滚。

---

# 5. 预览输出设计

不要引入 Rich 等新依赖，使用 Django `self.stdout` / `self.style` 即可。

建议输出：

```text
TMS 默认业务数据预览
模式：普通
============================================================

[assessments.AssessmentLevel] 竞赛与考核级别

+ CREATE world（世界级）
~ SKIP   national（国家级）
    name:  全国级 -> 国家级
    order: 30 -> 20
= UNCHANGED provincial（省级）

[feedback.FeedbackCategory] 反馈分类

= UNCHANGED bug（Bug反馈）

------------------------------------------------------------
CREATE: 1
UPDATE: 0
SKIP: 1
UNCHANGED: 2
ERROR: 0
```

Force：

```text
模式：强制覆盖
警告：将覆盖 Bootstrap 已声明记录的受管字段；不会删除额外数据。
...
~ UPDATE national（国家级）
    name:  全国级 -> 国家级
    order: 30 -> 20
```

要求：

- Preview 与 Apply 使用同一个 plan 对象；
- 不要在确认后重新生成另一套“看不见”的业务决策；
- Apply 时如果发现目标记录的关键旧值已与 preview 时不同，应安全失败并回滚，而不是盲目覆盖新变化。

可通过在 plan 中保存 expected old values，并在事务内 Apply 前复核实现；不要在人工确认期间一直持有数据库事务。

---

# 6. Apply 实现

## 6.1 普通模式

只 Apply `CREATE`。

`SKIP` 和 `UNCHANGED` 都不写数据库。

## 6.2 Force 模式

Apply：

- `CREATE`；
- `UPDATE`。

UPDATE：

- 按稳定业务键重新定位同一记录；
- 验证 preview 时的旧值仍成立；
- 只更新受管字段；
- 不改 stable key；
- 不删除额外记录。

## 6.3 单一外层事务

Apply：

```python
with transaction.atomic():
    ...
```

全 APP 共用同一最外层事务。

不要在各 APP 再各自提交事务。

## 6.4 条件唯一默认项专用处理

### `ConductSeverityRule.is_default`

Force 切换默认项前：

1. 在对应 `nature` 的 Bootstrap 受管规则中先清理旧 `is_default=True`；
2. 再应用声明目标；
3. 全部在同一事务内。

### `ScoringParserConfig.is_default`

同理先清旧默认，再设置 Registry 默认。

保持最终数据库状态与 Preview 一致。

## 6.5 FlatPage Site 专用处理

`FlatPage` 内容字段与 Site 绑定分别显示 Diff。

Force 时只保证：

```text
settings.SITE_ID ∈ page.sites
```

不得为了恢复默认而清空其他 Site 关系。

---

# 7. 各 APP 具体改造

## 7.1 `assessments/bootstrap.py`

改造：

- 位置元组 → `list[dict]`；
- 新增 `ASSESSMENT_LEVELS`；
- 新增 `ASSESSMENT_SERIES`；
- `ASSESSMENT_TYPES` 补齐 description / is_active；
- `COMPETITION_ROLES` 补齐 description / is_active；
- 移除 `_create_defaults()` / `bootstrap_defaults()` ORM 写逻辑；
- 提供 `BOOTSTRAP_DATA` 元数据。

稳定键：

```text
AssessmentLevel.code
AssessmentSeries.code
AssessmentType.code
CompetitionRole.code
```

名称冲突继续作为 Preflight error，不通过 `--force` 改 stable code 或自动合并记录。

## 7.2 `feedback/bootstrap.py`

将 4 个分类改为具名字典，至少明确：

```text
code
name
description
default_private
order
is_active
```

删除 ORM 写逻辑。

## 7.3 `event_countdown/bootstrap.py`

改为具名字典，明确：

```text
code
name
description（若模型有）
order
is_active
```

不要继续依赖模型隐式默认作为 Force 的目标值。

## 7.4 `worldskills_forum/bootstrap.py`

四套默认数据全部改为具名字典。

特别修正：

- `ForumCategory` / `ForumModule` / `ForumSourceRole` 的 `sort_order` 必须显式写入；
- 不再使用 `enumerate()` 隐式决定人工目录排序；
- 所有 active / flag 字段明确写出。

稳定键使用现有 `slug` / `code`。

## 7.5 `behaviors/bootstrap.py`

这是本次最复杂的数据声明，但仍要保证文件可读。

四套数据：

```text
CONDUCT_SEVERITIES
CONDUCT_SEVERITY_RULES
CONDUCT_CATEGORIES
CONDUCT_ITEMS
```

全部 `list[dict]`。

关系只写：

```text
severity: "MINOR"
category: "attendance"
```

由 engine 按稳定 code 解析。

保留/迁移现有业务规则：

- 同性质分类名称冲突检测；
- 同分类事项名称冲突检测；
- category nature 等差异普通模式 SKIP、force 才恢复；
- 奖励/惩罚默认分值符号等业务校验不能因 Bootstrap 重构而失效；
- 默认 severity 切换按第 6.4 节处理。

## 7.6 `core/bootstrap.py`

保留人类可读：

```text
SITE_CONFIG_DEFAULTS
FLAT_PAGES
```

可以把 `SiteConfig` 的固定 `pk=1` 作为唯一例外，因为模型本身用数据库约束和 `save()` 明确规定这是单例主键，不是环境偶然 PK。

删除通用 ORM 编排；FlatPage Site 关系由小型 core adapter 处理。

## 7.7 `scoring/bootstrap.py`

不要复制 `PARSER_DEFINITIONS`。

改成 Registry → normalized Bootstrap records 的纯构造逻辑 + 必要 dataset metadata。

新增 Registry/DB 漂移 Preflight。

---

# 8. `bootstrap_tms` 命令重构

修改：

```text
core/management/commands/bootstrap_tms.py
```

## 8.1 `add_arguments()`

添加：

```text
--force
--dry-run
--yes
```

参数 help 使用中文并明确语义。

不要增加互相重复的 `--apply` / `--no-input`。

## 8.2 `handle()` 推荐结构

保持薄：

```text
解析参数
↓
build_bootstrap_plan(force=...)
↓
render_plan(...)
↓
ERROR? -> CommandError
↓
dry_run? -> return
↓
无 CREATE/UPDATE? -> return
↓
yes? 否则确认
↓
apply_bootstrap_plan(plan)
↓
输出执行摘要
```

不要把逐模型 ORM 细节塞回 command。

## 8.3 Django 命令输出

继续使用：

```text
self.stdout.write
self.stderr.write
self.style.SUCCESS/WARNING/ERROR
```

不要用裸 `print()`。

---

# 9. 文档规范同步

## 9.1 `AGENTS.md`

当前文字“Bootstrap 不会覆盖已存在记录的管理员修改”需要改成模式化规则：

- 默认模式不会覆盖；
- `--force` 是显式、可预览、需确认的恢复默认能力；
- Force 只覆盖声明字段，不删额外数据；
- Bootstrap 仍不得在 request / ready / signal 等隐式执行。

增加“默认数据声明优先 `list[dict]`、以人类可读为第一目标”的长期规则，但不要写成过度详细的实现文档。

## 9.2 ADR 0008

更新第 4/5 条和后果：

旧：

```text
只创建缺失，不覆盖管理员修改；主要新环境运行
```

新：

```text
默认模式只创建缺失；显式 --force 可在 Preview/Confirm 后恢复受管默认值；两种模式都不删除额外数据。
```

ADR 继续强调：

- 显式命令；
- 非启动同步器；
- 不替代 migration；
- Registry / Enum 边界不变。

## 9.3 `README.md`

更新“初始化默认业务目录”和生产部署说明。

至少给出：

```bash
uv run manage.py bootstrap_tms
uv run manage.py bootstrap_tms --dry-run
uv run manage.py bootstrap_tms --force
uv run manage.py bootstrap_tms --force --dry-run
```

明确：

- 正常执行会先预览并确认；
- 默认保留管理员修改；
- `--force` 用于明确需要恢复出厂值的场景，生产运行前应备份数据库；
- 不删除额外业务目录；
- 自动化可用 `--yes`。

## 9.4 旧实施 Plan

`docs/agents/plan/TMS-业务目录-Enum与Bootstrap全站治理实施Plan.md` 是历史执行计划，不要为了让它“看起来一致”大面积回写。

当前新 Plan 和更新后的 ADR/AGENTS/README 构成新的权威行为说明。

---

# 10. 测试计划

重点修改：

```text
core/test_bootstrap.py
scoring/test_bootstrap.py
```

必要时给复杂 APP 新增聚焦测试文件，不要把所有情况继续堆进一个超大测试。

## 10.1 Plan / Preview 测试

覆盖：

1. 空数据库计划正确识别 CREATE；
2. 已有完全相同 → UNCHANGED；
3. 已有字段不同：
   - 普通 → SKIP；
   - force → UPDATE；
4. 字段 Diff 正确列出 old/new；
5. Decimal / bool / FK 不产生假 Diff；
6. 声明重复 key → ERROR；
7. 名称/组合 collision → ERROR；
8. FK 自然键缺失 → ERROR；
9. Plan 阶段数据库零写入。

## 10.2 CLI 测试

覆盖：

1. 默认运行先输出 Preview，再读取确认；
2. 默认回答 No → 零写入；
3. 回答 Yes → 只 CREATE；
4. `--dry-run` → 不询问、零写入；
5. `--force --dry-run` → 显示 UPDATE、零写入；
6. `--yes` → 不读取输入但正常 Apply；
7. `--force` 不隐含 `--yes`；
8. Preflight ERROR → 不询问、不 Apply，并以 `CommandError` 失败；
9. EOF → 给出非交互环境可操作提示。

## 10.3 Force 行为测试

准备管理员修改：

- SiteConfig 名称；
- FlatPage 内容；
- AssessmentLevel/Type 名称、排序、active；
- FeedbackCategory.default_private；
- ForumPostType.is_official；
- CountdownEventType.is_active；
- ConductItem.default_score；
- ScoringParserConfig display_name / enabled / default。

断言：

- 普通模式全部保留；
- force 恢复所有 Bootstrap 受管字段；
- stable key 不变；
- PK 不变；
- 业务引用不丢失。

## 10.4 不删除额外数据

分别向至少两个普通目录和一个 Registry 配置场景增加额外记录。

断言：

- 普通模式不删；
- force 也不删；
- Registry 不存在实现的 parser key 按本 Plan 的 Preflight 规则报错，不由 Bootstrap 擅自删除。

## 10.5 FlatPage Site 关系

覆盖：

- 新建页会绑定当前 Site；
- 已存在但缺当前 Site：普通模式 Preview SKIP；
- force 补当前 Site；
- force 不移除其他 Site。

## 10.6 默认项唯一约束

### behaviors

先把默认 severity 人工切到非出厂项，然后 `--force`。

断言：

- 不出现条件唯一约束错误；
- 最终只有声明目标 `is_default=True`。

### scoring

同样测试 parser default 切换。

## 10.7 全局原子回滚

构造后段 Apply 失败：

- 前段有 CREATE/UPDATE；
- 后段故意触发模型/DB 校验错误。

断言整个 Bootstrap 的所有实际写入回滚。

## 10.8 stale plan 防覆盖

构造 Preview 后、Apply 前目标记录发生变化。

断言：

- Apply 检测 expected old values 不匹配；
- 整体失败并回滚；
- 不覆盖确认之后的新修改。

---

# 11. 验证命令

这是跨多个 APP 的公共初始化机制重构，验证范围可以高于普通局部修改。

先执行聚焦验证：

```bash
uv run pytest core/test_bootstrap.py scoring/test_bootstrap.py
```

根据实际拆分出的测试文件补充：

```bash
uv run pytest assessments feedback worldskills_forum event_countdown behaviors scoring -k bootstrap
```

然后：

```bash
uv run ruff check core assessments feedback worldskills_forum event_countdown behaviors scoring
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
```

由于本次是全站公共 Bootstrap 机制，聚焦测试通过后再执行：

```bash
uv run pytest
```

若全量测试存在与本次无关的既有失败，记录基线并只修复由本次改动导致的回归，不顺手扩大范围。

本次没有模板/Tailwind class 修改时，不需要机械执行 `npm run build:css`。

---

# 12. 手工验收场景

至少用本地 SQLite 或专用测试数据库执行以下流程。

## 场景 A：新库

```bash
uv run manage.py migrate
uv run manage.py bootstrap_tms --dry-run
uv run manage.py bootstrap_tms
```

确认 Preview 全部合理，输入 `y` 后创建。

再次：

```bash
uv run manage.py bootstrap_tms --dry-run
```

应主要为 `UNCHANGED`，无写入需求。

## 场景 B：管理员修改后普通 Bootstrap

后台修改若干目录名称、排序、active。

运行：

```bash
uv run manage.py bootstrap_tms
```

应显示 `SKIP` Diff，并且即便确认，也不能覆盖这些记录。

## 场景 C：测试环境强制恢复

```bash
uv run manage.py bootstrap_tms --force --dry-run
```

确认 Preview 显示 UPDATE。

然后：

```bash
uv run manage.py bootstrap_tms --force
```

确认后恢复声明默认值，但额外业务记录仍存在，PK 和引用不变化。

## 场景 D：自动化

```bash
uv run manage.py bootstrap_tms --force --yes
```

必须仍打印 Preview，然后自动 Apply。

---

# 13. 非目标

本次不要做：

- 不建立通用 Seed/Fixture 第三方框架；
- 不引入 YAML/JSON 作为默认业务数据主格式；
- 不做数据库全量同步；
- 不实现 `--prune` / 自动删除；
- 不实现 reset database；
- 不给每个 APP 做独立 management command；
- 不自动执行 Bootstrap 于 `migrate`、`post_migrate`、应用启动、request；
- 不把 Permission Bundle、导航、Enum、Parser 实现本身复制进业务目录；
- 不修改历史 migration；
- 不因为本次 Bootstrap 改造顺手重构 assessments/scoring/behaviors 的其他业务代码；
- 不做前端 UI。

---

# 14. 完成定义（Definition of Done）

只有满足以下全部条件才算完成：

- [ ] 各人工 Bootstrap 数据已改成清晰 `list[dict]`，不再以位置元组作为主要编辑格式；
- [ ] `AssessmentLevel` 已包含 world/national/provincial 默认声明；
- [ ] `AssessmentSeries` 已包含 worldskills 默认声明；
- [ ] `bootstrap.py` import 不访问数据库；
- [ ] 通用 ORM Plan/Diff/Apply 不再复制在各 APP；
- [ ] 默认模式有 Preview + Confirm；
- [ ] 默认模式 CREATE 缺失、SKIP 已修改；
- [ ] `--force` 可 UPDATE 已修改受管字段；
- [ ] `--force` 不删除数据库额外数据；
- [ ] `--force` 不改变 stable key、PK 或破坏引用；
- [ ] `--dry-run` 零写入；
- [ ] `--yes` 只跳确认、不跳 Preview/Validation；
- [ ] Preflight ERROR 在任何写入前被报告；
- [ ] 可预期配置错误以 `CommandError` 形式呈现；
- [ ] FlatPage 当前 Site 关系可被 Preview/Force 正确处理；
- [ ] scoring Registry/DB 漂移不再静默；
- [ ] behaviors/scoring 默认项 Force 切换不违反条件唯一约束；
- [ ] 全站 Apply 仍由一个外层 `transaction.atomic()` 保证；
- [ ] stale preview 不会盲目覆盖确认后的新数据变化；
- [ ] 普通模式保留管理员修改的旧测试仍成立；
- [ ] Force、dry-run、cancel、rollback、extra-data 测试齐全；
- [ ] `AGENTS.md`、ADR 0008、README 与新行为一致；
- [ ] `makemigrations --check --dry-run` 无新增 migration；
- [ ] 聚焦测试、Ruff、Django check 通过；
- [ ] 全量测试没有由本次改动引入的新失败。

---

# 15. 实施顺序建议

Codex 按以下顺序执行，避免边写边改语义：

1. 重新读取当前分支 HEAD、`AGENTS.md`、ADR 0008、现有 Bootstrap 与测试；
2. 先写/调整 engine 的 Plan 数据结构和纯只读 Diff 测试；
3. 把各 APP 默认数据逐步改成 `list[dict]`，保持行为暂不 Apply；
4. 实现 FK 自然键解析和 Preflight；
5. 实现 Preview renderer；
6. 实现普通 CREATE Apply；
7. 实现 Force UPDATE；
8. 处理 behaviors/scoring 默认项唯一约束专用 hook；
9. 处理 core FlatPage Site 专用 hook；
10. 重构 management command 参数、确认和错误边界；
11. 完善普通/force/dry-run/cancel/rollback/stale-plan 测试；
12. 更新 AGENTS、ADR 0008、README；
13. 执行验证命令；
14. 最终检查 `git diff`，确认没有无关业务重构、历史 migration 修改或前端构建噪声。

实现过程中如果发现某个具体模型无法适配上述通用 dataset 结构，优先增加**最小的模型专用 adapter/hook**，不要为了消灭一个特殊情况把 `bootstrap_engine.py` 扩展成通用 ORM 同步框架。
