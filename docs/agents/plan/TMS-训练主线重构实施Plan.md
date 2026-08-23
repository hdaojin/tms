# TMS 训练主线重构实施 Plan

> **文档性质**：可供 Codex 直接执行的工程实施计划  
> **唯一业务依据**：`TMS-世赛网络系统管理项目训练体系设计方案.md`  
> **目标仓库**：`hdaojin/tms`  
> **目标分支基线**：`develop`  
> **计划编制时基线提交**：`b343872`  
> **编制日期**：2026-08-18  
> **实施性质**：允许破坏性领域重构；当前无重要业务数据，不要求保留现有训练主线数据兼容性

---

# 0. 执行契约

本 Plan 的业务语义已经确定。执行过程中：

1. **业务设计以《TMS 世界技能大赛网络系统管理项目训练体系设计方案》为唯一业务依据。**
2. 当前代码与设计方案冲突时，以设计方案为准，不为了兼容旧模型保留错误的领域抽象。
3. 不重新讨论以下已经确定的结论：
   - `Skill` 是长期稳定的核心业务对象；
   - `TechnicalDomain` 是训练组织与技术教练职责的主轴；
   - WSOS 是独立的标准映射维度；
   - `CapabilityDomain` 删除；
   - `Skill` 与技能树版本解耦；
   - `events` 重构为 `assessments`；
   - `knowledge` 重构为 `evidence`；
   - `archives` 删除；
   - `examcontent` 当前阶段删除；
   - 文件回归具体业务 APP；
   - `TrainingCycle → TrainingPlan → TrainingTask → TaskExecution → TrainingLog`；
   - 系统提供分析证据，不自动制定或调整训练计划；
   - 当前阶段不实现 AI 试题解析、不实现 AI 训练日志生成，仅为未来扩展保留合理边界。
4. 当前没有重要业务数据：
   - **不实施旧训练主线数据迁移**；
   - 可以重建受影响 APP 的 migration history；
   - 可以要求开发/测试环境重建数据库；
   - 但必须保证全新仓库 + 空数据库能够一次性完成 `migrate`。
5. 不允许为了降低一次重构工作量而长期保留新旧两套领域模型。
6. 允许实施过程中短暂保留旧 APP 作为过渡，但最终提交必须清除旧代码、旧路由、旧导航、旧文档和无效 migration dependency。
7. 所有实现遵循仓库最新 `AGENTS.md` 中仍然适用的工程规范；当 `AGENTS.md` 与本次已确认业务方案冲突时，本 Plan 优先，并在本次重构末尾同步更新 `AGENTS.md`。
8. 不进行与训练主线无关的业务重构。`feedback`、`worldskills_forum`、`meetings`、`notices`、`behaviors`、`glossary` 等只处理因模型依赖变化而必须修改的部分。

---

# 1. 实施目标

本次重构完成后，TMS 训练主线必须稳定为：

```text
                    ┌──────── 标准维度 ────────┐
                    │                          │
TechnicalDomain ─→ Skill ←──────────── WSOSSection
       │             │
       │             ├──────────────┐
       │             │              │
       ↓             ↓              ↓
技术教练职责      Evidence       TrainingTask
                     ↑              ↓
                     │          TaskExecution
                     │              ↓
AssessmentModule     │          TrainingLog
       ↓              │
AssessmentDocument   │
       ↓              │
ScoringScheme         │
       ↓              │
ScoringAspect ────────┘
       ↓
ScoringResult
       ↓
Skill 表现分析
       ↓
教练人工判断
       ↓
人工调整下一阶段 TrainingPlan / TrainingTask
```

最终达到以下业务能力：

- 项目负责人可以全局管理 Linux / Windows / Network 三个技术领域；
- 每个技术教练可以主要维护自己负责领域的 Skill、评测模块、训练任务和评价数据；
- WSOS 作为独立标准维度映射到 Skill；
- Skill 不因技能树版本变化而失去长期身份；
- 历届比赛与考核资料可归档并形成考点证据；
- 评分表可以解析成评分点，并继续生成考点证据；
- 训练计划可以结构化拆解成训练任务；
- 训练任务与 Skill 建立明确关联；
- 每个选手有独立 TaskExecution；
- 训练日志建立在真实 TaskExecution 数据之上；
- 训练投入与考核表现可以在 Skill 层汇合；
- 不再存在独立“资料资产中心”；
- 新项目规范和领域文档不再描述旧架构。

---

# 2. 当前 `develop` 基线与主要差距

实施开始前重新确认 `develop` HEAD。如果 HEAD 已不是 `b343872`：

```bash
git fetch origin
git switch develop
git pull --ff-only
git log -1 --oneline
```

然后检查自 `b343872` 之后是否修改：

```text
standards/
events/
archives/
examcontent/
knowledge/
scoring/
training/
core/
accounts/
tmsproject/settings.py
tmsproject/urls.py
AGENTS.md
CONTEXT.md
```

如果有修改，将新修改吸收到本 Plan，不得覆盖后续已经合并的有效功能。

## 2.1 `standards`

当前：

```text
SkillProject
CapabilityDomain
SkillTreeVersion
SkillNode
```

问题：

- `CapabilityDomain` 混合技术领域与横向能力语义；
- Skill 的稳定身份包含在版本化 `SkillNode` 中；
- 历史数据不能天然跨技能树版本持续指向同一个 Skill。

目标：

```text
SkillProject
TechnicalDomain
TechnicalDomainMembership
Skill
SkillTreeVersion
SkillTreeNode
WSOSVersion
WSOSSection
SkillWSOSMap
```

## 2.2 `events`

当前：

```text
CompetitionSeries
CompetitionLevel
Event
EventModule
EventModuleCapabilityDomainMap
EventParticipant
EventResultSummary
```

目标：新增 `assessments`，以“竞赛与考核”表达训练主线中的评测对象。

## 2.3 `archives`

当前以 `ArchiveAsset + GenericForeignKey` 管理业务文件。

目标：删除独立 `archives` APP；文件直接属于具体业务对象；通用 storage/upload/validation/cleanup 继续放在 `core`。

## 2.4 `examcontent`

当前 `ExamPaper / ExamRequirement` 暂无必要继续作为独立领域。

目标：删除；原始试题作为 `AssessmentDocument(TEST_PROJECT)`；教练直接手工补充 Evidence。

## 2.5 `knowledge`

当前 Evidence 映射到版本化 `SkillNode`，并依赖 `CapabilityDomain`。

目标：新增 `evidence`；Evidence 映射到长期稳定 `Skill`。

## 2.6 `training`

当前仅有：

```text
TrainingCycle
TrainingLog
```

目标：完整建立：

```text
TrainingCycle
TrainingCycleMember
TrainingPlan
TrainingTask
TrainingTaskDomain
TrainingTaskSkill
TrainingTaskCoach
TrainingTaskAttachment
TaskExecution
TaskExecutionAttachment
TrainingLog
TrainingLogExecution
```

---

