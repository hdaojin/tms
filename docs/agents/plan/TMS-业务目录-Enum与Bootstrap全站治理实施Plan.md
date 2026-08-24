# TMS 业务目录、Enum 与 Bootstrap 全站治理实施 Plan

> **文档性质**：可供 Codex 直接执行的跨 APP 工程实施计划  
> **目标仓库**：`hdaojin/tms`  
> **目标分支**：`codex/assessment-refactor`  
> **编制日期**：2026-08-24  
> **基线说明**：编制前 `codex/assessment-refactor` 相对 `develop@ce0d5a86f18949f8945a1d77be5be4d7f229f5a7` 领先竞赛与考核重构提交；本 Plan 编制前已经在该分支更新 `AGENTS.md`，提交 `7fadcf0dd37f6f63c5d279aa844e6307dc1e3926`。执行时必须重新读取分支最新 HEAD，不得假定提交号仍未变化。  
> **实施性质**：跨 APP 模型、数据迁移、初始化机制和文档治理；必须保留现有生产数据，不重写已经存在的 migration history。

---

# 0. 执行契约

本 Plan 是一次明确要求的**全站治理任务**，允许跨 `core`、`assessments`、`feedback`、`worldskills_forum`、`event_countdown`、`behaviors`、`scoring` 以及相关 `accounts`、文档和测试进行必要修改，但不得借机扩展到无关业务重构。

执行过程中遵守以下已经确认的结论，不再重新讨论：

1. `AGENTS.md` 已正式确定以下长期规则：

   > **业务目录数据用 Model；程序状态和语义用 Enum。默认业务目录通过 Bootstrap 初始化。**
   >
   > **如果管理员合理地可以增加一个值，而程序无需因此增加代码，那么它就不应该是 `TextChoices`。**
   >
   > **如果增加一个值以后程序必须知道“这个值意味着什么、应该怎么处理”，它就应该继续是 Enum 或代码 Registry。**

2. 不建立全局泛型“字典表”“枚举表”“配置项表”。每个目录 Model 归属自己的业务 APP。
3. Django `auth.Group + GroupProfile` 已经是 TMS 的数据库角色体系；不得再建立平行的 `Role` Model 或 Role Enum。
4. `core/config/permission_bundles.yml` 是随代码版本发布的“业务能力 → Django Permission”目录，不数据库化。
5. Parser、倒计时主题等需要 Python 实现、模板、CSS、静态资源或外部协议支持的对象继续使用代码 Registry；数据库只保存可配置的启用/默认/显示信息。
6. `bootstrap_tms` 是**显式**的初始数据入口，不是启动钩子、`post_migrate` 自动同步器，也不是每次部署都会执行的“数据库校正器”。
7. Bootstrap 必须幂等：重复执行不得制造重复记录；已有记录的管理员修改不得被默认值覆盖；停用的数据不得被 Bootstrap 擅自重新启用。
8. 历史 `RunPython` migration 是迁移历史的一部分，必须保留。不得为了“统一 Bootstrap”回头修改已发布 migration。
9. Fixture 可以用于测试、演示或明确的数据交换，但生产安装不再依赖 `loaddata core/default behaviors/default` 作为默认业务数据权威来源。
10. 当前仓库没有明确权威默认值的目录，不得为了 Bootstrap 看起来“完整”而自行发明默认数据。特别是当前没有发现应强制预置的 `AssessmentSeries`、`AssessmentLevel` 或默认 Django Group 列表，这些模型允许初始为空。
11. 本次不做 UI 大改版，不重构导航信息架构，不引入新的前端框架，不改变 TMS 当前 Django 6 / HTMX / django-tables2 / Tailwind CSS 4 / DaisyUI 5 / Alpine.js / Iconify 技术栈。
12. 所有数据迁移优先保证 PostgreSQL 生产数据安全，同时必须可在项目测试使用的 SQLite 环境通过。

---

# 1. 本次治理的目标状态

完成后，全站配置边界必须稳定为：

```text
                        TMS 可选值 / 配置数据
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
        业务目录数据           程序语义值域          代码实现
             │                    │                    │
          Model                  Enum               Registry
             │                    │                    │
 code/name/order/active    status/source/role     parser/theme/
 以及业务专属属性          protocol/mode/...      permission bundle
             │                                         │
             └───────────┐                   ┌─────────┘
                         │                   │
                         ▼                   ▼
                    bootstrap_tms       代码随版本发布
                  只创建缺失默认数据       不由 DB 创造实现
```

最终要达到：

- 管理员可以合理扩展的目录，不再因为新增一个值而修改 Python `TextChoices`、生成 schema migration、重新部署；
- 程序必须理解的状态、协议、来源、结构角色继续明确留在代码；
- 默认业务目录只有一个显式 Bootstrap 入口；
- request / selector / 普通读取 service 不再暗中写数据库；
- 生产安装流程不再依赖多个 default fixture；
- 所有从字符串 choice 改成 FK 的历史数据安全迁移；
- URL/filter/query 参数尽量继续使用稳定 `code`，避免前端和收藏链接因 FK 主键变化而失去兼容性；
- 全仓以后可以用稳定的 review 规则判断新字段应该使用 Model、Enum 还是 Registry。

---

# 2. 执行前先重新审计分支

开始实现前执行：

```bash
git status --short
git branch --show-current
git log -3 --oneline
```

必须确认当前分支是：

```text
codex/assessment-refactor
```

不要覆盖用户未提交修改。

然后重新做一次生产代码扫描，确认自本 Plan 编制之后没有新增可配置 choice：

```bash
rg -n "TextChoices|IntegerChoices|choices=|_CHOICES|STATUS_CHOICES" \
  core accounts samba standards assessments training scoring evidence glossary \
  worldskills_forum feedback notes meetings notices behaviors event_countdown articles

rg -n "get_or_create|update_or_create|sync_.*config|loaddata|fixtures" \
  core accounts samba standards assessments training scoring evidence glossary \
  worldskills_forum feedback notes meetings notices behaviors event_countdown README.md docs

rg -n "complaint|official_reply|official_notice|rule_change|CONDUCT_SEVERITY|CONDUCT_NATURE" \
  feedback worldskills_forum behaviors core static
```

如果发现本 Plan 未覆盖、但明显符合新规范的新增代码：

- 先按 `AGENTS.md` 的 Model / Enum / Registry 判定原则归类；
- 只把真正属于本次治理范围的项纳入；
- 在最终交付说明中列出新增发现；
- 不因为扫描到无关常量而顺手扩大重构。

`demo` 为 DEBUG-only 组件演示 APP，不要求把纯演示 choice 纳入生产目录治理，除非其代码被生产 APP 复用。

