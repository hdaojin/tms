# TMS「竞赛与考核」APP 重构执行 Plan

> 目标分支：`develop`  
> 项目：TMS（Training Management System）  
> 技术栈：Django 6 / Python 3.13 / django-htmx / django-tables2 / Tailwind CSS 4 / DaisyUI 5 / Alpine.js CSP / Iconify  
> 本 Plan 基于当前 `develop` 分支现有 `assessments`、`scoring`、`evidence` 实现，以及已经确定的 TMS 训练体系设计方案。

---

## 0. 总体目标

将当前偏“赛后资料存档 + 成绩导入分析”的「竞赛与考核」能力，升级为贯穿：

**赛前组织 → 赛中实施与在线评分 → 赛后成绩确认与归档 → 技能证据分析 → 反哺训练**

的完整评测业务域。

继续保持三个 APP 的职责边界：

- `assessments`：竞赛与考核本体、模块、人员、资料、最终结果、奖项；
- `scoring`：评分方案、评分点、在线评分、成绩导入；
- `evidence`：考点证据、Skill 映射、历史证据分析。

不要把三者合并成一个巨大 APP。

用户界面上则统一呈现为一个「竞赛与考核」业务域，并以单场 `Assessment` 为中心组织工作台。

---

# 1. 已确认的业务决策

以下内容已经确认，不再作为实施中的开放问题。

## 1.1 Assessment 生命周期覆盖赛前、赛中、赛后

`Assessment` 不只是历史档案，而是一次真实运行中的竞赛或考核。

主要阶段：

1. 草稿准备；
2. 发布；
3. 比赛/考核进行中；
4. 比赛结束；
5. 成绩确认；
6. 成绩发布；
7. 历史归档。

当前已有状态：

- `DRAFT`
- `PUBLISHED`
- `ACTIVE`
- `COMPLETED`
- `ARCHIVED`
- `CANCELLED`

保留这套主状态，不引入过度复杂的状态机。

需要新增或明确：

- 计划时间与实际启动/结束时间分离；
- “比赛结束”与“成绩已发布”分离；
- 使用 `results_published_at` 或等价字段控制学生何时能看到最终成绩。

---

## 1.2 不实现学生报名流程

本阶段 **不新增 `AssessmentRegistration`**。

选手由：

- 项目负责人；
- 教练；
- 有权限的工作人员；

直接添加为 `AssessmentParticipant`。

学生端只展示自己已经被加入的竞赛与考核。

不实现：

- 学生自行报名；
- 报名审核；
- 确认参赛；
- 主动退出；
- 报名状态流转。

---

## 1.3 在线评分采用“最终评分点得分”模式

TMS 支持在比赛过程中，直接在线录入每名选手每个评分点的最终得分。

不实现完整 WorldSkills/CIS 式评分引擎，例如：

- 三位专家分别录入 Judgment；
- 自动计算裁判平均/偏差；
- 专家签字；
- 锁分；
- 多阶段裁判确认；
- 完整竞赛裁判工作流。

上述复杂功能属于未来 CMP / `cmp-marking-controller` 范围。

TMS 第一阶段只需要：

- 每个评分点最终得分；
- 录入人；
- 修改人；
- 确认人；
- 时间；
- 来源；
- 修改历史。

---

## 1.4 保留外部成绩导入

在线评分与 Excel/CMP 导入必须汇聚到同一套 `ScoringResult` 数据结构。

成绩来源建议统一为：

- `ONLINE`
- `EXCEL_IMPORT`
- `CMP_IMPORT`
- `MANUAL`

禁止为不同导入渠道创建互不兼容的成绩模型。

---

## 1.5 长期赛事人员库

新增一个轻量、不可登录的长期赛事人员模型。

建议命名：

`CompetitionPerson`

它不是 Django `User`，不参与认证和权限。

用途：

- Project Manager；
- Skill Competition Manager；
- Venue Manager；
- Team Leader；
- Chief Expert；
- Expert；
- 其他跨届长期稳定的赛事人员。

