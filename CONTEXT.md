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

### 技术领域角色范围

一个业务角色可负责一个或多个 TechnicalDomain；领域内能力与领域范围必须由同一个角色同时提供，不能把不同角色的能力和范围交叉组合。跨领域模块或任务仍需要显式教练分配。

### Skill（技能）

跨技能树版本长期存在、可具有不同粒度的稳定能力单元。Skill 有一个主要技术领域，可关联其他技术领域；它可以在技能树中作为父技能或叶子技能，是否有子技能不改变其身份。

Skill 不设置面向用户的业务编号。正式名称和别名在技能项目范围内保持唯一归属；历史 Evidence、TrainingTask 和评分表现始终直接关联稳定 Skill，不随技能树换版或结构调整重绑。停用 Skill 仍保留其称谓和历史身份。

技能库是一个技能项目下长期 Skill 的集合，不是独立日常维护页面。日常标准维护从当前标准技能树进入；尚未纳入当前树的 Skill 仍保留在技能库中，可由其主要技术领域重新挂载。

### SkillTreeVersion / SkillTreeNode（技能树版本/节点）

技能树版本属于一个明确的 TechnicalDomain，表达该领域某一时期 Skill 的组织结构。每个节点只表示一个稳定 Skill 在该版本中的位置、父子关系和顺序；节点的技术领域由所属版本唯一确定，所有节点都关联 Skill，树不限固定层级，不存在分类、主题或分组节点类型。

树父子关系只表达组织与细化，不自动产生评分、掌握度或 Skill 属性的汇总与继承。同一 Skill 在同一技能树版本中只出现一次，但可以出现在不同版本中。

每个技术领域独立维护至多一个当前技能树，领域换版不要求同项目其他领域同步换版。新版本可基于本领域当前版本、任意历史版本或空白结构创建；`based_on` 只记录不可变的来源关系，克隆复用长期 Skill，仅复制节点结构。创建新版本不会自动设为当前版本，也不会修改既有训练周期的版本快照。

### WSOSVersion / WSOSSection（WSOS 版本/章节）

世界技能组织标准的版本与章节，是 SkillProject 级标准映射轴；当前建模粒度止于 WSOSSection，不建立 WSOSItem。Skill 与 WSOSSection 是多对多关系，映射可记录备注；WSOS 不直接归属 TechnicalDomain，也不承担训练组织权限。

### Assessment（竞赛与考核）

一次正式竞赛、选拔赛、交流赛、模拟赛、训练考核或训练测试。可绑定系列、级别和训练周期。

### AssessmentModule（评测模块）

某次 Assessment 的实际模块。模块可覆盖一个或多个 TechnicalDomain，但模块本身不是 TechnicalDomain。

### CompetitionPerson / CompetitionRole（长期赛事人员/赛事角色）

CompetitionPerson 是不可登录、可跨届复用的轻量赛事人员目录；CompetitionRole 是使用稳定代码和类别表达机器语义的可配置赛事角色。两者都不替代 Django User 或 Django Permission。

### AssessmentParticipant（评测参与人员）

某个人在单场 Assessment 中的历史人员快照，可来源于 User、CompetitionPerson 或临时录入。只有角色类别为 COMPETITOR 的参与人员可以产生 ScoringResult 和最终结果；后续修改 User 或长期人员目录不得改写既有比赛快照。

### AssessmentDocument（评测资料）

Assessment 或 AssessmentModule 拥有的私有业务文件，包括试题、评分表、评分标准、评分脚本、结果文件和附件。同一上下文、资料类型和 SHA256 的重复文件拒绝保存；不同版本文件可以并存。

### KnowledgeEvidence（考点证据）

评分点、试题、评分标准、脚本检查项、CMP 结果项或人工补充形成的可审核证据。Evidence 不是 Skill；只有已批准 Evidence 进入历史考查统计。

### EvidenceSkillMap（考点技能映射）

把 Evidence 映射到稳定 Skill。单条映射权重满足 `0 < weight <= 1`，同一 Evidence 的已批准映射权重合计不超过 1；修正映射后历史统计和表现按当前映射动态重算。

### ScoringResult / AssessmentFinalResult（评分点结果/官方最终结果）

ScoringResult 是某位选手在某个 ScoringAspect 上的统一评分事实，在线录入和外部导入使用同一结构。AssessmentFinalResult 是经确认的整场官方结果，可拥有多种 AssessmentFinalScore 表示和多个 AssessmentAward；实时汇总不能自动成为官方结果。

### TrainingCycle（训练周期）

训练管理时间边界，可使用“总周期 → 阶段周期”两层结构。周期至少固定一个技术领域的具体技能树版本，同一领域最多一个版本；阶段周期的领域必须是父周期领域的子集，但可选用不同历史版本。版本快照只在筹备中且尚无已开始执行时可编辑，之后保持不变。

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
10. 删除 SkillTreeNode 只移除某个版本中的树位置，不删除长期 Skill。
11. Skill 名称属于长期 Skill，不做节点级名称快照；改名会反映到引用它的所有技能树版本。
12. Skill 的主要或关联技术领域不得被修改为与任何既有树位置冲突；应先移动或移除对应树位置。
13. SkillTreeVersion 只属于一个 TechnicalDomain；SkillTreeNode 不单独持久化技术领域，也不能跨版本移动。
14. TrainingCycle 至少绑定一个领域版本；TrainingTask 的技术领域必须是其周期已绑定领域的子集。
15. 训练周期状态只允许按“筹备中 → 进行中 → 已完成 → 已归档”前进，不能跳级或回退。
16. ScoringResult 与 AssessmentFinalResult 只能关联同一 Assessment 内的 COMPETITOR 类参与人员。
17. 最终名次、成绩表示和奖项相互独立；一名选手可以拥有多个成绩表示和多个奖项。

## 专业词库术语

- 专业词库：技能项目下组织中英文专业词条的命名集合。
- 词条：已通过、可浏览和学习的中英文对应项。
- 词条提案：尚待审核的候选内容。
- 学习会话：学习者的一次连续答题过程。
- 作答记录：学习会话中单题的题面、答案与判定结果。
