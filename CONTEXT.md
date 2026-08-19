# TMS 训练主线领域上下文

本文档定义 TMS 标准、竞赛与考核、评分、考点证据和训练主线的稳定业务语言。

## 核心链路

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

## 术语

### SkillProject（技能项目）

长期稳定的专业项目边界，例如“网络系统管理”。标准、评测和训练数据都必须归属同一技能项目。系统可显式设置至多一个启用项目为默认项目；默认值只简化新建表单选择，不覆盖编辑对象、页面业务上下文或 Service 已确定的项目归属。

### TechnicalDomain（技术领域）

训练组织与权限范围轴，例如 Linux、Windows、Network。技术领域不是比赛模块，也不是技能本体。

### TechnicalDomainMembership（技术领域成员）

用户在技术领域内的负责关系。技术教练先满足 Django action permission，再按此关系收窄对象范围；跨领域模块或任务需要显式教练分配。

### Skill（技能）

跨技能树版本长期存在的稳定技能本体。Skill 有一个主要技术领域，可关联其他技术领域；历史 Evidence、TrainingTask 和评分表现始终直接关联稳定 Skill，不随技能树换版重绑。

技能编号由数据库主键统一显示为 `SK-000123`，不由用户命名。正式名称和别名通过项目级技能称谓登记维护；同一项目内，忽略 Unicode 宽度、英文大小写和普通空格后的称谓只能属于一个 Skill。停用 Skill 仍保留其称谓和历史身份。

### SkillTreeVersion / SkillTreeNode（技能树版本/节点）

技能树版本表达某一时期的组织结构。节点分为分类、主题和技能节点；技能节点挂载稳定 Skill，同一 Skill 可以出现在多个版本中。

### WSOSVersion / WSOSSection（WSOS 版本/章节）

世界技能组织标准的版本与章节，是标准映射轴。Skill 可以映射多个 WSOSSection；WSOS 不承担训练组织权限。

### Assessment（竞赛与考核）

一次正式竞赛、选拔赛、交流赛、模拟赛、训练考核或训练测试。可绑定系列、级别和训练周期。

### AssessmentModule（评测模块）

某次 Assessment 的实际模块。模块可覆盖一个或多个 TechnicalDomain，但模块本身不是 TechnicalDomain。

### AssessmentDocument（评测资料）

Assessment 或 AssessmentModule 拥有的私有业务文件，包括试题、评分表、评分标准、评分脚本、结果文件和附件。同一上下文、资料类型和 SHA256 的重复文件拒绝保存；不同版本文件可以并存。

### KnowledgeEvidence（考点证据）

评分点、试题、评分标准、脚本检查项、CMP 结果项或人工补充形成的可审核证据。Evidence 不是 Skill；只有已批准 Evidence 进入历史考查统计。

### EvidenceSkillMap（考点技能映射）

把 Evidence 映射到稳定 Skill。单条映射权重满足 `0 < weight <= 1`，同一 Evidence 的已批准映射权重合计不超过 1；修正映射后历史统计和表现按当前映射动态重算。

### TrainingCycle（训练周期）

训练管理时间边界，可使用“总周期 → 阶段周期”两层结构，并固定一个技能树版本。

### TrainingPlan（训练计划）

周期内由教练维护的计划容器，拥有目标、日期范围和可选原始计划文件。

### TrainingTask（训练任务）

计划中的具体任务，显式关联技术领域、技能、教练和选手。发布时只为明确选择的选手创建执行记录，不自动分配全体选手。

### TaskExecution（任务执行）

某位选手对某个 TrainingTask 的执行事实，记录状态、实际用时、问题、解决方法、反思和教练反馈。任一执行开始后，任务日期、领域、技能和核心要求锁定；重大调整应取消旧任务并新建任务。

### TrainingLog（训练日志）

选手在某天、某周期提交的正式日志，可关联本人同周期且计划日期或实际执行日期覆盖当天的 TaskExecution。

## 业务不变量

1. Skill 是长期本体；技能树版本只组织 Skill。
2. TechnicalDomain 是训练组织和权限范围轴；WSOS 是标准映射轴。
3. AssessmentModule 不是 TechnicalDomain，Evidence 也不是 Skill。
4. 训练完成仅表示执行事实，不等于掌握度。
5. Skill 表现从真实 ScoringResult 经批准 Evidence/Mapping 动态反推，不持久化全局“掌握度”。
6. 历史考查只统计已批准 Evidence 与已批准 EvidenceSkillMap。
7. 业务文件由所属业务 APP 持有，`core` 只提供存储、上传校验和清理等技术能力。
8. 系统提供事实与分析，后续训练计划由教练人工判断和调整，不自动生成或改写。
9. 全系统至多一个默认 SkillProject，且默认项目必须启用；默认项目只作为新建表单的末级初始值。

## 专业词库术语

- 专业词库：技能项目下组织中英文专业词条的命名集合。
- 词条：已通过、可浏览和学习的中英文对应项。
- 词条提案：尚待审核的候选内容。
- 学习会话：学习者的一次连续答题过程。
- 作答记录：学习会话中单题的题面、答案与判定结果。