---

# 3. 全站最终分类表

## 3.1 必须改成「Model + Bootstrap」或补齐 Bootstrap 的业务目录

| APP | 当前对象 | 目标 | Bootstrap 默认数据 |
| --- | --- | --- | --- |
| `core` | `SiteConfig` 已是 Model，但 `get_solo()` 隐式创建 | 保留单例 Model，移除读取时写库 | 当前 `core/default` 中 SiteConfig 默认值 |
| `core` | `/about/site/`、`/about/author/` FlatPage fixture | 保留 FlatPage Model，Bootstrap 初始化 | 当前 fixture 两页 |
| `assessments` | `Assessment.Type` TextChoices | 新建 `AssessmentType` Model，`Assessment.assessment_type` 改 FK | 现有 7 个类型 |
| `assessments` | `CompetitionRole` 已是 Model，默认角色写在 migration | 保留 Model，默认角色纳入当前 Bootstrap 权威定义 | 当前 13 个角色 seed |
| `assessments` | `AssessmentSeries` | 保留 Model | **当前不预置，禁止自行发明** |
| `assessments` | `AssessmentLevel` | 保留 Model | **当前不预置，禁止自行发明** |
| `feedback` | `FeedbackCategory` TextChoices | 新建 `FeedbackCategory` Model | bug / feature / suggestion / complaint |
| `worldskills_forum` | `ForumCategory` 已是 Model，默认值只在历史 migration | 保留 Model，纳入 Bootstrap | 当前 7 个默认分类 |
| `worldskills_forum` | `ForumModule` 已是 Model | 保留 Model，纳入 Bootstrap | 综合、A-D、其他 |
| `worldskills_forum` | `ForumSourceRole` 已是 Model | 保留 Model，纳入 Bootstrap | 当前 6 个来源身份 |
| `worldskills_forum` | `PostType` TextChoices | 新建 `ForumPostType` Model | 当前 5 个信息类型 |
| `event_countdown` | `CountdownEvent.EventType` TextChoices | 新建 `CountdownEventType` Model | 当前 9 个事件类型 |
| `behaviors` | 严重程度 code/label 写死、系数在 DB | 新建 `ConductSeverity` Model；`ConductSeverityRule` 关联它 | 4 个 severity + 2×4 条规则 |
| `behaviors` | `ConductCategory` / `ConductItem` 已是 Model，默认值在 fixture | 补稳定 code，Bootstrap 初始化 | 当前 2 分类 + 7 事项 |
| `scoring` | `ScoringParserConfig` 已是 Model，但读取路径会自动同步 | 保留 Model；仅 Bootstrap 创建缺失 Registry 配置 | 当前 `PARSER_DEFINITIONS` 中实现 |

## 3.2 必须继续留在 Enum / `TextChoices` 的程序语义

以下值域不要数据库化：

### `accounts`

- `UserProfile.Gender`

### `assessments`

- `CompetitionRole.Category`
- `Assessment.Status`
- `AssessmentModuleDomain.Role`
- `AssessmentModuleCoach.Role`
- `AssessmentFinalScore.ScoreType`
- `AssessmentAward.Category`
- `AssessmentDocument.DocumentType`

### `training`

- `TrainingCycle.Status`
- `TrainingCycleMember.Role`
- `TrainingPlan.Status`
- `TrainingTask.Priority`
- `TrainingTask.Status`
- `TrainingTaskDomain.Role`
- `TrainingTaskSkill.Role`
- `TrainingTaskCoach.Role`
- `TaskExecution.Status`

### `scoring`

- `ScoringSchemeImport.Status`
- `ScoringAspect.AspectType`
- `ScoringResult.Source`

### `evidence`

- `KnowledgeEvidence.SourceType`
- `KnowledgeEvidence.ExtractionSource`
- `KnowledgeEvidence.ReviewStatus`
- `EvidenceSkillMap.MappingSource`

### `standards`

- `SkillTerm.Kind`

### `glossary`

- `GlossaryEntry.Source`
- `GlossaryEntryProposal.Status`
- `GlossaryImport.Status`
- `StudySession.Mode`
- `StudySession.Status`
- `StudyAttempt.Direction`

### `articles`

- `Article.Status`

### `feedback`

- `FeedbackStatus`

### `worldskills_forum`

- `Importance`
- `TopicStatus`
- `AttachmentKind`

### `behaviors`

- 奖励 / 惩罚性质：改为 `ConductNature(models.TextChoices)`，但继续是 Enum
- `ConductRecord.Status`：把旧式 `STATUS_CHOICES` 收敛为 `TextChoices`，值保持兼容

### `samba`

- `SambaOperation.Action`
- `SambaOperation.Status`

这些值新增后都需要程序同步理解其状态流转、校验、算法、审计或协议语义，因此不得开放为任意后台目录。

## 3.3 必须继续留在代码 Registry / 版本化配置的对象

- `scoring/registry.py` 的 `PARSER_DEFINITIONS`
- `event_countdown/themes.py` 的 `COUNTDOWN_THEMES` / 由 Registry 派生的主题 choices
- `core/config/permission_bundles.yml`
- `core/config/navigation.yml`
- 上传格式、大小、路径、安全扩展名、缓存/超时等技术常量

允许 Registry 对应数据库运行时配置，但数据库只能引用 Registry 中存在的稳定 key，不能创建 Python 实现不存在的新 parser/theme。

## 3.4 已正确是 Model、但不需要默认 Bootstrap 的业务数据

例如：

- `SkillProject`
- `TechnicalDomain`
- `Skill`
- `SkillTreeVersion`
- `WSOSVersion` / `WSOSSection`
- `ProfessionalGlossary`
- `Article.Category` / `Tag`
- `ForumTag`
- `AssessmentAward`
- `CompetitionPerson`
- `NoteRepo`

“应该用 Model”不等于“每个安装都必须预置记录”。这些内容继续由真实业务创建。

---

# 4. 建立统一 Bootstrap 架构

## 4.1 新增统一管理命令

新增：

```text
core/management/__init__.py
core/management/commands/__init__.py
core/management/commands/bootstrap_tms.py
```

如果目录已存在则复用，不重复创建。

建议每个拥有默认目录的 APP 自己维护 bootstrap 函数：

```text
core/bootstrap.py
assessments/bootstrap.py
feedback/bootstrap.py
worldskills_forum/bootstrap.py
behaviors/bootstrap.py
event_countdown/bootstrap.py
scoring/bootstrap.py
```

`bootstrap_tms` 显式按固定顺序调用，不做动态 AppConfig 自动发现：

```text
core
assessments
feedback
worldskills_forum
behaviors
event_countdown
scoring
```