# 3. 分支与提交策略

创建功能分支：

```bash
git switch develop
git pull --ff-only
git switch -c feature/training-domain-refactor
```

采用**一个功能分支、多个可验证提交**，不要拆成多个长期并行分支，因为 APP 重命名、migration graph 和跨 APP FK 高度耦合。

推荐提交边界：

1. `refactor(standards): establish technical domains and stable skills`
2. `refactor(assessments): replace events and move assessment documents`
3. `refactor(evidence): map evidence to stable skills`
4. `refactor(scoring): rewire scoring to assessments and evidence`
5. `feat(training): add plans tasks executions and logs`
6. `refactor(core): remove archive asset workflow`
7. `refactor(migrations): rebuild training-domain migration graph`
8. `feat(ui): complete training and assessment workflows`
9. `docs: align TMS domain documentation with training architecture`
10. `test: complete training mainline regression coverage`

允许实际执行时合并相邻提交，但禁止一个超大提交同时完成所有内容。

---

# 4. Phase 0：依赖审计与重构安全边界

## 4.1 全局检索旧领域依赖

在任何删除操作之前执行：

```bash
rg -n \
  "archives|ArchiveAsset|events\.|EventModule|EventParticipant|EventResultSummary|CapabilityDomain|SkillNode|examcontent|ExamPaper|ExamRequirement|knowledge\.|KnowledgeEvidenceSkillMap" \
  . \
  --glob '!media/**' \
  --glob '!media-private/**' \
  --glob '!staticfiles/**' \
  --glob '!.venv/**' \
  --glob '!.uv-cache/**' \
  --glob '!node_modules/**'
```

按以下类型分类结果：

- Python import；
- 字符串 ForeignKey；
- migration dependency；
- URL namespace；
- templates；
- navigation；
- permissions；
- tests；
- fixtures；
- management commands；
- docs；
- scripts。

## 4.2 单独检查 migration graph

执行：

```bash
rg -n \
  "('standards'|\"standards\"|'events'|\"events\"|'archives'|\"archives\"|'examcontent'|\"examcontent\"|'knowledge'|\"knowledge\"|'training'|\"training\"|'scoring'|\"scoring\")" \
  */migrations
```

特别确认：

- 哪些非主线 APP migration 依赖 `standards`；
- 哪些 migration 依赖即将删除的 `events / archives / examcontent / knowledge`；
- fixture 是否通过自然键引用旧 ContentType / Permission；
- 是否有 `RunPython` 直接 import 当前模型而非 historical model。

### 迁移策略原则

由于没有重要业务数据：

- 不写复杂的数据保留 migration；
- 不使用 `SeparateDatabaseAndState` 保存旧关系；
- 不保留旧表兼容层；
- **重建受影响 migration history**。

但必须先计算完整受影响集合，禁止简单删几个 migration 后留下悬空 dependency。

## 4.3 建立重构前基线

执行当前 CI 等价命令：

```bash
uv sync --frozen
uv run ruff check .
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
uv run pytest
npm ci
npm run build:css
```

如果基线已有失败：记录失败并判断是否与本次重构有关；不顺手大面积修复无关问题，本次改动不能新增失败。

---

# 5. Phase 1：重建 `standards` 标准领域

这是整个重构的地基，必须优先完成。

## 5.1 保留 `SkillProject`

继续保留现有长期技能项目模型：

```text
code
name
short_name
description
order
is_active
created_at
updated_at
```

不将 WorldSkills、国赛、省赛等复制成不同 SkillProject。

## 5.2 删除 `CapabilityDomain`

最终删除 `CapabilityDomain` 以及所有 `capability_domain*` 外键、表单、视图、模板、过滤器和测试。禁止保留“兼容用 CapabilityDomain”。

## 5.3 新增 `TechnicalDomain`

字段：

```text
skill_project    FK -> SkillProject / CASCADE
code             CharField(50)
name             CharField(120)
description      TextField(blank=True)
order            PositiveIntegerField(default=0)
is_active        BooleanField(default=True)
created_at
updated_at
```

约束：

```text
UniqueConstraint(skill_project, code)
```

默认排序：

```text
skill_project, order, code, name
```

不把 Linux / Windows / Network 写死成代码 choice；它们是项目数据。

## 5.4 新增 `TechnicalDomainMembership`

字段：

```text
technical_domain   FK -> TechnicalDomain / CASCADE
user               FK -> AUTH_USER_MODEL / CASCADE
role               LEAD_COACH | COACH
created_at
updated_at
```

约束：

```text
UniqueConstraint(technical_domain, user)
```

项目管理员/superuser 的全局权限不要通过复制三条 Membership 实现。

## 5.5 新增长期稳定 `Skill`

字段：

```text
skill_project       FK -> SkillProject / CASCADE
primary_domain      FK -> TechnicalDomain / PROTECT
name                CharField(200)
description         TextField(blank=True)
difficulty          PositiveSmallIntegerField(1..5, default=3)
is_core             BooleanField(default=False)
is_assessable       BooleanField(default=True)
tags                JSONField(default=list, blank=True)
order               PositiveIntegerField(default=0)
is_active           BooleanField(default=True)
created_at
updated_at
```

技能编号直接由数据库主键显示为 `SK-000123`，不维护第二套人工代码。正式名称和别名使用独立 `SkillTerm` 登记：

```text
skill_project       FK -> SkillProject / CASCADE
skill               FK -> Skill / CASCADE
term                CharField(200)
normalized_term     CharField(400)
kind                name / alias

UniqueConstraint(skill_project, normalized_term)
Conditional UniqueConstraint(skill, kind=name)
```

`normalized_term` 使用 NFKC、英文大小写折叠并忽略普通空白生成，但保留 `+`、`#`、`.`、`/`、连字符等技术符号。停用 Skill 的称谓继续参与查重。

验证：

- `primary_domain.skill_project == skill_project`；
- inactive domain 不用于新建 active Skill；
- difficulty 1..5。
- 正式名称和别名不能与同项目其他 Skill 的称谓发生规范化冲突。

### related domains

第一版允许：

```text
related_domains M2M TechnicalDomain, blank=True
```

要求：

- 所有关联领域属于同一 SkillProject；
- primary_domain 不重复出现在 related_domains；
- UI 将其作为少量例外使用，不鼓励普通 Skill 全部跨领域。

M2M 关联校验放在 ModelForm/service 层，并补测试，不依赖 `Model.clean()` 处理尚未保存的 M2M。

## 5.6 重构 `SkillTreeVersion`

保留：

```text
skill_project
version
name
description
is_current
created_by
created_at
updated_at
```

约束：

- `(skill_project, version)` 唯一；
- 每个 SkillProject 最多一个 current version。

## 5.7 `SkillNode` 重构为 `SkillTreeNode`

字段：