临时人员无需进入长期人员库，可直接作为某场 Assessment 的人员快照保存。

---

## 1.6 赛事角色可配置

采用数据库配置角色，而不是把所有角色写死在 Python 枚举中。

建议新增：

`CompetitionRole`

至少包含：

- `code`
- `name`
- `category`
- `order`
- `is_active`

`category` 为少量稳定的机器语义类型，例如：

- `COMPETITOR`
- `OFFICIAL`
- `EXPERT`
- `COACH`
- `STAFF`
- `OTHER`

具体角色名称由数据库配置，例如：

- 项目经理；
- 场地经理；
- Team Leader；
- 专家组长；
- 副专家组长；
- 专家；
- 裁判；
- 教练；
- 选手；
- 工作人员；
- 观察员。

系统逻辑不得依赖中文角色名称判断是否为选手，而应依赖稳定的 `category` / `code`。

---

## 1.7 一名人员在某届比赛中的信息必须做历史快照

`AssessmentParticipant` 表示：

> 某个人在某一场 Assessment 中的人员记录。

它可以来源于：

- Django `User`；
- `CompetitionPerson`；
- 完全临时录入。

建议字段：

- `assessment`
- `user`（nullable）
- `competition_person`（nullable）
- `role`
- `display_name`
- `organization`
- `country_or_region`
- `external_code`
- `metadata`

即使关联了 `User` 或 `CompetitionPerson`，仍然保存姓名、单位、国家/地区、身份等快照字段。

后续长期人员资料变化，不得修改历史比赛记录。

---

## 1.8 `AssessmentParticipant` 继续表示所有赛事参与人员

不要把它缩减成只表示选手。

它可以包含：

- 项目经理；
- 场地经理；
- Team Leader；
- 专家组长；
- 专家；
- 裁判；
- 教练；
- 选手；
- 工作人员；
- 观察员；
- 其他角色。

只有 `CompetitionRole.category == COMPETITOR` 的 Participant 才允许产生评分结果和最终比赛成绩。

---

## 1.9 删除/收敛 `ScoringParticipant`

当前：

`AssessmentParticipant → ScoringParticipant → ScoringResult`

存在重复身份层。

目标结构：

`AssessmentParticipant → ScoringResult`

`ScoringResult.participant` 直接指向 `AssessmentParticipant`。

原则：

- 只能给当前评分方案所属 Assessment 的选手评分；
- 参与人员必须是 `COMPETITOR` 类角色；
- 评分结果的唯一性为“选手 + 评分点”。

如果现有数据需要迁移，提供安全的数据迁移。

---

## 1.10 最终结果与评分点明细分开

详细评分：

`ScoringResult`

表示：

> 某选手某个 `ScoringAspect` 的得分。

最终官方结果：

`AssessmentFinalResult`

表示：

> 某选手在整场 Assessment 中最终确认的官方结果。

两者不能合并。

---

## 1.11 最终成绩支持多评分体系

采用：

`AssessmentFinalResult + AssessmentFinalScore`

不要固定成 `score_100`、`score_700` 两个字段。

同一选手同一场比赛允许同时保存多个成绩表示，例如：

- 原始总分；
- 百分制；
- WorldSkills 700 分标准化成绩；
- 其他赛事自定义成绩。

建议 `AssessmentFinalScore` 至少包含：

- `final_result`
- `score_type`
- `label`
- `value`
- `max_value`（nullable）
- `metadata`

`score_type` 可使用稳定枚举，例如：

- `RAW`
- `PERCENTAGE`
- `WORLDSKILLS`
- `CUSTOM`

注意：

WorldSkills 700 分结果不能简单理解成“满分 700 分”，因此模型语义应是“评分体系/标准化结果”，不要设计成 `score_700`。

---

## 1.12 名次和奖项分开

`AssessmentFinalResult` 至少保存：

- `rank`
- `is_official`
- `confirmed_at`
- `confirmed_by`
- `notes`