原因：

- 初始化依赖关系清楚；
- review 时能直接看到 Bootstrap 的全站范围；
- 不建立新的隐式 plugin/registry 机制；
- 失败位置和测试更明确。

## 4.2 命令行为

管理命令要求：

- 继承 Django `BaseCommand`；
- `requires_migrations_checks = True`；
- 使用 `self.stdout.write()` / `self.style.SUCCESS()` 输出结果，不直接 `print()`；
- 整个 Bootstrap 使用 `transaction.atomic()`；任何 APP 初始化失败时整次回滚；
- 输出每个 APP 的 `created / existing` 简要统计；
- 不要求交互确认；
- 不接受“force sync all defaults”之类会覆盖管理员修改的参数；
- 可以安全重复运行。

## 4.3 Bootstrap 的写入规则

默认：

```python
obj, created = Model.objects.get_or_create(
    code=stable_code,
    defaults={...},
)
```

禁止普通 Bootstrap：

```python
update_or_create(... defaults=canonical_defaults)
```

去覆盖管理员已经修改的名称、排序、启用状态、说明、系数等。

对于多字段稳定键，例如旧 `ForumCategory` 使用唯一 `slug`，Bootstrap 使用其现有稳定 `slug`。

如果现有记录已经存在：

- 不改 `name`；
- 不改 `description`；
- 不改 `order`；
- 不改 `is_active`；
- 不恢复被管理员停用的记录；
- 不替换管理员选择的默认 parser。

## 4.4 禁止隐式 Bootstrap

最终代码中不得出现：

- context processor 读取 SiteConfig 时 `get_or_create()`；
- selector 为了查询目录而自动创建目录；
- `enabled_parser_configs()` 为了读取 parser 而写数据库；
- `AppConfig.ready()` 自动补种子；
- `post_migrate` 自动反复同步业务目录；
- signal 因读取/保存普通业务对象而补建目录行。

注意：像 `ensure_group_profile(group)` 这种**给一个已经明确存在的 Group 补自己的 OneToOne 扩展记录**不是“默认业务目录 seed”，可以继续保留；不要机械删除所有 `get_or_create()`。

---

# 5. Bootstrap 当前明确的默认数据

以下定义是**当前版本 Bootstrap 的权威出厂默认**。历史 migration 中相同定义继续保持历史快照，不从 Bootstrap import。

## 5.1 `core`

### SiteConfig

按当前 fixture / 现有 `get_solo()` 的默认内容创建 `pk=1`，至少保持：

```text
site_name: Training management system
site_short_name: TMS
site_description: A training management system for skill competitions.
site_keywords: training, management, skills, competitions
site_author: hdaojin
site_copyright: TMS 版权所有
```

其他未指定字段保持模型空值/default。

`default_registration_group` 保持空，不自行创建默认 Group。

### FlatPage

按 URL `get_or_create`：

```text
/about/site/
/about/author/
```

仅创建时写入当前 fixture 的 title/content，并关联 `settings.SITE_ID` 对应 Site。

重复 Bootstrap 不覆盖管理员修改后的页面内容。

## 5.2 `assessments.AssessmentType`

```text
competition          正式竞赛
selection            选拔赛
exchange             交流赛
mock                 模拟赛
training_assessment  训练考核
training_test        训练测试
other                其他
```

给出稳定 `order`，保持现有列表语义即可。

## 5.3 `assessments.CompetitionRole`

Bootstrap 当前 13 个默认角色：

```text
project_manager             项目经理        official
skill_competition_manager   技能竞赛经理    official
venue_manager               场地经理        official
team_leader                 领队            official
chief_expert                专家组长        expert
deputy_chief_expert         副专家组长      expert
expert                      专家            expert
judge                       裁判            expert
coach                       教练            coach
competitor                  选手            competitor
staff                       工作人员        staff
observer                    观察员          other
other                       其他            other
```

顺序保持现有 migration 的 10/20/.../120/999。

不要修改 `CompetitionRole.Category` Enum。

## 5.4 `feedback.FeedbackCategory`

```text
bug         Bug反馈     default_private=False
feature     功能需求    default_private=False
suggestion  意见建议    default_private=False
complaint   我要投诉    default_private=True
```

## 5.5 `worldskills_forum`

### ForumCategory

按现有历史 seed：

```text
official        官方发布
technical       技术讨论
rules           竞赛规则
marking         评分
environment     竞赛环境
infrastructure  基础设施
other           其他
```

这里使用现有 `slug` 作为稳定键。

### ForumModule

```text
general   综合
module-a  模块 A
module-b  模块 B
module-c  模块 C
module-d  模块 D
other     其他
```

### ForumSourceRole

```text
worldskills_official  世界技能组织官方  is_official=True   allows_detail=False
chief_expert          首席专家          False              False
deputy_chief_expert   副首席专家        False              False
expert                专家              False              False
organizer             竞赛组织方        False              False
other                 其他              False              True
```

### ForumPostType

```text
discussion          专家讨论   is_official=False
official_reply      官方回复   is_official=True
official_notice     官方通知   is_official=True
rule_change         规则变更   is_official=True
important_reminder  重要提醒   is_official=False
```

`rule_change` 设置为 official 是为了保持当前 selector 中“官方视图”的已有语义。

## 5.6 `event_countdown.CountdownEventType`

```text
worldskills  世界技能大赛
national     全国技能大赛
provincial   省级技能大赛
municipal    市级技能大赛
school       校内比赛
training     集训活动
exam         考核测评
meeting      会议活动
other        其他活动
```

## 5.7 `behaviors`

### ConductSeverity

```text
MINOR     轻微
MODERATE  一般
SEVERE    严重
CRITICAL  特别严重
```

### ConductSeverityRule

奖励 `REWARD`：

```text
MINOR     鼓励      ×0.00
MODERATE  表扬      ×1.00   default
SEVERE    嘉奖      ×2.00
CRITICAL  特别嘉奖  ×3.00
```

惩罚 `PENALTY`：

```text
MINOR     轻微      ×0.00
MODERATE  一般      ×1.00   default
SEVERE    严重      ×2.00
CRITICAL  特别严重  ×3.00
```

### ConductCategory

为现有默认分类补稳定 code：

```text
attendance         PENALTY  考勤
competition_award  REWARD   竞赛获奖
```

### ConductItem

为当前默认事项补稳定 code，`code` 在 category 内唯一：

```text
attendance / late          迟到    -1.00
attendance / early_leave   早退    -1.00
attendance / absence       旷课    -5.00

competition_award / municipal   市级    +1.00
competition_award / provincial  省级    +5.00
competition_award / national    国家级  +10.00
competition_award / world       世界级  +20.00
```