```text
tree_version        FK -> SkillTreeVersion / CASCADE
technical_domain    FK -> TechnicalDomain / PROTECT
parent              FK self / CASCADE / null / blank
node_type           CATEGORY | TOPIC | SKILL
code                CharField(100)
name                CharField(200, blank=True)
description         TextField(blank=True)
skill               FK -> Skill / PROTECT / null / blank
order               PositiveIntegerField(default=0)
is_active           BooleanField(default=True)
created_at
updated_at
```

约束：

```text
UniqueConstraint(tree_version, code)
UniqueConstraint(tree_version, skill, condition=skill IS NOT NULL)
```

规则：

### CATEGORY / TOPIC

- skill 必须为空；
- name 必填。

### SKILL

- skill 必须存在；
- Skill 属于 tree_version 对应 SkillProject；
- Skill primary_domain 与当前 technical_domain 相同，或当前 domain 属于 Skill.related_domains；
- SKILL 节点不能有子节点；
- 页面名称默认使用 Skill.name；
- 不在树节点重复存 difficulty/tags/aliases/is_core/is_assessable。

### 树结构

- 根节点只能 CATEGORY；
- CATEGORY 下允许 TOPIC 或 SKILL；
- TOPIC 下只允许 SKILL；
- SKILL 下不能创建子节点；
- parent 必须同 tree_version、同 technical_domain；
- 禁止循环引用。

## 5.8 新增 WSOS 模型

### `WSOSVersion`

```text
skill_project
code
name
description
is_current
created_by
created_at
updated_at
```

约束：

- `(skill_project, code)` 唯一；
- 每个 SkillProject 最多一个 current WSOSVersion。

### `WSOSSection`

```text
wsos_version
code
name
description
weight DecimalField(max_digits=5, decimal_places=2)
order
```

约束：

```text
UniqueConstraint(wsos_version, code)
0 <= weight <= 100
```

允许某个 Section 暂时 0 个 Skill 映射。

### `SkillWSOSMap`

```text
skill
wsos_section
note blank
created_at
```

约束：

```text
UniqueConstraint(skill, wsos_section)
```

验证 Skill 与 WSOSSection 属于同一 SkillProject。

第一版不增加 primary WSOS、mapping weight、competency score。

## 5.9 `standards` selectors/services

至少提供：

```python
manageable_domains_for(user, skill_project=None)
can_manage_domain(user, domain)
can_manage_skill(user, skill)
current_skill_tree_for(project)
current_wsos_for(project)
```

权限原则：

- superuser / 项目全局管理员：全部；
- 技术教练必须同时具有 Django action permission 和对应 TechnicalDomainMembership；
- Skill 修改范围以 primary_domain 为准；
- related_domains 不自动赋予主要维护权。

## 5.10 Phase 1 测试

至少覆盖：

- TechnicalDomain 项目内 code 唯一；
- Membership 唯一；
- Skill primary/related domain 项目一致；
- SkillTreeNode 结构约束；
- 同一 Skill 可出现在不同 SkillTreeVersion，但 Skill PK 不变；
- 同一版本同一 Skill 只能出现一次；
- WSOSSection 权重范围；
- Skill↔WSOS 跨项目禁止；
- domain-scope selectors；
- current SkillTreeVersion / WSOSVersion 唯一。

执行：

```bash
uv run pytest standards
uv run manage.py check
uv run ruff check standards
```

---

# 6. Phase 2：新增 `assessments`，替代 `events`

先新增新 APP，再重接 scoring/evidence/training，不要第一步直接删 `events`。

```bash
uv run manage.py startapp assessments
```

按项目既有方式整理 models/services/selectors/forms/tables/urls/templates/tests。

## 6.1 `AssessmentSeries`

替代 `CompetitionSeries`：

```text
code
name
description
order
is_active
created_at
updated_at
```

## 6.2 `AssessmentLevel`

替代 `CompetitionLevel`：

```text
code
name
weight
order
is_active
created_at
updated_at
```

weight 只作为历史统计维度，不自动决定训练优先级。

## 6.3 `Assessment`

类型：

```text
COMPETITION          正式竞赛
SELECTION            选拔赛
EXCHANGE             交流赛
MOCK                 模拟赛
TRAINING_ASSESSMENT  训练考核
TRAINING_TEST        训练测试
OTHER
```

状态：

```text
DRAFT
PUBLISHED
ACTIVE
COMPLETED
ARCHIVED
CANCELLED
```

字段：

```text
skill_project
series nullable
level nullable
training_cycle nullable
assessment_type
name
code unique
start_date
end_date nullable
location blank
description blank
status
created_by
created_at
updated_at
```

验证 end_date >= start_date，training_cycle 与 skill_project 一致。

## 6.4 `AssessmentModule`

字段：

```text
assessment
code
name
description
order
total_mark
duration_minutes
counts_towards_ranking
created_at
updated_at
```

约束：

```text
UniqueConstraint(assessment, code)
```

## 6.5 `AssessmentModuleDomain`

字段：

```text
assessment_module
technical_domain
role = PRIMARY | RELATED
note blank
```

约束：

```text
UniqueConstraint(assessment_module, technical_domain)
```

最多一个 PRIMARY，但允许全部 RELATED，表达真正没有单一主领域的综合模块。

验证 assessment 项目与 domain 项目一致。

## 6.6 `AssessmentModuleCoach`

字段：

```text
assessment_module
user
role = PRIMARY | COLLABORATOR
created_at
```

约束：

```text
UniqueConstraint(assessment_module, user)
```

最多一个 PRIMARY coach，但允许没有 PRIMARY。

权限规则：

1. 项目管理员：全权；
2. 单领域模块：对应 TechnicalDomain 的教练可维护；
3. 跨领域模块：只有显式 AssessmentModuleCoach 和项目管理员可以修改模块级业务，其他相关领域教练可查看；
4. coach assignment 由项目管理员或有模块管理权的主教练维护。

## 6.7 `AssessmentParticipant`

字段延续现有语义：

```text
assessment
user nullable
external_code blank
display_name
role
organization
metadata
created_at
updated_at
```

角色：COMPETITOR / EXPERT / COACH / STAFF / OBSERVER / OTHER。

保持 user/external_code 唯一性语义。

## 6.8 `AssessmentResultSummary`

字段：

```text
assessment
participant OneToOne
total_score
rank
award
metadata
created_at
updated_at
```

participant 必须属于 assessment。

---

# 7. Phase 3：业务文件回归 `assessments`

## 7.1 新增 `AssessmentDocument`

字段：

```text
assessment         FK -> Assessment
module             FK -> AssessmentModule / null / blank
document_type
title
description blank
file
original_filename
file_sha256
version blank
metadata JSONField(default=dict, blank=True)
uploaded_by
created_at
updated_at
```

类型：

```text
TEST_PROJECT       试题
MARKING_SCHEME     评分表
MARKING_STANDARD   评分标准
SCORING_SCRIPT     评分脚本
RESULT_FILE        成绩/结果文件
ATTACHMENT         其他附件
```

文件使用：

```text
PrivateMediaStorage("assessments")
```

上传路径建议：