名次与奖项不能建立固定映射。

不得假设：

- 第一名一定是金牌；
- 第二名一定是银牌；
- 第三名一定是铜牌。

---

## 1.13 一名选手允许多个奖项

新增：

`AssessmentAward`

表示某场比赛可使用的奖项，例如：

- 金牌；
- 银牌；
- 铜牌；
- 优胜奖；
- 最佳选手；
- 最佳新人；
- 一等奖；
- 二等奖；
- 三等奖。

新增中间模型：

`AssessmentResultAward`

关系：

`AssessmentFinalResult -> AssessmentResultAward -> AssessmentAward`

一名选手可获得 0～多个奖项。

---

## 1.14 比赛中不向选手显示实时排名

比赛进行过程中：

- 项目负责人 / 教练 / 授权人员可以查看实时成绩汇总与实时排名；
- 选手不显示实时排名。

比赛结束后，也不要立即因为 `Assessment.status == COMPLETED` 就向学生展示成绩。

只有明确发布成绩后，学生才能看到：

- 最终成绩；
- 最终排名；
- 奖项。

建议使用：

`results_published_at`

作为明确控制点。

---

# 2. 目标领域模型

最终核心关系应收敛为：

```text
Assessment
│
├── AssessmentModule
│      ├── AssessmentModuleDomain
│      ├── AssessmentModuleCoach
│      ├── AssessmentDocument
│      └── ScoringScheme
│             ↓
│        ScoringAspect
│             ↓
│        ScoringResult
│
├── AssessmentParticipant
│      ├── User?
│      ├── CompetitionPerson?
│      └── CompetitionRole
│
├── AssessmentAward
│
└── AssessmentFinalResult
       ├── AssessmentFinalScore
       └── AssessmentResultAward

ScoringAspect
      ↓
KnowledgeEvidence
      ↓
EvidenceSkillMap
      ↓
Skill
```

---

# 3. Phase 1：先完成模型重构

优先完成模型，不先做大规模页面重写。

---

## 3.1 扩展 Assessment

检查当前字段，保留已有：

- `skill_project`
- `series`
- `level`
- `training_cycle`
- `type`
- `name`
- `code`
- `start_date`
- `end_date`
- `location`
- `description`
- `status`
- `created_by`

建议结合当前实现决定是否将 DateField 逐步升级/补充为 DateTimeField。

至少新增：

- `started_at`
- `completed_at`
- `results_published_at`

含义：

- `start_date/end_date`：计划日期；
- `started_at`：实际启动时间；
- `completed_at`：实际完成时间；
- `results_published_at`：最终成绩发布时间。

不要为了状态机引入第三方 workflow 库。

---

## 3.2 扩展 AssessmentModule

当前已有：

- `code`
- `name`
- `description`
- `order`
- `total_mark`
- `duration_minutes`
- `counts_towards_ranking`

建议新增：

- `scheduled_start_at`
- 必要时 `scheduled_end_at`

如果 `scheduled_end_at` 可以稳定由开始时间 + `duration_minutes` 推导，则不要重复存储。

保留：

`AssessmentModuleDomain`

继续支持：

- PRIMARY domain；
- RELATED domain；
- 跨领域模块，例如 Troubleshooting。

---

## 3.3 新增 CompetitionPerson

在 `assessments` APP 中建立长期赛事人员目录。

建议字段：

```text
name
organization
country_or_region
title
email
phone
notes
metadata
is_active
created_at
updated_at
```

要求：

- 不继承 User；
- 不可登录；
- 不参与权限体系；
- 可被多届 Assessment 复用。

先保持轻量，不建设完整 CRM。

---

## 3.4 新增 CompetitionRole

建议字段：

```text
code
name
category
description
order
is_active
```

约束：

- `code` 唯一；
- `category` 使用稳定枚举；
- UI 可配置角色；
- 系统用 category 判断业务语义。

提供初始数据迁移，创建常用角色。

不要在 migration 中绑定中文名称作为业务逻辑。