Bootstrap 只创建缺失项，不覆盖管理员后来调整的默认分值。

## 5.8 `scoring.ScoringParserConfig`

Bootstrap 从当前 `PARSER_DEFINITIONS` 遍历代码实现，按 `parser_key` 创建缺失配置。

当前至少包含：

```text
cmp_single_module_v1
```

创建时可使用 Registry 的 display_name / alias / description，首次安装将 `default_parser_key()` 对应配置设置为默认、启用。

如果数据库已有任意配置：

- 不覆盖其显示字段；
- 不重新启用；
- 不重置 default；
- 不因 Registry 默认值变化而改写管理员配置。

---

# 6. 通用 Catalog Model 设计约束

新目录 Model 不共享全局基类到必须继承的程度。字段相似不代表要建立抽象复杂度；直接在各 APP 使用清晰字段即可。

建议通用形态：

```python
code = models.SlugField(..., unique=True)  # 或现有可表达稳定 code 的 CharField
name = models.CharField(...)
description = models.TextField(blank=True)
order = models.PositiveIntegerField(default=0)
is_active = models.BooleanField(default=True)
created_at = ...  # 与该 APP 现有风格一致时添加
updated_at = ...
```

具体要求：

1. `code` 是机器身份，不是展示文案。
2. 新建后原则上不允许普通管理员修改 `code`；Admin 可通过 `get_readonly_fields()` 在已有对象上设为只读，或在 Model/Form 校验修改。
3. `name` 可改。
4. `is_active=False` 表示“不再用于新业务选择”，不是删除历史。
5. 历史对象 FK 优先 `PROTECT`。
6. 下拉框新建时默认只显示 `is_active=True`；编辑已有对象时必须额外包含当前被引用的 inactive 行。
7. 排序优先：`order, code/name`，保持稳定。
8. 不把数据库 PK 暴露成跨系统或 URL 的稳定业务标识；现有 filter 参数可继续使用 `code`。

---

# 7. 通用 choice → FK 数据迁移模板

所有现有字符串 choice 转 FK 时都按安全的多阶段 migration 实施，不允许直接删字符串字段再“重建默认数据”。

推荐顺序：

1. 创建 Catalog Model。
2. 给业务模型新增 nullable 临时 FK，例如：

   ```text
   category_config
   event_type_config
   post_type_config
   severity_config
   assessment_type_config
   ```

3. 新建单独的数据 migration：
   - 使用 `apps.get_model()` 获取历史模型；
   - 按**迁移文件自己的常量快照**创建当前合法 choice 对应目录行；
   - 遍历旧字段 distinct 值并映射；
   - 如果生产历史数据出现当前代码之外的旧字符串，保留它：创建稳定的 historical code/name 行并设 inactive，不得丢数据；
   - 映射后断言不存在空 FK。
4. schema migration 删除旧字符串字段。
5. 将临时 FK rename 回原业务字段名。
6. 调整为非空、`on_delete=PROTECT` 等最终约束。
7. 如果 reverse migration 可以可靠恢复原 code，则提供反向函数；无法完全反向的结构要在 migration test 中明确边界。

历史数据迁移**禁止**：

```python
from app.bootstrap import DEFAULTS
from app.models import CurrentModel
```

因为未来 Bootstrap 定义变化不能改变历史 migration 的含义。

需要为 `AssessmentType`、`FeedbackCategory`、`ForumPostType`、`CountdownEventType`、`ConductSeverity` 分别添加 migration executor 测试，验证至少一条旧数据升级后 code/关系保持不变。

---

# 8. Phase 1：Core Bootstrap 与 SiteConfig 收口

## 8.1 改造 `SiteConfig.get_solo()`

当前 `get_solo()` 在读取路径使用 `get_or_create(pk=1, defaults=...)`，而 context processor 每个页面都调用它。这意味着“读取页面”可以隐式写数据库，必须移除。

目标：

- `get_solo()` 只读数据库和缓存；
- Bootstrap 负责真正创建 `pk=1`；
- 如果极端情况下未执行 Bootstrap，模板渲染不要因为没有 SiteConfig 立即崩溃，但 fallback 不得保存数据库。

实现建议：

- 查询 `pk=1`；
- 找到则缓存并返回；
- 找不到时返回一个未保存的 `SiteConfig(...)` 内存对象，至少提供站点名称/简称等安全展示 fallback；
- 不缓存“缺失”状态过长，避免刚执行 Bootstrap 后仍长期显示 fallback；
- 不调用 `.save()` / `get_or_create()`。

`SiteConfig.save/delete` 的缓存失效继续保留。

## 8.2 Bootstrap SiteConfig / FlatPage

新增 `core/bootstrap.py`。

FlatPage 创建时关联 Django Site：

```python
site = Site.objects.get(pk=settings.SITE_ID)
```

仅新建 page 时设置 site relation；重复运行不重写管理员已经维护的 relation/content。

## 8.3 Fixture 收口

在 Bootstrap 和 README 完成后：

- 移除生产初始化对 `core/fixtures/core/default.yaml` 的依赖；
- 如果没有测试或显式演示用途，删除该 default fixture；
- 如果保留 fixture 必须重命名/说明其用途，避免与 Bootstrap 形成第二权威来源。

不得修改历史 migration 来替代这一步。

## 8.4 测试

覆盖：

- `SiteConfig.get_solo()` 在 DB 缺失时不产生 INSERT；
- Bootstrap 后 `get_solo()` 返回持久对象；
- Bootstrap 重复执行不覆盖管理员修改的 site_name；
- FlatPage 重复 Bootstrap 不覆盖管理员修改内容。

---

# 9. Phase 2：Assessments 目录治理

## 9.1 新增 `AssessmentType`

建议：

```text
code       unique
name
description
order
is_active
created_at / updated_at（与 Series/Level 风格一致）
```

`Assessment.assessment_type` 最终改为：

```python
models.ForeignKey(
    AssessmentType,
    on_delete=models.PROTECT,
    related_name="assessments",
    verbose_name="类型",
)
```

不要改字段业务名 `assessment_type`，避免无意义的调用链修改。

## 9.2 迁移现有 Assessment

完整迁移现有 7 个字符串 code。

所有 view/form/table/filter/template 检查：

- `get_assessment_type_display()` → `assessment_type.name`；
- `assessment_type == Assessment.Type.X` 的逻辑必须检查是否真的存在机器语义依赖。

本轮预期 Assessment Type 只是目录分类；如果搜索到某处确实按某一类型改变程序算法，先判断是否应该把该机器语义独立为另一个 Enum/属性，而不是保留整个业务目录 TextChoices。

筛选参数如果当前使用：