```text
<assessment-code>/<module-code-or-general>/<document-type>/<filename>
```

校验：

- module 如果存在必须属于 assessment；
- 扩展、大小、签名使用 `core.uploads.UploadSpec`；
- SHA256 helper 移到 `core`；
- 下载必须先经过 Assessment/Module 业务权限判断。

## 7.2 页面入口

不提供独立 `/archives/upload/`。

只允许从 Assessment / AssessmentModule 上下文上传。

建议详情结构：

```text
竞赛与考核详情
├── 基本信息
├── 模块
├── 参与人员
├── 资料
└── 结果
```

Module 详情：

```text
Module A
├── 技术领域
├── 负责教练
├── 试题
├── 评分表
├── 评分标准
├── 评分脚本
├── 评分数据
└── 考点证据
```

## 7.3 `core` 文件能力

保留/提取：

- PrivateMediaStorage；
- UploadSpec；
- 扩展验证；
- 大小验证；
- 文件签名验证；
- SHA256 helper；
- 文件名 helper；
- cleanup；
- 下载响应 helper；
- 文件图标和大小格式化；
- 现有 FilePond 通用上传能力。

**不要创建新的全局泛型 `FileAsset` / `Attachment` 业务模型。**

---

# 8. Phase 4：新增 `evidence`，替代 `knowledge`

```bash
uv run manage.py startapp evidence
```

## 8.1 `KnowledgeEvidence`

类名继续使用 KnowledgeEvidence，APP 改为 evidence。

字段：

```text
skill_project
assessment_module nullable
source_type
scoring_aspect nullable
source_document nullable
title
original_text blank
normalized_text blank
source_location blank
estimated_mark nullable
estimated_difficulty nullable
evidence_level blank
extraction_source
confidence
review_status
reviewed_by nullable
reviewed_at nullable
review_note blank
metadata
created_by nullable
created_at
updated_at
```

SourceType：

```text
SCORING_ASPECT
TEST_PROJECT
MARKING_STANDARD
SCRIPT_CHECK
CMP_RESULT_ITEM
MANUAL
OTHER
```

ExtractionSource：MANUAL / PARSER / AI / CMP / IMPORTED。

ReviewStatus：DRAFT / PENDING / APPROVED / REJECTED。

### 来源关系

第一版**不使用 GenericForeignKey**。

使用：

```text
scoring_aspect -> scoring.ScoringAspect
source_document -> assessments.AssessmentDocument
```

典型组合：

```text
SCORING_ASPECT:
  scoring_aspect required
  source_document = marking scheme

TEST_PROJECT:
  scoring_aspect null
  source_document = test project

MARKING_STANDARD:
  source_document = marking standard

MANUAL:
  source_document optional
```

校验 source 对象、module 和 skill_project 一致。

## 8.2 `EvidenceSkillMap`

字段：

```text
evidence
skill
is_primary
weight
mapping_source
confidence
reason
review_status
reviewed_by nullable
reviewed_at nullable
created_at
updated_at
```

约束：

```text
UniqueConstraint(evidence, skill)
UniqueConstraint(evidence, condition=is_primary=True)
```

规则：

- 映射目标改为 `standards.Skill`；
- Skill 必须 active；
- Skill 与 evidence 同项目；
- 不再检查 current SkillTreeVersion；
- 一个 evidence 可映射多个 Skill；
- 最多一个 primary；
- 覆盖与分析只统计 APPROVED mapping。

保留 `weight`，用于一个评分点覆盖多个 Skill 时做分值折算。

## 8.3 Evidence services

至少实现：

```python
create_evidence_from_scoring_aspect(aspect, created_by=None)
create_manual_evidence_from_document(...)
approve_evidence(...)
reject_evidence(...)
approve_mapping(...)
```

评分点自动生成：

```text
source_type = SCORING_ASPECT
extraction_source = PARSER
estimated_mark = aspect.max_mark
source_document = scheme.source_document
assessment_module = scheme.assessment_module
```

当前规则可继续默认 APPROVED。

教练从试题手工补充：TEST_PROJECT 或 MANUAL；根据权限可以直接 APPROVED。

本次只保留 AI enum，不创建 AI service stub。

---

# 9. Phase 5：重构 `scoring`

保留 scoring APP。

## 9.1 `ScoringScheme`

修改：

```text
event_module    → assessment_module
source_asset    → source_document
```

`source_document` 必须是 MARKING_SCHEME，且 document.module == assessment_module。

## 9.2 `ScoringSchemeImport`

改为：

```text
assessment_module
source_document
scheme
status
parser_*
parsed_payload
...
```

不再保存 ArchiveAsset FK。

## 9.3 `ScoringAspect`

删除 GenericRelation 到旧 knowledge。

Evidence 通过 `KnowledgeEvidence.scoring_aspect` 反向访问。

保留 M/J、description、command、requirement、max_mark、row、JudgementOption。

## 9.4 `ScoringParticipant`

```text
event_participant → assessment_participant
```

其他 user / external identifier 兼容场景继续保留。

## 9.5 `ScoringResultImport`

```text
source_asset → source_document
```

source_document 类型使用 RESULT_FILE。

## 9.6 上传解析流程

当前：

```text
raw upload
→ ArchiveAsset
→ ScoringSchemeImport
→ ScoringScheme
```

目标：

```text
AssessmentDocument(MARKING_SCHEME)
→ ScoringSchemeImport
→ ScoringScheme
→ ScoringAspect
→ KnowledgeEvidence
```

建议 service：

```python
parse_scheme_document(document, parser_config, user=None)
confirm_scheme_import(scheme_import, user=None)
create_scheme_from_document(document, user=None, parser_config=None)
```

scoring service 不再负责创建通用文件对象。

## 9.7 评分权限

权限从：

```text
ScoringScheme → AssessmentModule → TechnicalDomain / ModuleCoach
```

推导。

- 项目管理员全部；
- 单领域模块对应教练按权限维护；
- 跨领域模块仅显式 ModuleCoach 可修改；
- 选手默认只看自己的结果，如当前产品没有选手成绩页则本次不额外扩展。

---

# 10. Phase 6：完整重构 `training`

## 10.1 `TrainingCycle`

字段：

```text
skill_project
parent nullable self
skill_tree_version
code
name
start_date
end_date nullable
status
description
created_at
updated_at
```

规则：

- skill_tree_version 属于 skill_project；
- parent 同项目；
- 禁止 self/cycle；
- 第一版最多两层：根周期 → 阶段周期；
- 阶段周期日期必须在父周期范围内；
- end_date >= start_date。

状态：PLANNING / ACTIVE / COMPLETED / ARCHIVED。

## 10.2 `TrainingCycleMember`

字段：

```text
training_cycle
user
role = COMPETITOR | COACH
created_at
```

约束：

```text
UniqueConstraint(training_cycle, user)
```

说明：