---

## 3.5 重构 AssessmentParticipant

保留它作为统一赛事参与人员。

目标字段：

```text
assessment
user?
competition_person?
role
external_code
display_name
organization
country_or_region
metadata
```

规则：

1. 可以关联 `User`；
2. 可以关联 `CompetitionPerson`；
3. 也可以完全不关联，直接填写临时人员；
4. 至少必须有能够确定人员身份的信息；
5. `display_name` 必须最终有值；
6. 保存时必须保留历史快照；
7. 不允许通过后续修改长期人员资料破坏历史记录。

迁移当前 role 枚举数据到 `CompetitionRole`。

注意兼容已有 Participant 数据。

---

# 4. Phase 2：重构评分对象

---

## 4.1 删除 ScoringParticipant 身份重复层

当前模型中：

`ScoringParticipant`

同时支持：

- assessment_participant；
- user；
- external_identifier；

导致与 `AssessmentParticipant` 重复。

目标：

`ScoringResult.participant -> AssessmentParticipant`

迁移流程必须安全：

1. 找出所有现有 `ScoringParticipant`；
2. 如果已有 `assessment_participant`，直接映射；
3. 如果只有 `user`，在对应 Assessment 中创建或复用 Participant；
4. 如果只有 `external_identifier`，创建对应临时 Participant；
5. 将 `ScoringResult` 外键迁移；
6. 验证数据完整性；
7. 再删除旧模型。

不要一步删除导致历史数据丢失。

---

## 4.2 强化 ScoringResult

目标字段至少包括：

```text
participant
aspect
score_awarded

source

entered_by
entered_at

updated_by
updated_at

confirmed_by
confirmed_at

evidence
raw_payload
```

根据现有字段合理复用，不机械重复。

数据库约束：

- 唯一 `(participant, aspect)`；
- score 不得超过 aspect.max_mark；
- participant 必须属于对应 Assessment；
- participant 必须是 COMPETITOR 类角色。

涉及跨表业务约束无法用数据库 Constraint 完成时：

- `Model.clean()`；
- service 层；
- form/service 同时保护。

---

## 4.3 增加评分修改审计

在线评分属于重要训练/比赛记录。

至少需要保留：

- 原值；
- 新值；
- 修改人；
- 修改时间；
- 原因（可选）。

优先考虑项目当前已有审计方案。

如果项目没有统一审计组件，新增轻量：

`ScoringResultRevision`

不要为了这一点引入庞大审计框架。

---

# 5. Phase 3：评分方案导入与在线评分统一

---

## 5.1 保留 Excel Marking Scheme 导入

当前：

`AssessmentDocument(MARKING_SCHEME)`
→ parser
→ `ScoringSchemeImport`
→ confirm
→ `ScoringScheme`
→ `ScoringAspect`

继续保留。

---

## 5.2 加强评分表一致性检查

导入确认前同时展示：

- `AssessmentModule.total_mark`
- parser 识别的 module total
- `ScoringScheme / ScoringAspect` 分值合计

如果存在不一致：

- 明确显示 warning；
- 对明显错误阻止确认；
- 不允许静默导入。

---

## 5.3 在线评分直接写 ScoringResult

新增评分工作台。

组织方式优先按：

> 模块 → 选手 → 评分点

支持至少两种高频视角：

### 选手视角

选择选手后显示该模块全部评分点，逐项录分。

### 评分点视角

选择评分点后，快速给所有选手录入该项成绩。

第一阶段不做电子表格级复杂前端。

优先 Django server-rendered + HTMX 局部提交。

---

## 5.4 成绩导入也必须写入 ScoringResult

Excel/CMP/人工导入后统一进入：

`ScoringResult`

禁止存在：

- 在线评分数据表；
- Excel 导入成绩表；

两套平行事实源。

---

# 6. Phase 4：最终成绩、名次与奖项

---

## 6.1 将 AssessmentResultSummary 演进为 AssessmentFinalResult