```text
?assessment_type=competition
```

继续保持 code 语义，queryset 改成：

```text
assessment_type__code=...
```

## 9.3 CompetitionRole Bootstrap

保留现有 `CompetitionRole.Category` Enum。

现有 `0002_competition_people_roles_and_assessment_times.py` 的 seed/migration 继续原样保留，因为它承担旧库升级职责。

新增当前 Bootstrap 默认角色定义，供：

- 新环境在 current migrations 后初始化；
- 显式修复缺失的默认角色。

Bootstrap 使用 `code`；已有角色不覆盖 category/name/order/is_active。

## 9.4 Series / Level 不发明默认数据

`AssessmentSeries` / `AssessmentLevel` 已经正确是 Model。

本轮只保证：

- 表单新建对象时只列 active 值（如果当前逻辑尚未这样做）；
- 编辑历史 Assessment 时仍可显示当前 inactive 的 series/level；
- 后台可以维护；
- 不建立未经确认的 `WSC / national / provincial` 等默认行。

## 9.5 Admin / 权限

注册 `AssessmentType`。

Admin 至少提供：

- `list_display`: code/name/order/is_active；
- `list_filter`: is_active；
- `search_fields`: code/name；
- 已存在对象 code readonly。

不要为了新目录建立一套新的前台管理中心。若当前 `AssessmentSeries/Level` 只由 Django Admin 管理，`AssessmentType` 保持一致即可。

不要为此重做业务 Permission 架构；Django 默认 model permissions 足够，除非现有目录维护入口明确需要加入某个已有 permission bundle，再做最小一致性调整。

---

# 10. Phase 3：FeedbackCategory 模型化

## 10.1 新增模型

建议：

```text
code
name
description
order
is_active
default_private
created_at
updated_at
```

`Feedback.category` 改 FK `PROTECT`。

Bootstrap 当前四类保持原有 code。

## 10.2 保持筛选/URL 兼容

如果列表页过滤当前使用：

```text
category=bug
```

保持该参数，查询改成：

```text
category__code="bug"
```

表格展示改为 `category.name`。

## 10.3 移除 `complaint` 前端硬编码

当前 `static/js/alpine-components.js` 中：

```javascript
this.$refs.category.value === "complaint"
```

必须删除。

新行为由数据库的 `default_private` 驱动。

实现时可以：

- Form 将当前可选分类的 `pk -> default_private` 映射作为安全 `data-*` 信息输出；
- Alpine 根据当前 option value 查询对应 flag；
- 或给每个 option 输出 `data-default-private` 并读取 selected option；

但不得再次硬编码 `complaint` code。

保持现有交互语义：只有用户尚未主动改过私密 checkbox 时，切换到默认私密分类才自动勾选；用户手动决定优先。

不要动态拼 Tailwind class。

## 10.4 Form / Admin

- 新建只显示 active category；
- 如果编辑历史 Feedback，其当前 inactive category 仍可保留；
- 分类 code 创建后只读；
- 管理后台可改名称、排序、停用、默认私密。

`FeedbackStatus` 保持 Enum，继续由服务器端强制“已解决/已关闭必须填写处理结果”。

---

# 11. Phase 4：WorldSkills Forum 目录继续收口

## 11.1 保留现有三个数据库目录

保持：

- `ForumCategory`
- `ForumModule`
- `ForumSourceRole`

历史 `0002/0003/0004` data migration 不修改。

为 current Bootstrap 写入当前默认定义，但不覆盖已有编辑。

## 11.2 `PostType` → `ForumPostType`

新模型建议：

```text
code
name
description
order
is_active
is_official
created_at
updated_at
```

`ForumPost.post_type` 改 FK `PROTECT`。

现有 5 个 type 迁移，`rule_change` / official reply / official notice 的 `is_official=True` 保持现有业务筛选语义。

## 11.3 重构 selector

当前 official 视图类似：

```text
source_role.is_official
OR post_type in [OFFICIAL_REPLY, OFFICIAL_NOTICE, RULE_CHANGE]
```

改为：

```text
Q(source_role__is_official=True) | Q(post_type__is_official=True)
```

当前过滤参数：

```text
post_type=<code>
```

继续保留，lookup 改 `post_type__code`。

所有模板/表单的 `PostType.choices` 改 active queryset。

## 11.4 权限包最小同步

`worldskills_forum.manage_forum` 当前已经负责管理 ForumCategory / Module / SourceRole / Tag。

把 `ForumPostType` 的 `view/add/change` 权限加入这个**已有**管理权限包，使新增目录与同类目录维护能力一致。

不要因此建立新的权限包或扩大普通翻译人员权限。

更新相应权限包测试。

---

# 12. Phase 5：CountdownEventType 模型化，Theme 继续 Registry

## 12.1 新增 `CountdownEventType`

建议字段：

```text
code
name
description
order
is_active
```

`CountdownEvent.event_type` 改 FK `PROTECT`，迁移现有 9 个 code。

Bootstrap 创建当前 9 个默认项。

## 12.2 Theme 不动到数据库目录

`event_countdown/themes.py` 中主题 Registry 明确依赖：

- `body_class`
- 背景图片；
- 字体 token；
- Iconify 图标；
- 模板展示；
- 静态资源。

因此继续保留 `COUNTDOWN_THEMES` / `THEME_CHOICES`。

这是一种**允许存在的 code-derived choices**，不应为了形式统一改成 Theme Model。

## 12.3 不复用 AssessmentType

`CountdownEventType` 与 `AssessmentType` 分属不同业务语义：

- Countdown 可包含会议、集训等；
- Assessment Type 表示竞赛/考核性质。

不要为了“少一张表”做跨 APP 泛化。

---

# 13. Phase 6：Behaviors 彻底结束“半 Enum / 半 DB”

这是本轮相对复杂的一段，必须做数据迁移测试。

## 13.1 `ConductNature` 留在 Enum，但归还 `behaviors`

把当前 `core/constants.py` 中行为领域相关：

```text
CONDUCT_NATURE_REWARD
CONDUCT_NATURE_PENALTY
CONDUCT_NATURE_CHOICES
```

收敛为 `behaviors` 自己的：

```python
class ConductNature(models.TextChoices):
    REWARD = "REWARD", "奖励"
    PENALTY = "PENALTY", "惩罚"
```

可放在 `behaviors/models.py` 顶层或 `behaviors/enums.py`；优先最简单且不制造循环依赖的方案。

`ConductCategory.nature`、`ConductSeverityRule.nature` 等继续使用该 Enum。

不能数据库化 Nature，因为正/负分值验证明确依赖其机器语义。

## 13.2 新增 `ConductSeverity`

建议：