- TechnicalDomainMembership 表达长期教练技术职责；
- TrainingCycleMember 表达某个周期实际参与人；
- TaskExecution 只分配给 COMPETITOR；
- TaskCoach 应来自 cycle member coach，项目管理员除外。

## 10.3 `TrainingPlan`

字段：

```text
training_cycle
title
start_date
end_date
objective
status
source_file nullable
created_by
created_at
updated_at
```

状态：DRAFT / PUBLISHED / COMPLETED / ARCHIVED。

source_file 直接使用 FileField + PrivateMediaStorage，用于现有 Word/Excel 月计划归档，但不作为系统分析数据源。

校验日期位于 TrainingCycle 内。

## 10.4 `TrainingTask`

字段：

```text
training_plan
planned_date
title
description
requirements
estimated_minutes
priority
status
order
created_by
created_at
updated_at
```

priority：LOW / NORMAL / HIGH / URGENT。

status：DRAFT / PUBLISHED / CANCELLED。

发布前要求：

- 至少一个 TechnicalDomain；
- 至少一个 PRIMARY Skill；
- 至少一个 coach；
- planned_date 位于 plan 日期范围。

不要实现根据评分结果自动创建 TrainingTask。

## 10.5 `TrainingTaskDomain`

```text
training_task
technical_domain
role = PRIMARY | RELATED
```

约束 pair 唯一，最多一个 PRIMARY；允许综合任务全部 RELATED。

## 10.6 `TrainingTaskSkill`

```text
training_task
skill
role = PRIMARY | RELATED
order
```

约束 pair 唯一。

规则：

- 发布任务至少一个 PRIMARY；
- Skill 同项目；
- Skill.primary_domain 或 related_domains 与 TaskDomain 至少有一个交集；
- 不设置训练权重；
- 不把训练次数转换成 mastery。

## 10.7 `TrainingTaskCoach`

```text
training_task
user
role = PRIMARY | COLLABORATOR
created_at
```

约束 pair 唯一；最多一个 PRIMARY。

权限：

- 单领域任务对应领域教练可维护；
- 跨领域任务必须显式 TaskCoach；
- 项目管理员始终可管理。

## 10.8 `TrainingTaskAttachment`

```text
training_task
title blank
file
original_filename
uploaded_by
created_at
```

用途：题目、拓扑、配置样例、学习资料、训练要求附件。

## 10.9 `TaskExecution`

字段：

```text
training_task
user
status
assigned_at
started_at nullable
completed_at nullable
actual_minutes nullable
completion_note
problems
problem_resolved nullable
solution
reflection
coach_feedback
feedback_by nullable
feedback_at nullable
created_at
updated_at
```

状态：

```text
ASSIGNED
IN_PROGRESS
COMPLETED
PARTIALLY_COMPLETED
BLOCKED
CANCELLED
```

约束：

```text
UniqueConstraint(training_task, user)
```

规则：

- user 是该 cycle 的 COMPETITOR；
- actual_minutes >= 0；
- completed 状态设置 completed_at；
- started 状态设置 started_at；
- coach_feedback 仅授权教练修改；
- 选手不能设置 feedback_by；
- 选手只能修改自己的 execution；
- 教练不覆盖选手原始 problems/reflection，需纠正时用反馈字段。

## 10.10 `TaskExecutionAttachment`

```text
task_execution
title blank
file
original_filename
uploaded_by
created_at
```

用于截图、配置、实验报告、拓扑、故障分析、导出结果等。

选手只能向自己的 TaskExecution 上传。

## 10.11 重构 `TrainingLog`

字段：

```text
training_cycle
author
training_date
topic
summary
document nullable
created_at
updated_at
```

增加：

```text
executions = M2M TaskExecution through TrainingLogExecution
```

中间模型：

```text
training_log
task_execution
order
```

约束：

```text
UniqueConstraint(training_log, task_execution)
UniqueConstraint(training_cycle, author, training_date)
```

验证：

- execution.user == author；
- execution 所属 cycle == log cycle；
- execution 与日志日期存在合理对应；
- document 可为空；
- Word/PDF 正式日志直接挂在 TrainingLog。

## 10.12 TrainingLog 辅助生成

本次只实现非 AI 的结构化辅助：

```python
suggest_executions_for_log(user, cycle, date)
build_log_summary_context(...)
```

自动选择当天相关 Execution，并将事实展示给用户。

本次不实现 OpenAI API、自动撰写、自动提交、AI 修改 Execution。

## 10.13 训练日志批量归档

重写现有 `build_training_log_archive()`：直接读取 `TrainingLog.document`。

建议 zip 路径：

```text
<YYYY-MM>/<training-cycle-code>/<author>/<YYYYMMDD>-<filename>
```

无 document 的结构化日志第一版跳过即可。

---

# 11. Phase 7：领域权限与数据范围

不引入第三方 object-permission 框架。

继续使用：

```text
Django Group / Permission
+
TechnicalDomainMembership
+
显式 Module/Task Coach assignment
```

## 11.1 权限层次

### 项目管理员

全局管理标准、评测、训练、scoring/evidence/execution。

### 技术教练

先满足 Django action permission，再限制 TechnicalDomain scope。

### 选手

- 看自己被分配的训练任务；
- 改自己的 TaskExecution；
- 上传自己的 execution 附件；
- 创建/修改自己的 TrainingLog；
- 不访问其他选手私人执行记录。

## 11.2 统一 selectors/helpers

至少建立：

```python
visible_skills_for(user)
manageable_skills_for(user)
visible_assessments_for(user)
manageable_assessment_modules_for(user)
visible_training_tasks_for(user)
manageable_training_tasks_for(user)
visible_task_executions_for(user)
```

View/service 调用这些 helper。

禁止：

- 只在模板隐藏按钮；
- 每个 view 复制一套 group 判断；
- 仅依赖 URL 不暴露。

## 11.3 跨领域编辑规则

- Skill：按 primary_domain；
- AssessmentModule：跨领域时必须显式 ModuleCoach；
- TrainingTask：跨领域时必须显式 TaskCoach；
- Scoring/Evidence：跟随 AssessmentModule；
- TaskExecution feedback：跟随 TrainingTaskCoach / 项目管理员。

---

# 12. Phase 8：页面与实际工作流

继续使用项目现有技术栈：Django 6 template/partials、HTMX、django-htmx、django-tables2、django-filter、Tailwind CSS 4、DaisyUI 5、Alpine CSP、Iconify Tailwind 4。

不引入 React/Vue。

## 12.1 Standards 页面

### 技能目录与技术领域

技能目录采用“技能项目 → 技术领域 → Skill”两级浏览结构，技能项目和技术领域都是页面上下文，不在 Skill 表格中逐行重复显示。

```text
/standards/projects/<project_id>/skills/
/standards/projects/<project_id>/domains/<domain_id>/
/standards/skills/<skill_id>/
```