不要简单删除历史 summary 数据。

优先迁移/重命名为：

`AssessmentFinalResult`

目标关系：

- 一个 COMPETITOR Participant；
- 对一场 Assessment；
- 最多一条最终结果。

建议字段：

```text
assessment
participant
rank
is_official
confirmed_by
confirmed_at
notes
metadata
```

如果 `assessment` 可由 participant 推导，可以不重复保存。

优先减少冗余。

---

## 6.2 新增 AssessmentFinalScore

一条 `AssessmentFinalResult` 可拥有多条成绩表示。

建议字段：

```text
final_result
score_type
label
value
max_value
order
metadata
```

示例：

```text
RAW              86.35 / 100
PERCENTAGE       86.35
WORLDSKILLS      712
```

不要自动认为 WORLDSKILLS 最大值为 700。

---

## 6.3 新增 AssessmentAward

建议字段：

```text
assessment
code
name
category
description
order
metadata
```

可以允许比赛自己配置：

- 金牌；
- 银牌；
- 铜牌；
- 优胜奖；
- 最佳选手；
- 其他奖项。

可选 `category` 用于长期统计：

- `GOLD`
- `SILVER`
- `BRONZE`
- `EXCELLENCE`
- `OTHER`

具体展示名称仍保存真实赛事名称。

---

## 6.4 新增 AssessmentResultAward

中间表：

```text
final_result
award
notes
```

唯一：

`(final_result, award)`

允许一个选手多个奖项。

---

## 6.5 最终结果生成策略

TMS 可以基于详细 `ScoringResult`：

- 汇总模块成绩；
- 汇总总成绩；
- 计算实时排名；

但：

**不要自动把实时计算结果直接当成最终官方结果。**

正式结果应由授权人员确认。

因此需要明确：

- calculated result：实时计算；
- official final result：确认后存档。

---

# 7. Phase 5：权限体系重构

遵循当前项目已经确定的权限原则：

> 权限 = Django Group Permission + TechnicalDomainGroupScope

不要新增 User 级领域 Scope。

---

## 7.1 Assessment 顶层权限

Assessment 是跨领域聚合对象。

创建、编辑、发布、启动、结束、归档：

应由项目级角色/权限控制。

不要继续使用当前：

> 非 superuser 更新 Assessment 直接 404

的特殊限制。

移除这种硬编码 superuser-only 行为。

---

## 7.2 Module / Scoring / Evidence 领域权限

继续通过：

- Permission；
- TechnicalDomain scope；

限制教练只能管理自己技术领域相关模块。

跨领域模块：

- explicit module coach；
- 或项目级权限；

可获得管理能力。

---

## 7.3 参与人员权限

Participant 列表和详情必须遵循所属 Assessment 可见性。

修复当前 participant detail 等可能绕过 scoped queryset 的问题。

---

## 7.4 Scoring 权限

修复当前 scoring 相关页面的领域范围问题。

包括但不限于：

- Scheme list；
- Scheme detail；
- Marking Scheme 导入来源；
- ScoringResult 编辑；
- 在线评分页面。

普通教练不得看到与自己无关技术领域的评分资料。

---

## 7.5 实时成绩可见性

比赛进行中：

允许：

- 项目负责人；
- 对应模块教练；
- 授权人员；

查看实时汇总。

选手：

- 不显示实时排名；
- 不显示其他选手成绩。

---

## 7.6 最终成绩发布

`results_published_at is None`：

选手不能查看正式结果。

`results_published_at` 已设置：

选手可以查看自己的：

- 最终成绩；
- 排名；
- 奖项。

默认不要让普通选手查看其他选手详细评分点。

---

# 8. Phase 6：Assessment 工作台 UI

将当前偏 CRUD 的页面改成：

> “单场比赛工作台”

而不是在主导航暴露十几个模型级入口。

---

## 8.1 顶层列表

「竞赛与考核」列表保留。

提供：

- 搜索；
- 类型筛选；
- 状态筛选；
- 时间；
- 级别；
- 系列；
- 项目。