```text
code unique
name
description
is_active
created_at/updated_at（与 APP 风格一致）
```

不要把 multiplier 放到 `ConductSeverity`，因为 multiplier/显示文案是按 Nature 的规则。

## 13.3 重构 `ConductSeverityRule`

目标字段：

```text
nature          ConductNature Enum
severity        FK -> ConductSeverity (PROTECT)
label           当前 nature 下的显示名称
multiplier
order
is_default
```

约束：

- Unique `(nature, severity)`；
- 每个 nature 最多一个 `is_default=True`；
- default rule 对应 severity 必须 active；
- multiplier >= 0；
- 不强制奖励/惩罚使用相同 multiplier。

由 Rule 提供最终下拉文案，例如：

```text
表扬（×1.00）
一般（×1.00）
```

删除当前 Python 中按 Nature 维护的一系列 severity 中文映射字典。

## 13.4 `ConductRecord.severity` 改 FK

按通用 migration 模板安全迁移：

```text
MINOR / MODERATE / SEVERE / CRITICAL
```

现有记录不得丢失。

`ConductRecord.clean()` 改为验证：

- 当前 item.category.nature 下存在对应 severity rule；
- 得分仍由 item.default_score × rule.multiplier 计算。

显示名称通过该 Nature 下的 Rule label，而不是硬编码 Python dict。

## 13.5 默认 Severity 不再硬编码 MODERATE

当前 Form/View 直接依赖 `CONDUCT_SEVERITY_MODERATE`。

改为：

- 根据所选 item 的 Nature 查询 `ConductSeverityRule(is_default=True)`；
- HTMX 返回下拉时由 DB rule 决定 selected；
- 如果没有 default rule，选择列表可正常显示但不擅自猜测；必要时给出明确配置错误。

## 13.6 `ConductRecord.Status` 收敛为 `TextChoices`

将旧式：

```text
STATUS_PENDING
STATUS_APPROVED
STATUS_REJECTED
STATUS_CHOICES
```

重构为嵌套 `Status(models.TextChoices)`，保持数据库字符串完全不变：

```text
PENDING
APPROVED
REJECTED
```

这只是代码结构治理，不改变业务语义。

## 13.7 给 Category / Item 增加稳定 code

当前 fixture 用 PK/name 隐式标识默认分类和事项，不适合作为 Bootstrap 稳定键。

增加：

```text
ConductCategory.code
ConductItem.code
```

约束：

- `ConductCategory.code` 唯一；
- `ConductItem` Unique `(category, code)`；
- code 创建后原则上只读。

数据迁移：

- 精确匹配当前已知默认行时写本 Plan 的稳定 code；
- 其他管理员自定义历史行生成确定性 legacy code，例如基于主键的 `legacy-category-<pk>` / `legacy-item-<pk>`，但不得修改其 name/nature/score；
- 迁移完成后字段设为非空。

Bootstrap 随后只使用稳定 code，不按中文 name 猜已有行。

## 13.8 迁移 behaviors fixture

把 `behaviors/fixtures/behaviors/default.yaml` 的出厂分类/事项移入 `behaviors/bootstrap.py`。

README 不再要求 `loaddata behaviors/default`。

如果 fixture 没有测试/演示用途则删除；不要留两套生产默认数据源。

---

# 14. Phase 7：Scoring Parser Config 去掉“读取时自动同步”

## 14.1 保留 Parser Registry

`scoring/registry.py` 保持：

```text
ParserDefinition
PARSER_DEFINITIONS
default_parser_key()
```

Python parser 实现仍然由代码版本控制。

## 14.2 删除读取路径的 DB 写操作

当前：

```text
enabled_parser_configs()
  -> sync_parser_configs()
  -> get_or_create / 改 default / 重新启用
```

以及：

```text
default_parser_config()
  -> sync_parser_configs()
```

必须改掉。

目标：

```python
def enabled_parser_configs():
    return ScoringParserConfig.objects.filter(is_enabled=True)...
```

```python
def default_parser_config():
    return configured default or first enabled or None
```

只读函数不写数据库。

如果没有配置：

- UI 给维护者明确提示“请先执行 bootstrap_tms / 配置评分解析器”；
- 不在请求中偷偷创建。

## 14.3 Bootstrap parser config

`scoring/bootstrap.py` 当前可以读取 `PARSER_DEFINITIONS`，因为它是“当前版本显式初始化”，不是历史 migration。

创建缺失 parser config：

- `parser_key` 作为稳定键；
- 只有创建时使用 Registry display/alias/description；
- 首次空库可把 `default_parser_key()` 对应项设为默认；
- 如果数据库已有 parser rows，不调整管理员的 default/enable 状态。

特别测试：

1. 管理员停用 `cmp_single_module_v1`；
2. 调用 `enabled_parser_configs()`；
3. 不得自动重新启用；
4. 重复 Bootstrap 也不得重新启用已经存在的 row。

`ScoringParserConfig.clean()` 继续拒绝 `parser_key` 不在 Registry 的配置。

---

# 15. Phase 8：Accounts / 角色只做边界确认，不发明默认角色

本轮检查 `accounts`，但原则上不新增业务模型。

保持：

```text
auth.User
  └── UserProfile

auth.Group
  └── GroupProfile
```

保持：

```text
core/config/permission_bundles.yml
```

作为代码能力目录。

## 15.1 不建立 `Role` Enum / Model

“项目负责人、教练、选手、翻译人员”等如果作为系统授权角色，应继续由 Group + Permission Bundle + TechnicalDomain Scope 组合表达。

## 15.2 当前 Bootstrap 不创建默认 Group

仓库现有权威文档说明管理员自行建立代表业务角色的用户组，并选择权限包；没有发现唯一、稳定、必须存在的默认 Group 清单。

因此当前 `bootstrap_tms`：

- 不创建 coach / competitor / translator / admin 等 Group；
- 不猜这些 Group 应包含哪些 bundle；
- `SiteConfig.default_registration_group` 保持空。

未来如果业务明确确认默认角色模板，可以单独增加有依据的 Bootstrap 定义，不应在本轮自行决定。

## 15.3 `ensure_group_profile()` 不算 seed

`ensure_group_profile(group)` 为已经存在的 Group 补 OneToOne profile，属于实体完整性操作，可以继续使用 `get_or_create()`。

不要把“禁止隐式业务 seed”误解成“全仓禁止 get_or_create”。

---

# 16. Phase 9：全仓清理硬编码和旧 API

完成模型迁移后，再做一次针对性扫描。

## 16.1 必须消失的旧定义

生产代码中不应再存在：