- 项目技能目录显示该项目下的技术领域卡片、当前用户可见的主要 Skill 数量和关联 Skill 数量；普通用户只看到启用领域，领域维护者还可看到明确标记的停用领域。
- 技术领域详情合并领域信息、负责成员和 Skill 条目表格，不再维护独立的领域管理列表入口。
- Skill 条目表格默认只显示启用的主要 Skill，支持关键词、active、core、assessable、排序和分页；用户可显式开启“包含关联技能”，关联结果必须标记且不计入主要 Skill 数量。
- 新增技术领域从项目技能目录进入；新增 Skill 从具体领域详情进入，并由页面上下文固定技能项目和主要技术领域。
- 导航只保留“技能目录”，旧 `/standards/domains/` 和旧的跨项目 Skill 列表 URL 不提供兼容入口。

### Skill 详情

详情显示：

- 基本信息；
- primary/related domains；
- 不同 SkillTreeVersion 中位置；
- WSOS mapping；
- 历史 Evidence 摘要；
- 近期 Training 摘要；
- Scoring 表现入口。

第一版不要求复杂图表。

## 12.2 WSOS 页面

项目负责人查看：

```text
WSOSVersion
→ WSOSSection
→ mapped Skills
```

支持 current version、section weight、Skill mapping、按 TechnicalDomain 分布。

Communication 等 section 允许 0 mapping，不显示错误警告。

## 12.3 Assessment 页面

一级导航名称：**竞赛与考核**。

列表支持：类型、系列、级别、日期、状态、TechnicalDomain、搜索。

详情：基本信息、模块、参与人员、资料、结果。

## 12.4 评分表工作流

在 AssessmentModule：

1. 上传 MARKING_SCHEME；
2. 成为 AssessmentDocument；
3. 选择/default parser；
4. 显示解析预览；
5. 确认；
6. 创建 ScoringScheme；
7. 创建 ScoringAspect；
8. 自动生成 Evidence；
9. 教练做 Evidence→Skill mapping。

保留当前解析器能力，不重写解析算法。

## 12.5 试题工作流

上传 TEST_PROJECT：

- 只归档原文件；
- 不自动解析；
- 页面提供“从试题补充考点”；
- 教练手工创建 Evidence 并映射 Skill。

## 12.6 Training 页面

一级导航建议：

```text
训练管理
├── 训练周期
├── 训练计划
├── 我的训练
└── 训练日志
```

TrainingCycle 详情：周期信息、阶段、成员、计划、相关 Assessment。

TrainingPlan 详情：按日期展示 Task；提供列表和简洁月视图，不引入复杂日历库。

TrainingTask 详情：日期、要求、Domain、Skills、Coach、附件、分配选手、完成摘要。

## 12.7 选手“我的训练”

展示：今日、待完成、进行中、已完成、被阻塞。

Execution 编辑只填写真实事实：状态、实际用时、完成情况、问题、解决情况、总结、附件。

不让选手重复抄任务标题和 Skill。

## 12.8 教练工作台

第一版至少提供领域过滤后的：

- 待评价 TaskExecution；
- 近期任务完成情况；
- blocked tasks；
- 最近考核失分 Skill；
- 未映射 Evidence。

可由多个现有列表组合，不要求一次开发复杂 Dashboard。

## 12.9 HTMX

适合：列表筛选、状态更新、Domain/Skill/Coach 关联、TaskExecution 更新、Evidence mapping、modal form、局部刷新。

服务端返回 HTML partial，不为普通 CRUD 新建 JSON API。

## 12.10 Alpine.js

继续使用 CSP build，只用于 modal/dropdown/tab/FilePond bridge 等轻交互；训练业务状态始终以服务端为事实源。

---

# 13. Phase 9：删除旧 APP 和旧模型

只有所有运行时代码已切换新模型后执行。

## 13.1 删除 `archives`

删除目录、INSTALLED_APPS、URL、navigation、permissions、templates、tests、imports、GenericRelation、全局资料入口。

执行：

```bash
rg -n "archives|ArchiveAsset|archive_assets" .
```

运行时代码不得残留。

## 13.2 删除 `events`

所有运行时代码改为 assessments 后删除。

```bash
rg -n "\bEvent\b|EventModule|EventParticipant|events\." .
```

注意排除无关 JavaScript DOM event。

## 13.3 删除 `examcontent`

```bash
rg -n "ExamPaper|ExamRequirement|examcontent" .
```

不建立空壳替代。

## 13.4 删除 `knowledge`

所有引用改为 evidence 后删除。

```bash
rg -n "knowledge\.|KnowledgeEvidenceSkillMap" .
```

`KnowledgeEvidence` 类名可继续存在于 evidence。

## 13.5 清除 CapabilityDomain / SkillNode

```bash
rg -n "CapabilityDomain|capability_domain|SkillNode" .
```

运行时代码必须无旧 CapabilityDomain；旧 SkillNode 完全由 Skill + SkillTreeNode 取代。

---

# 14. Phase 10：Migration 重建策略

## 14.1 不保留旧训练主线数据

不写：

- Event→Assessment data migration；
- ArchiveAsset→业务 FileField data migration；
- SkillNode→Skill data migration；
- CapabilityDomain→TechnicalDomain data migration。

开发环境重建数据库。

## 14.2 计算完整 reset 集合

再次执行：

```bash
rg -n \
  "dependencies\s*=|standards|events|archives|examcontent|knowledge|scoring|training|assessments|evidence" \
  */migrations
```

至少检查 standards/training/scoring/assessments/evidence 和所有依赖它们 migration node 的其他 APP。

如果例如 `glossary` 依赖 `("standards", "0001_initial")`，新的 standards 仍应提供兼容的 `0001_initial` 且创建 glossary 所需模型（如 SkillProject）。

如果任何非主线 APP 依赖将消失的 events/archives/examcontent/knowledge：

- 修改 dependency；或
- 将该 APP migration 一并 reset。

不得留下 dangling node。

## 14.3 重建 migrations

对最终 reset 集合：

1. 删除 migration 文件，只留 `__init__.py`；
2. 确认 model import 已处于最终状态；
3. 执行 `uv run manage.py makemigrations`；
4. 人工审阅 dependency、swappable user dependency、FK 顺序、conditional constraints、FileField storage serialization、through models；
5. 再提交。

## 14.4 空数据库验证

不能只使用现有开发数据库。

使用临时 SQLite：

```bash
rm -f /tmp/tms-training-refactor.sqlite3

DATABASE_URL=sqlite:////tmp/tms-training-refactor.sqlite3 \
SECRET_KEY=refactor-check-secret \
DEBUG=False \
ALLOWED_HOSTS=localhost \
uv run manage.py migrate --noinput
```

然后：

```bash
DATABASE_URL=sqlite:////tmp/tms-training-refactor.sqlite3 \
SECRET_KEY=refactor-check-secret \
DEBUG=False \
ALLOWED_HOSTS=localhost \
uv run manage.py check
```

如果 `.env` 覆盖 shell env，按项目实际 environ 读取顺序调整；目标不变：**真正空数据库必须从 0 跑完整 migration graph。**

最后：