使用：

- django-tables2；
- 当前全站筛选模式；
- Tailwind CSS 4；
- DaisyUI。

---

## 8.2 Assessment detail 改造成工作台

推荐 Tab：

1. **概览**
2. **模块与资料**
3. **人员**
4. **评分**
5. **最终结果**
6. **考点与技能**
7. **分析**

不要用前端 SPA。

---

## 8.3 概览

展示：

- Assessment 基本信息；
- 状态；
- 时间；
- 地点；
- 模块数量；
- 选手数量；
- 当前进度；
- 是否已发布最终成绩。

根据权限显示操作：

- 编辑；
- 发布；
- 启动；
- 完成；
- 发布成绩；
- 归档；
- 取消。

所有状态动作走 POST。

---

## 8.4 模块与资料

每个 Module 展示：

- code / name；
- TechnicalDomain；
- 计划开始时间；
- 时长；
- 总分；
- 教练；
- 评分方案状态；
- 试题；
- 评分表；
- 附件。

可通过 HTMX 局部新增/编辑。

---

## 8.5 人员

统一管理：

- 项目经理；
- 专家；
- 裁判；
- 教练；
- 选手；
- 其他角色。

新增人员时支持三种模式：

1. 从 TMS User 选择；
2. 从 CompetitionPerson 选择；
3. 临时人员手工录入。

选取 User / CompetitionPerson 后自动填充快照字段，但允许针对本届比赛调整。

---

## 8.6 评分

按 Module 进入在线评分界面。

显示：

- 评分方案；
- 评分进度；
- 已评分人数；
- 未完成项；
- 实时汇总。

使用 HTMX：

- 单评分点提交；
- 局部刷新；
- 成功提示；
- 无整页刷新。

Alpine.js 只处理：

- tab / collapse；
- 本地显示状态；
- 小型交互。

遵守 Alpine CSP build。

---

## 8.7 最终结果

支持：

- 实时计算预览；
- 生成/更新 FinalResult；
- 编辑名次；
- 添加多评分体系成绩；
- 分配多个奖项；
- 最终确认；
- 发布成绩。

正式发布前需要明确的确认动作。

---

## 8.8 考点与技能

保留现有：

`ScoringAspect → KnowledgeEvidence → EvidenceSkillMap → Skill`

功能。

入口收敛到具体 Assessment/Module 工作台中。

不再要求用户从主菜单跳到孤立的 Evidence CRUD。

---

## 8.9 分析

第一阶段只做可解释分析。

例如：

- 模块得分率；
- 选手得分率；
- Skill 得分/失分聚合；
- 历史重复失分；
- 趋势。

不要存储自动推断的“SkillMastery 真值”。

不要自动修改训练计划。

---

# 9. Phase 7：主导航调整

当前「竞赛与考核」菜单暴露过多实现对象。

目标主导航简化为：

```text
竞赛与考核
├── 竞赛与考核
├── 长期赛事人员
└── （必要时）角色配置
```

“新增模块、上传资料、导入评分表、录入评分结果、Evidence 映射”等操作：

进入具体 Assessment 后完成。

普通用户不应面对数据库模型菜单。

---

# 10. Phase 8：学生端

本阶段不做报名。

学生看到：

## 即将开始

- 比赛名称；
- 日期；
- Module；
- 开始时间；
- 时长；
- 说明；
- 被允许查看的资料。

## 已结束且成绩已发布

显示：

- 最终成绩；
- 多评分体系结果；
- 名次；
- 奖项；
- 根据权限允许展示的模块成绩。

比赛期间：

- 不显示实时排名；
- 不显示其他选手成绩。

---

# 11. Phase 9：服务层与 Selector

不要把业务规则堆入 CBV 或 Model.save()。

建立清晰 service / selector。

建议逐步形成：

```text
assessments/services/
    lifecycle.py
    participants.py
    results.py

assessments/selectors/
    assessments.py
    participants.py
    results.py

scoring/services/
    imports.py
    scoring.py
    aggregation.py

scoring/selectors/
    schemes.py
    results.py
```