```text
Assessment.Type
FeedbackCategory(TextChoices)
PostType(TextChoices)
CountdownEvent.EventType
CONDUCT_SEVERITY_CHOICES
CONDUCT_REWARD_SEVERITY_NAMES
CONDUCT_PENALTY_SEVERITY_NAMES
CONDUCT_SEVERITY_MODERATE 作为 UI 默认来源
SiteConfig.get_solo() 中 get_or_create
scoring 读取路径 sync_parser_configs()
```

如果为了 migration 历史在旧 migration 文件里出现，允许保留。

## 16.2 检查 `get_*_display()`

涉及改 FK 的字段：

```text
assessment_type
feedback.category
forum post_type
countdown event_type
conduct severity
```

所有旧 `get_xxx_display()` 使用点改成目录关系展示。

## 16.3 检查查询字符串硬编码

保持兼容的地方使用稳定 code：

```text
assessment_type__code
category__code
post_type__code
event_type__code
severity__code
```

不要用目录 PK 作为长期筛选值。

## 16.4 检查活跃目录查询

新建表单：active only。

编辑历史对象：

```text
active rows OR current row
```

防止停用目录后旧对象无法打开表单保存其他字段。

---

# 17. Phase 10：README、用户文档和规范同步

## 17.1 README 初始化流程

把当前：

```bash
uv run manage.py migrate
uv run manage.py loaddata core/default behaviors/default
uv run manage.py createsuperuser
```

改为：

```bash
uv run manage.py migrate
uv run manage.py bootstrap_tms
uv run manage.py createsuperuser
```

补一句：

- `bootstrap_tms` 用于全新环境或管理员明确需要补齐缺失出厂目录时显式执行；
- 普通应用启动和每次部署不会自动运行；
- 重复运行不会覆盖已有目录项的管理员修改。

部署文档中如存在 `loaddata core/default behaviors/default` 同步修改。

## 17.2 `AGENTS.md`

本 Plan 编制前已经加入 Model / Enum / Registry / Bootstrap 规范。

实施结束只检查是否需要根据最终实现微调文字，不要重复增加第二套规则。

## 17.3 用户手册

根据实际用户可见变化最小更新：

- `docs/user-manual/assessments/overview.md`：类型属于可配置目录；
- `docs/user-manual/feedback/...`：反馈分类可维护、默认私密行为；
- `docs/user-manual/worldskills_forum/...`：信息类型目录；
- `docs/user-manual/event_countdown/...`：事件类型目录；
- `docs/user-manual/behaviors/...`：严重程度和系数由规则配置；
- `docs/user-manual/scoring/overview.md`：解析器由代码实现 + DB 启用配置，初始化来自 Bootstrap（如果用户手册当前涉及该内容）。

不要把纯内部 migration 细节写进用户手册。

---

# 18. Migration 实施顺序建议

各 APP 可以独立生成 migrations，但在最终合并前检查依赖图。

推荐顺序：

1. `core`：Bootstrap 代码不涉及 schema；SiteConfig 不需要 schema migration。
2. `assessments`：AssessmentType + Assessment FK migration。
3. `feedback`：FeedbackCategory + FK migration。
4. `worldskills_forum`：ForumPostType + FK migration。
5. `event_countdown`：CountdownEventType + FK migration。
6. `behaviors`：Nature 代码整理、Severity model/FK、Rule、Category/Item code migration。
7. `scoring`：通常无 schema 变化，只改 Bootstrap/service；如果为配置增加约束再单独 migration。
8. 最后统一 permission bundle / docs / README。

注意：

- 不修改 `assessments/0002...`、`worldskills_forum/0002~0004`、`behaviors/0007...` 等已有 migration；
- 新 migration dependency 只指向当前 APP 最新 migration 和真实跨 APP schema 依赖；
- 数据 migration 不 import current models/bootstrap；
- migration 文件中不要依赖 fixture。

---

# 19. 测试要求

这是跨 APP schema/data migration 任务，不能只测页面 happy path。

## 19.1 Bootstrap tests

建议建立集中测试，例如：

```text
core/test_bootstrap.py
```

或按 APP 分散后再由 command test 覆盖整体。

必须验证：

1. 空的业务目录执行 `bootstrap_tms` 后创建本 Plan 明确的默认数据；
2. 第二次执行数量不增加；
3. 手工修改默认名称后再次执行，名称不被覆盖；
4. 手工调整 order 后不被覆盖；
5. 手工 `is_active=False` 后不被重新启用；
6. SiteConfig 管理员修改不被覆盖；
7. FlatPage 内容不被覆盖；
8. Parser 配置不被重新启用/抢 default；
9. 不存在权威默认值的 Series/Level/Group 不被擅自创建；
10. 任一 bootstrap function 抛异常时整体事务回滚。

## 19.2 Migration tests

至少为以下迁移建立历史模型升级测试：

- Assessment Type char → FK；
- Feedback category char → FK；
- ForumPost post_type char → FK；
- Countdown event_type char → FK；
- ConductRecord severity char → FK；
- ConductCategory/Item code backfill。

测试应使用 Django `MigrationExecutor` / 项目现有 migration test 风格，不自己发明数据库脚本。

至少覆盖：

- 标准旧值；
- 一条现有业务记录关系保持；
- 可行时覆盖未知 legacy 字符串保留策略；
- reverse migration（如果实现）恢复 code。

## 19.3 行为回归 tests

### Assessments

- 创建 Assessment 使用 active `AssessmentType`；
- inactive type 不出现在新建下拉；
- 历史对象仍能展示 inactive type；
- 按 code 筛选保持。

### Feedback

- 四个默认分类存在；
- complaint 默认 private 数据属性来自 DB，不由 JS code 名称判断；
- 修改 `default_private` 后前端逻辑跟随；
- `FeedbackStatus` 业务校验不变；
- category filter 用 code 正常。

### WorldSkills Forum

- PostType active filter；
- official feed 使用 `post_type.is_official`；
- 改一个自定义新 PostType 为 `is_official=True` 后无需改 Python 即出现在 official 视图；
- `worldskills_forum.manage_forum` 包含新目录管理权限。

### Countdown

- 新建只选 active EventType；
- Theme Registry 行为不受影响；
- 旧 event_type 数据升级无损。

### Behaviors

- Nature 正/负分验证不变；
- Severity Rule 根据 nature 提供不同 label；
- multiplier 计算不变；
- default severity 从 DB rule 获取；
- 停用 severity 不影响旧记录展示；
- 缺 rule 时给出明确校验错误；
- HTMX item/severity endpoint 返回正确 option；
- Record status 审核流保持。

### Scoring

- 读取 enabled/default parser config 不写数据库；
- 禁用 parser 后读取不会恢复；
- 空配置时返回可处理的无配置状态；
- Bootstrap 首次创建 Registry-backed config；
- 数据库不能保存不存在于 Registry 的 parser key。