```bash
uv run manage.py makemigrations --check --dry-run
uv run manage.py showmigrations
```

必须无未生成 migration、无 dangling dependency。

---

# 15. Phase 11：第一版闭环分析

本阶段只实现足够支持教练决策的第一版，不追求复杂 BI。

## 15.1 Skill 历史考查统计

只统计：

```text
APPROVED KnowledgeEvidence
+
APPROVED EvidenceSkillMap
```

指标：

- evidence count；
- assessment count；
- 最近出现日期；
- `estimated_mark × mapping.weight` 累计分值；
- AssessmentLevel 分布；
- TechnicalDomain；
- WSOSSection。

draft/rejected 不计入。

## 15.2 Skill 训练投入

通过 TrainingTaskSkill + TaskExecution 统计：

- 最近训练日期；
- 任务数；
- completed/partial/blocked；
- actual_minutes；
- 常见问题。

页面称为“训练投入/训练情况”，不命名 mastery。

## 15.3 Skill 考核表现

链路：

```text
ScoringResult
→ ScoringAspect
→ KnowledgeEvidence
→ EvidenceSkillMap
→ Skill
```

至少计算：

```text
awarded_mark / mapped_max_mark
```

一个 aspect 映射多个 Skill 时：

```text
max contribution = aspect.max_mark × mapping.weight
score contribution = result.score_awarded × mapping.weight
```

不创建全局“掌握度百分比”持久化字段。

## 15.4 Skill 详情闭环

至少展示：

```text
标准：TechnicalDomain / WSOS
历史考查：次数 / 分值 / 最近出现
训练投入：任务 / 时长 / 问题
考核表现：最近得分趋势
```

提供“创建训练任务”入口，但仅打开人工表单，不自动生成计划。

---

# 16. Phase 12：导航、术语和文档统一

## 16.1 导航

删除旧“资料资产 / 事件 / 旧考点知识”等入口。

建议：

```text
标准体系
  技能目录
  技能树
  WSOS

竞赛与考核
  竞赛与考核列表

训练管理
  训练周期
  训练计划
  我的训练
  训练日志
```

Evidence/Scoring 主要从 AssessmentModule 和 Skill 上下文进入，不强制做一级导航。

## 16.2 `CONTEXT.md`

全面改写，稳定定义：

- SkillProject；
- TechnicalDomain；
- TechnicalDomainMembership；
- Skill；
- SkillTreeVersion；
- SkillTreeNode；
- WSOSVersion；
- WSOSSection；
- Assessment；
- AssessmentModule；
- AssessmentDocument；
- KnowledgeEvidence；
- EvidenceSkillMap；
- TrainingCycle；
- TrainingPlan；
- TrainingTask；
- TaskExecution；
- TrainingLog。

明确不变量：

1. Skill 是长期本体；
2. TechnicalDomain 是训练组织轴；
3. WSOS 是标准映射轴；
4. AssessmentModule 不是 TechnicalDomain；
5. Evidence 不是 Skill；
6. training completion 不是 mastery；
7. Skill 表现从真实评分结果反推；
8. 文件跟随业务；
9. 系统不自动调整计划。

## 16.3 `AGENTS.md`

删除旧规则“业务文件优先登记 ArchiveAsset”。

替换为：

> 业务文件必须由其业务 APP 拥有；跨 APP 统一的是 storage、upload、validation、cleanup 等技术能力，不建立全局泛型文件资产模型。

更新 APP 边界：standards / assessments / scoring / evidence / training / core。

写入 stable Skill、跨领域权限、Evidence 统计、人机边界等长期规则，但不要把本 Plan 全文复制进 AGENTS。

## 16.4 README

更新核心链路：

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
Skill performance
    ↓
Coach review
```

更新 APP 列表，删除 archives/events/examcontent/knowledge，加入 assessments/evidence。

## 16.5 用户手册

如已有对应手册，更新：

- 竞赛与考核页面名称；
- 资料上传入口；
- 教练训练计划/任务/评价流程；
- 选手“我的训练/执行记录/训练日志”流程。

---

# 17. Phase 13：测试矩阵

## 17.1 Standards

### stable Skill

1. 创建 Skill；
2. 创建 SkillTreeVersion V1；
3. V1 挂载 Skill；
4. 创建 V2；
5. V2 再挂同一 Skill；
6. Skill PK 不变；
7. 历史 Evidence/TrainingTask 无需重绑。

### WSOS

- 一个 Skill 映射多个 Section；
- 一个 Section 0 Skill 合法；
- 跨项目映射拒绝。

## 17.2 TechnicalDomain 权限

创建 Linux/Windows/Network coach 和 Project admin。

验证：

- Linux coach 可改 Linux Skill；
- 不可改 Windows Skill；
- admin 全部；
- cross-domain task 未显式分配 coach 时普通教练不能整体修改；
- 显式分配后可修改。

## 17.3 Assessment

覆盖：日期、module/domain project 一致、single/cross-domain module、coach assignment、document module/assessment 一致、下载权限。

## 17.4 Scoring → Evidence

完整测试：

```text
upload marking scheme
→ AssessmentDocument
→ parse
→ confirm
→ ScoringScheme
→ ScoringAspect
→ KnowledgeEvidence
```

确认不创建 ArchiveAsset，source_document/scoring_aspect/max_mark 正确。

## 17.5 Manual Test Project Evidence

```text
AssessmentDocument(TEST_PROJECT)
→ coach creates Evidence
→ approve
→ map to Skill
```

不经过 ExamPaper/ExamRequirement。

## 17.6 ScoringResult → Skill

建立 participant/aspect/evidence/multi-skill mappings/result，验证 weight 折算。

## 17.7 Training

完整测试：

```text
TrainingCycle
→ TrainingPlan
→ TrainingTask
→ Domain
→ Skill
→ Coach
→ TaskExecution
→ Attachment
→ TrainingLog
```

验证日期、skill/domain intersection、选手只能改自己的 execution、coach feedback、log 只能关联自己 execution、正式 document direct file。

## 17.8 文件

验证 invalid extension、over-size、signature mismatch、private storage、cleanup、unauthorized download、无 ArchiveAsset。

## 17.9 Migration

验证 empty DB migrate、test DB creation、无 removed-app dependency。

---

# 18. Phase 14：最终质量门禁

按仓库当前 CI 执行：

```bash
uv run ruff check .
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
uv run manage.py migrate --noinput
uv run pytest
npm run build:css
```

如果改到 FilePond 集成，再运行：

```bash
npm run test:filepond
```

不无理由升级依赖；沿用仓库 lockfile。

---

# 19. 明确不在本次重构范围

禁止范围膨胀：

- OpenAI / 其他 AI API；
- AI 自动解析试题；
- AI 自动生成 TrainingLog；
- AI 自动生成/调整 TrainingPlan；
- 自动持久化“最终技能掌握度”；
- 机器学习预测；
- 自动推荐下一项训练；
- TrainingTask 复杂权重算法；
- WSOS Communication / Work Organization 行为量表；
- 单独 Troubleshooting TechnicalDomain；
- 单独 Automation TechnicalDomain；
- 重构 feedback/forum/meetings/notices 等外围业务；
- CMP 深度集成；
- 实时消息推送；
- 全站 Dashboard 重做；
- 历史旧数据迁移；
- 旧 URL 长期兼容层。

如发现以上需求，只记录 TODO/issue，不在本 PR 实现。

---

# 20. 建议最终 APP 边界

```text
core
accounts