不要求为了目录形式机械拆文件。

原则：

- selectors：查询与可见范围；
- services：状态改变、业务动作；
- views：HTTP 协调；
- forms：输入验证；
- models：领域数据约束。

---

# 12. Phase 10：HTMX / 前端实现原则

继续使用服务端渲染。

优先：

- Django templates；
- django-tables2；
- django-htmx；
- DaisyUI 5；
- Tailwind CSS 4；
- Alpine.js CSP；
- Iconify。

HTMX 主要负责：

- inline form；
- modal form；
- 局部刷新；
- 在线评分单项提交；
- 切换筛选；
- 状态动作后的局部更新。

不要：

- 构建 React/Vue SPA；
- 引入重复状态管理；
- 为简单 CRUD 写大量 JS；
- 升级到 htmx 4 beta 作为本次重构前提。

---

# 13. 数据迁移要求

此次涉及现有生产/历史数据，必须写数据迁移。

重点：

1. 当前 Participant role 枚举 → CompetitionRole；
2. `ScoringParticipant` → `AssessmentParticipant`；
3. `ScoringResult` 外键迁移；
4. `AssessmentResultSummary` → `AssessmentFinalResult`；
5. 原有 total_score → `AssessmentFinalScore(RAW)` 或等价映射；
6. 原有 award 字符串：
   - 为对应 Assessment 创建 `AssessmentAward`；
   - 创建 `AssessmentResultAward`；
7. rank 保留；
8. metadata 不丢失。

迁移结束必须做完整性检查。

不要只做 schema migration。

---

# 14. 测试要求

不要机械全量测试每一个微小步骤。

但每个 Phase 完成后运行与改动直接相关的测试。

最终至少覆盖：

## Models

- CompetitionRole；
- CompetitionPerson；
- Participant 三种来源；
- 历史快照；
- COMPETITOR 校验；
- FinalResult；
- 多 Score；
- 多 Award；
- ScoringResult 唯一性；
- 跨 Assessment 错误关联。

## Permissions

- superuser；
- 项目级负责人；
- Linux 教练；
- Windows 教练；
- 跨领域模块；
- 普通学生；
- 无权限用户。

## Lifecycle

- DRAFT → PUBLISHED；
- PUBLISHED → ACTIVE；
- ACTIVE → COMPLETED；
- 发布结果；
- ARCHIVED；
- 非法状态动作拒绝。

## Scoring

- 在线录分；
- 修改；
- 审计；
- 确认；
- Excel import；
- 不同 source；
- module mark mismatch；
- 成绩汇总。

## Result

- rank；
- 多成绩体系；
- 多奖项；
- 结果发布前学生不可见；
- 发布后只看自己的结果。

---

# 15. 实施顺序

Codex 严格按以下顺序实施，不要同时大面积修改所有层。

## Step 1

重构/新增基础模型：

- CompetitionPerson
- CompetitionRole
- AssessmentParticipant
- Assessment 时间字段

完成 migration + tests。

## Step 2

迁移 ScoringParticipant：

- ScoringResult 直接关联 AssessmentParticipant；
- 数据迁移；
- 删除旧重复层。

完成 tests。

## Step 3

实现 FinalResult：

- AssessmentFinalResult
- AssessmentFinalScore
- AssessmentAward
- AssessmentResultAward

迁移旧 AssessmentResultSummary。

完成 tests。

## Step 4

修正 Selector / Permission。

重点修复：

- Assessment update superuser-only；
- participant scope；
- scoring scope；
- document/scoring import source scope。

## Step 5

完善 Marking Scheme import consistency validation。

## Step 6

实现在线评分业务 service + 页面。

## Step 7

重构 Assessment detail 为工作台。

## Step 8

重构最终结果页面和成绩发布流程。

## Step 9

收敛主导航。

## Step 10

完善 Skill evidence 分析入口。