## 19.4 “无隐式写入”回归测试

至少针对两个当前已知问题建立明确测试：

- 空 SiteConfig 情况下调用 `SiteConfig.get_solo()` 不产生数据库 row；
- 调用 `enabled_parser_configs()` / `default_parser_config()` 不增加或修改 parser config rows。

---

# 20. 验证命令

分阶段开发时先跑受影响 APP 的聚焦测试。

模型和 migration 全部完成后至少执行：

```bash
uv run ruff check core assessments feedback worldskills_forum event_countdown behaviors scoring accounts
uv run manage.py makemigrations --check --dry-run
uv run manage.py check
uv run pytest core assessments feedback worldskills_forum event_countdown behaviors scoring accounts
```

因为本次明确是跨 APP、公共初始化与 migration 治理，最终提交前再运行一次：

```bash
uv run pytest
```

若修改 `static/js/alpine-components.js`、模板中 class 或前端源码，按项目规范执行：

```bash
npm run build:css
```

检查 `static/css/output.css` 是否有真实变化；无必要不要手工编辑生成文件。

还要在**一次性测试/临时数据库**验证 fresh install：

```bash
uv run manage.py migrate
uv run manage.py bootstrap_tms
uv run manage.py bootstrap_tms
```

第二次必须安全无重复、无管理员配置覆盖。

不要在用户生产数据库上为了测试而执行 destructive reset/flush。

---

# 21. 最终全仓静态验收

实施结束再次执行：

```bash
rg -n "TextChoices|IntegerChoices|choices=|_CHOICES|STATUS_CHOICES" \
  core accounts samba standards assessments training scoring evidence glossary \
  worldskills_forum feedback notes meetings notices behaviors event_countdown articles
```

逐项人工确认剩余结果只属于本 Plan 第 3.2 / 3.3 节允许的 Enum/Registry/技术 choices。

特别确认生产代码中没有：

```text
Assessment.Type
FeedbackCategory TextChoices
worldskills_forum.PostType TextChoices
CountdownEvent.EventType
行为严重程度静态 choice/name 映射
```

再执行：

```bash
rg -n "get_or_create|update_or_create" \
  core accounts scoring assessments feedback worldskills_forum event_countdown behaviors
```

人工区分：

- Bootstrap / 正常实体创建幂等逻辑：允许；
- request/read selector/read service 为了“补默认配置”：禁止。

最后扫描：

```bash
rg -n "loaddata .*default|core/default|behaviors/default" README.md docs .github
```

生产安装说明不得再依赖旧 fixture。

---

# 22. 建议的提交拆分

不要把整个跨 APP 改动硬塞进一个难以 review 的提交。建议按可验证纵向切片提交：

1. `core: add explicit bootstrap_tms and stop implicit site config seeding`
2. `assessments: model configurable assessment types`
3. `feedback: model configurable feedback categories`
4. `worldskills_forum: model configurable post types`
5. `event_countdown: model configurable event types`
6. `behaviors: model severities and bootstrap conduct catalogs`
7. `scoring: move parser config creation to bootstrap`
8. `docs: replace fixture initialization with bootstrap workflow`

每个提交完成后跑对应 APP 聚焦测试；最终再跑全量。

如果实现过程中 migration dependency 要求适当合并某两个提交，可以调整，但保持 review 边界清楚。

---

# 23. 明确禁止事项

本次实现不要做以下事情：

- 不建立 `core.Dictionary` / `LookupValue` / `ChoiceOption` 之类全局万能字典表；
- 不把所有 Enum 一刀切数据库化；
- 不把所有 Model 反过来都写进 Bootstrap；
- 不创建未经确认的默认竞赛系列、级别、技能项目、技术领域、用户组；
- 不把 `CompetitionRole.Category` 数据库化；
- 不把 Assessment Status、Training Status、Evidence Review Status 等状态机数据库化；
- 不把评分 M/J 类型数据库化；
- 不把 Parser 实现数据库化；
- 不把 Countdown Theme 变成可以在后台随便创建的 DB row；
- 不把 permission bundles 数据库化；
- 不修改已存在 migration 的历史 seed；
- 不在 `AppConfig.ready()` / signal / request 中自动执行 Bootstrap；
- 不用 `update_or_create` 把管理员修改过的目录强制同步回代码默认值；
- 不依赖目录中文 `name` 做业务判断；
- 不以数据库自增 PK 作为长期 API/filter code；
- 不因为这次跨 APP 改模型顺便重做页面视觉、导航或权限架构。

---

# 24. 完成定义（Definition of Done）

只有同时满足以下条件，本 Plan 才算完成：

1. `AGENTS.md` 的 Model / Enum / Registry / Bootstrap 规则与实际代码一致；
2. `Assessment.Type` 已变为 `AssessmentType` FK，并安全迁移历史数据；
3. `FeedbackCategory` 已变为 Model，`default_private` 数据驱动，前端没有 `complaint` 业务硬编码；
4. `ForumPostType` 已变为 Model，official 语义由 `is_official` 数据驱动；
5. `CountdownEventType` 已变为 Model，Theme 仍是代码 Registry；
6. behaviors 的 Nature 保留 Enum，Severity 成为 Model，Rule 承载 context label/multiplier/default，旧 severity Python 映射被移除；
7. `ConductCategory` / `ConductItem` 有稳定 code，默认 fixture 内容迁到 Bootstrap；
8. `ScoringParserConfig` 不再在读取路径自动创建/启用/重设默认；
9. `SiteConfig.get_solo()` 不再隐式写数据库；
10. `bootstrap_tms` 一次执行创建所有**已有明确依据**的默认目录，第二次执行无重复且不覆盖管理员修改；
11. `AssessmentSeries`、`AssessmentLevel`、默认 Group 等没有被擅自填充未经确认的数据；
12. 历史 `RunPython` migrations 未被重写；
13. README 新安装只需 `migrate -> bootstrap_tms -> createsuperuser`，不再依赖多个 default fixture；
14. 所有新 choice→FK migration 有数据迁移测试；
15. 相关 APP 测试、全量 pytest、Django check、migration drift check、Ruff 通过；
16. 最终 `rg` 扫描中剩余 Enum/Registry 都能按 `AGENTS.md` 明确解释为什么必须留在代码。

完成后，TMS 对“这个可选值到底应该写成 `TextChoices`、数据库 Model，还是代码 Registry”的架构边界应当不再模糊；后续新增业务目录时按同一规则实施，不再重复出现 fixture、data migration、runtime `get_or_create` 和 static choice 多套默认数据来源并存的问题。