standards
assessments
scoring
evidence
training

glossary
worldskills_forum
feedback
notes
meetings
notices
behaviors
event_countdown
samba
...
```

| APP | 唯一主要职责 |
|---|---|
| `standards` | 项目、技术领域、稳定 Skill、技能树、WSOS |
| `assessments` | 竞赛、考核、模块、人员、原始业务资料 |
| `scoring` | 评分表结构化与评分结果 |
| `evidence` | 考点证据、Evidence→Skill 映射、考查统计 |
| `training` | 周期、计划、任务、执行、反馈、训练日志 |
| `core` | 跨业务技术能力，不拥有训练业务实体 |

---

# 21. Definition of Done

## 21.1 领域结构

- [ ] `CapabilityDomain` 删除；
- [ ] stable `Skill` 建立；
- [ ] `SkillTreeNode` 与 Skill 解耦；
- [ ] `TechnicalDomain` 成为教练与训练组织主轴；
- [ ] WSOS 独立建模并映射 Skill；
- [ ] `AssessmentModule` 可映射多个 TechnicalDomain；
- [ ] Evidence 直接映射 stable Skill；
- [ ] Plan/Task/Execution/Log 主链完整。

## 21.2 APP

- [ ] `assessments` 替代 `events`；
- [ ] `evidence` 替代 `knowledge`；
- [ ] `archives` 删除；
- [ ] `examcontent` 删除；
- [ ] INSTALLED_APPS/URLs/navigation 无旧 APP。

## 21.3 文件

- [ ] 试题/评分表属于 AssessmentDocument；
- [ ] TrainingPlan 文件属于 TrainingPlan；
- [ ] TrainingTask 文件属于 TrainingTaskAttachment；
- [ ] 训练成果属于 TaskExecutionAttachment；
- [ ] 正式训练日志属于 TrainingLog；
- [ ] core 只提供文件技术能力；
- [ ] 无新的全局泛型 FileAsset。

## 21.4 权限

- [ ] 项目管理员全局管理；
- [ ] 技术教练按 TechnicalDomain scope；
- [ ] 跨领域 Module/Task 使用显式 coach assignment；
- [ ] 选手只能维护自己的 execution/log；
- [ ] 后端有真实 query/service 权限校验。

## 21.5 闭环

- [ ] marking scheme 可导入；
- [ ] ScoringAspect 可生成 Evidence；
- [ ] Evidence 可映射 Skill；
- [ ] ScoringResult 可聚合到 Skill；
- [ ] TrainingTask 可映射 Skill；
- [ ] TaskExecution 可提供训练投入数据；
- [ ] Skill 页面可同时看到历史考查、训练投入、考核表现；
- [ ] 系统不会自动修改 TrainingPlan。

## 21.6 工程质量

- [ ] 空数据库完整 migrate；
- [ ] `makemigrations --check --dry-run` 无变化；
- [ ] `manage.py check` 通过；
- [ ] Ruff 通过；
- [ ] 全量 pytest 通过；
- [ ] Tailwind CSS build 通过；
- [ ] 无旧 runtime import/FK/URL/template reference；
- [ ] README 更新；
- [ ] CONTEXT 更新；
- [ ] AGENTS 更新。

---

# 22. Codex 最终执行顺序摘要

```text
0. 重新确认 develop HEAD、跑基线测试
1. 扫描运行时依赖和 migration graph
2. 重构 standards：
      CapabilityDomain → TechnicalDomain
      SkillNode → stable Skill + SkillTreeNode
      + WSOS
      + domain membership
3. 新建 assessments：
      Assessment / Module / Participant / Document / Coaches
4. 新建 evidence：
      KnowledgeEvidence / EvidenceSkillMap
5. 重接 scoring：
      EventModule → AssessmentModule
      ArchiveAsset → AssessmentDocument
      SkillNode → Skill
6. 重构 training：
      Cycle → Plan → Task → Execution → Log
7. 建立 domain-scope 权限 helpers
8. 完成 standards / assessments / training / scoring / evidence UI
9. 删除 archives / events / examcontent / knowledge
10. 扫描并重建受影响 migrations
11. 用真正空数据库验证完整 migrate
12. 实现第一版 Skill 闭环分析
13. 更新导航、README、CONTEXT、AGENTS、用户文档
14. 跑全量 CI 等价检查
15. 清理旧术语、旧 import、旧路由、死代码
16. 提交最终 PR
```

---

# 23. 最终业务验收场景

## 场景 A：标准

创建：

```text
SkillProject: 网络系统管理
TechnicalDomain: Linux / Windows / Network
```

创建：

```text
LINUX.DNS.AUTH  部署和配置权威 DNS 服务
NETWORK.OSPF    配置和验证 OSPF
```

创建 WSC2026 WSOS：

```text
LINUX.DNS.AUTH
→ Network and System Operations

NETWORK.OSPF
→ Data Transfer Networks
→ Troubleshooting
```

建立两个 SkillTreeVersion，确认同一 Skill 在两版保持相同身份。

## 场景 B：教练

```text
张三 → Linux
李四 → Windows
王五 → Network
```

验证张三可维护 Linux Skill、不能改 Windows Skill；项目管理员全部可管理。

## 场景 C：竞赛资料与评分

创建：

```text
Assessment: WSC2026 模拟赛 01
Module A: Linux
Coach: 张三
```

上传：

```text
Module A Marking Scheme.xlsx
Module A Test Project.pdf
```

确认：

```text
AssessmentDocument
→ ScoringScheme
→ ScoringAspect
→ KnowledgeEvidence
→ Skill
```

评分表未涵盖考点由张三从 Test Project 手工补充 Evidence。

## 场景 D：训练

```text
TrainingCycle: WSC2026 备赛
TrainingPlan: 2026年9月训练计划
TrainingTask: DNS 主从综合训练
Domain: Linux
Primary Skill: DNS 主从复制
Coach: 张三
```

分配选手，选手记录状态、实际用时、问题、解决方法、总结和附件；教练填写反馈；当天多个 Execution 关联 TrainingLog。

## 场景 E：闭环

举行训练考核：

```text
Assessment
→ ScoringResult
→ Evidence
→ Skill
```

Skill 页面同时显示：

```text
历史考查情况
近期训练投入
近期考核表现
```

教练据此**人工**创建下一阶段 TrainingTask，系统不自动生成计划。

以上 A～E 完整走通，即表示本次训练主线重构的核心业务目标达成。