## Step 11

最终运行：

- Django system check；
- migrations check；
- 相关 APP tests；
- 必要的全量 test；
- 前端 build。

---

# 16. 非目标

本轮明确不要实现：

- 学生报名；
- 报名审核；
- 多裁判 Judgment 完整工作流；
- WorldSkills CIS 替代品；
- 复杂电子签字；
- 自动训练计划；
- 自动调整训练任务；
- 持久化 SkillMastery 真值；
- CMP 的完整功能；
- React/Vue SPA；
- 与本次业务无关的大规模代码清理。

---

# 17. Codex 执行要求

1. 开始前先阅读当前仓库根目录 `AGENTS.md` 及相关局部规范。
2. 基于最新 `develop` 创建独立 feature branch，不直接在 `develop` 上实施。
3. 先确认当前 migration 状态和现有数据模型，再修改。
4. 以现有代码风格为主，不为了“理想架构”大规模重写无关代码。
5. 优先复用当前 selector/service/template/table/form 基础设施。
6. 所有领域权限必须遵守当前：
   `Django Group Permission + TechnicalDomainGroupScope`
   的权限模型。
7. 不新增 User 级 scope。
8. 保持 Skill 为稳定训练对象；Evidence 关联 Skill，不关联 SkillTreeNode。
9. 所有评分数据最终进入统一 `ScoringResult`。
10. 所有最终比赛结果进入统一 `AssessmentFinalResult`。
11. 历史数据迁移优先级高于模型“干净程度”。
12. 每完成一个 Phase 再进入下一阶段，避免一次性大爆炸式重构。
13. 对无法从当前代码确定的小型实现细节，按“最简单、最少模型、最少维护成本”的原则处理。
14. 如果发现需要改变本 Plan 已确认的核心业务决策，停止该部分实现并在 PR/执行总结中明确说明，不要自行改变产品语义。

---

# 18. 最终验收标准

完成后，应满足以下典型业务流程：

## 场景 A：TMS 内部训练考核

1. 教练创建阶段考核；
2. 配置 Module A / B / C；
3. 设置比赛时间、模块开始时间和时长；
4. 添加选手；
5. 上传 Marking Scheme；
6. TMS 解析评分表；
7. 比赛发布；
8. 比赛启动；
9. 教练在线逐项给选手评分；
10. 系统实时汇总；
11. 比赛完成；
12. 确认最终结果；
13. 填写/确认名次；
14. 如有奖项则分配奖项；
15. 发布成绩；
16. 学生看到自己的最终成绩；
17. TMS 将评分点通过 KnowledgeEvidence 映射到 Skill；
18. 教练查看 Skill 层面的得失分证据。

## 场景 B：外部比赛归档

1. 创建历史 Assessment；
2. 添加参赛人员；
3. 录入长期专家或临时人员；
4. 上传 Test Project / Marking Scheme；
5. 导入外部成绩；
6. 生成 ScoringResult；
7. 保存官方最终成绩；
8. 同时保存百分制 / WorldSkills 标准化成绩；
9. 录入排名；
10. 录入金牌、银牌、铜牌、优胜奖等；
11. 允许一个选手多个奖项；
12. 归档；
13. 后续参与历史分析。

## 场景 C：历史 WorldSkills 数据

允许只存在：

- 选手；
- 最终 WorldSkills 成绩；
- 百分制或其他换算成绩；
- 排名；
- 奖项；

即使缺少完整 ScoringAspect / ScoringResult，也能作为有效历史档案保存。

---

# 19. 产品边界总结

本轮完成后：

**TMS 负责：**

> 训练相关比赛/考核的组织、资料、在线最终评分点录入、成绩归档、历史比赛导入、Skill 证据分析。

**CMP 负责：**

> 正式竞赛环境、复杂裁判流程、多裁判 Judgment、锁分、签字、竞赛控制等重型赛事运行能力。

二者未来通过统一评分结果结构交换数据。

这条边界在本轮实现中不要打破。
