# TMS 世界技能大赛网络系统管理项目训练体系设计方案

> 文档性质：业务与系统设计方案  
> 适用项目：世界技能大赛网络系统管理（IT Network Systems Administration）  
> 载体系统：TMS（Training Management System）  
> 当前阶段：训练体系主线设计确认稿  
> 日期：2026-08-17

---

## 1. 文档目的

本方案用于明确世界技能大赛网络系统管理项目的训练体系，以及 TMS 在整个训练体系中的定位、核心业务对象、数据关系和工作闭环。

本方案首先解决“训练体系应该如何建立”这一业务问题，再据此指导 TMS 后续重构。

本方案不是代码实施计划，不规定具体迁移步骤、开发任务拆分、页面组件实现或数据库迁移顺序。待本方案确认后，再单独制定可供 Codex 执行的重构实施 Plan。

---

## 2. 设计范围

本方案只讨论 TMS 的竞赛训练主线，包括：

- 项目技能标准体系；
- 技术领域与教练职责划分；
- WSOS 标准映射；
- 历届竞赛、考核、模拟赛、交流赛资料沉淀；
- 评分表和考点提取；
- 技能与考点映射；
- 训练周期、训练计划和训练任务；
- 选手训练执行记录；
- 教练评价与反馈；
- 训练日志；
- 考核与评分结果；
- 技能表现分析；
- 教练人工复盘和调整后续训练计划。

以下功能虽然属于 TMS，但不属于本次训练主线设计范围：

- 通知公告；
- 意见反馈；
- WorldSkills 论坛翻译；
- 会议管理；
- 奖惩管理；
- 专业词库；
- 倒计时；
- 其他行政或辅助功能。

这些功能以后可以围绕训练主线建立关联，但不应反过来影响训练核心模型。

---

## 3. TMS 的核心定位

TMS 不应只是一个文件归档系统、训练日志提交系统或竞赛成绩管理系统。

TMS 的核心定位应当是：

> **以标准技能体系为核心，将历届竞赛与考核资料沉淀为技能证据，将训练计划分解为与技能关联的训练任务，记录选手训练执行过程，并通过竞赛和考核评分结果持续分析选手技能表现，为教练人工调整后续训练提供依据，从而形成“标准—证据—训练—评测—调整”的闭环训练体系。**

TMS 的作用是：

1. 统一训练标准；
2. 沉淀历史竞赛知识；
3. 组织训练活动；
4. 记录真实训练过程；
5. 分析选手技能表现；
6. 为教练决策提供证据。

TMS **不是自动教练系统**。

训练计划是否调整、下一阶段重点训练什么、选手是否真正掌握某项技能，最终仍由教练结合系统数据进行判断。

---

# 第一部分：训练体系总体框架

## 4. 整体业务闭环

整个训练体系可以分为五个核心环节：

```text
标准
  ↓
证据
  ↓
训练
  ↓
评测
  ↓
调整
  ↺
```

展开后：

```text
                       ┌────────── 长期知识沉淀 ──────────┐
                       │                                  │
WorldSkills WSOS ──→ 标准体系 ←── 历届竞赛 / 考核 / 测试
                       ↑                  ↓
                       │          试题、评分表、评分脚本
                       │                  ↓
                       │        评分点 / 人工补充考点
                       │                  ↓
                       └────────── 技能证据映射 ──────────┘
                                          ↓
                              历史频次 / 分值 / 覆盖分析

─────────────────────── 训练执行闭环 ───────────────────────

标准技能体系 + 历史考查情况 + 选手当前表现
                    ↓
                 教练判断
                    ↓
训练周期 → 训练计划 → 训练任务 → 选手执行记录
              ↑                    ↓
              │               问题 / 总结 / 反馈
              │                    ↓
              │                 训练日志
              │
              └──── 考核 / 模拟赛 / 选拔赛 / 交流赛
                                  ↓
                               评分结果
                                  ↓
                              技能表现分析
                                  ↓
                              教练人工复盘
                                  ↓
                           调整下一阶段训练计划
```

所有关键数据最终都围绕 **Skill（技能）** 建立关联。

---

# 第二部分：标准体系

## 5. 标准体系不能只来自历届试题

网络系统管理项目的技能体系不能简单通过历届试题和评分表反向归纳。

技能体系应有三个主要来源：

### 5.1 WorldSkills WSOS

WSOS 用于回答：

> 网络系统管理项目整体应该具备哪些能力？

它是项目标准体系的官方依据。

### 5.2 历届比赛、考核和测试

包括：

- 世界技能大赛；
- 全国技能大赛；
- 省级竞赛；
- 国家集训队选拔；
- 国际交流赛；
- 校内或基地模拟赛；
- 日常阶段考核；
- 训练测试。

这些资料用于回答：

> 实际比赛中考过什么？  
> 怎样考？  
> 出现多少次？  
> 占多少分？  
> 最近是否频繁出现？

### 5.3 教练经验

评分表不能覆盖所有真正需要训练的内容，试题中也可能存在没有独立评分项但实际必须掌握的技术要求。

因此教练必须可以：

- 手工补充技能；
- 手工补充考点；
- 修正自动提取结果；
- 调整技能分类；
- 调整训练重点。

最终形成：

> **WSOS 给出项目标准框架，历届竞赛资料提供真实考查证据，教练负责技术细化和训练决策。**

---

# 第三部分：技术领域与 WSOS 的双维度设计

## 6. 为什么不能直接按 WSOS 组织训练

WSOS 是面向整个职业项目的能力标准，但它并不完全适合训练工作的日常组织。

例如：

- Communication and interpersonal skills 很难直接成为某一项客观技术考点；
- Network and System Operations 同时覆盖 Linux 和 Windows；
- Infrastructure Automation 可以出现在 Linux、Windows、Network 多个比赛模块；
- Troubleshooting 本身往往需要跨多个技术领域联合完成。

而实际训练团队通常按照长期技术专长分工，例如：

- Linux 教练；
- Windows 教练；
- Network/Cisco 教练。

因此 TMS 必须明确区分：

1. **训练组织维度**；
2. **WSOS 标准维度**。

两者是正交关系，不能混为一套分类。

---

## 7. TechnicalDomain：技术领域

### 7.1 定义

技术领域用于表达网络系统管理项目中长期稳定、适合训练组织和教练职责划分的技术分区。

建议网络系统管理项目的一级技术领域为：

```text
网络系统管理
├── Linux
├── Windows
└── Network
```

中文界面可显示为：

- Linux 系统；
- Windows 系统；
- 网络技术。

### 7.2 TechnicalDomain 的主要作用

TechnicalDomain 用于决定：

- Skill 主要归属哪个领域；
- 哪位技术教练负责维护 Skill；
- 哪位教练负责对应训练任务；
- 哪位教练负责相应考核模块；
- 哪位教练负责评分结果分析；
- 哪位教练负责训练评价和反馈；
- 页面和权限的数据范围。

因此：

> **TechnicalDomain 是 TMS 日常训练管理的主要组织轴。**

---

## 8. WSOSSection：WSOS 能力维度

WSOS 应作为另一套标准映射体系存在。

例如：

- Work organization and management；
- Communication and interpersonal skills；
- Data Transfer Networks；
- Network and System Operations；
- Infrastructure Automation；
- Troubleshooting。

它主要回答：

> 某个 Skill 对应 WSOS 的哪些能力要求？  
> 当前技能体系对 WSOS 的覆盖情况如何？  
> 历届竞赛实际覆盖哪些 WSOS 能力？  
> Automation 和 Troubleshooting 分别在 Linux、Windows、Network 中如何体现？

WSOS **不直接决定教练职责，也不直接作为日常训练任务一级目录**。

---

## 9. TechnicalDomain 与 WSOSSection 的关系

同一个 Skill 同时可以属于一个技术领域，并映射一个或多个 WSOS 能力维度。

例如：

| Skill | TechnicalDomain | WSOS |
|---|---|---|
| 配置 BIND 权威 DNS | Linux | Network and System Operations |
| 配置 AD DNS | Windows | Network and System Operations |
| 配置 OSPF | Network | Data Transfer Networks |
| Bash 批量部署账户 | Linux | Infrastructure Automation |
| PowerShell 批量配置 AD | Windows | Infrastructure Automation |
| Python/API 自动配置网络设备 | Network | Infrastructure Automation |
| 排查 BIND 区域传送故障 | Linux | Troubleshooting / Network and System Operations |
| 排查 AD 复制故障 | Windows | Troubleshooting / Network and System Operations |
| 排查 OSPF 邻接失败 | Network | Troubleshooting / Data Transfer Networks |

因此：

```text
训练组织视角：
Linux / Windows / Network

项目标准视角：
WSOS Sections
```

这两种视角同时存在，但互不替代。

---

# 第四部分：Skill——整个训练体系的核心对象

## 10. Skill 的定义

Skill 表示：

> **可以训练、实践、评价并长期追踪的具体技术能力。**

例如：

- 部署和配置权威 DNS；
- 配置 DNS 主从复制；
- 配置 DNSSEC；
- 配置 Active Directory 域服务；
- 配置组策略；
- 配置 OSPF；
- 配置 BGP；
- 配置 IPsec VPN；
- 使用 PowerShell 完成批量配置；
- 排查 OSPF 邻接故障。

Skill 不等同于某一次比赛的评分点。

Skill 是长期稳定的能力本体。

---

## 11. Skill 必须与技能树版本解耦

Skill 本身应该长期稳定。

例如：

```text
LINUX.DNS.AUTH
部署和配置权威 DNS 服务
```

即使未来：

- WSOS 分类变化；
- 技能树层级变化；
- 名称轻微调整；
- 某项技能从一个主题移动到另一个主题；

历史训练、考核、评分数据仍然应该继续指向同一个 Skill。

因此不建议让 Skill 本身成为某个 `SkillTreeVersion` 下临时存在的节点。

应区分：

```text
Skill
= 长期稳定的技能身份

SkillTreeVersion
= 某一版本的技能体系

SkillTreeNode
= Skill 在某一版本技能树中的位置
```

关系类似：

```text
SkillProject
│
├── TechnicalDomain
│
├── Skill
│
└── SkillTreeVersion
      ↓
   SkillTreeNode
      ↓
     Skill
```

---

## 12. Skill 的技术领域归属

绝大多数 Skill 应有一个明确的主要技术领域：

```text
Skill.primary_domain
```

例如：

```text
LINUX.DNS.AUTH
primary_domain = Linux
```

```text
WINDOWS.AD.GPO
primary_domain = Windows
```

```text
NETWORK.OSPF
primary_domain = Network
```

如果确实存在跨领域技能，可以增加关联领域，但应遵循：

> 每个 Skill 有且只有一个主要技术领域，可以有若干关联技术领域。

第一阶段应尽量避免大量跨领域 Skill，以防技能责任边界重新变得模糊。

---

## 13. Automation 不单独成为技术领域

Infrastructure Automation 是 WSOS 能力维度，不应成为与 Linux、Windows、Network 平行的第四个 TechnicalDomain。

自动化应该融入三个技术领域内部：

```text
Linux
└── Automation
    ├── Bash
    ├── Python
    └── Ansible

Windows
└── Automation
    └── PowerShell

Network
└── Automation
    ├── Python
    ├── API
    └── Network Automation
```

这些 Skill 可以同时映射 WSOS：

```text
Infrastructure Automation
```

---

## 14. Troubleshooting 不单独成为技术领域

Troubleshooting 同样属于横向能力。

### 14.1 领域内故障排查

例如：

- Linux DNS 故障排查；
- Windows AD 故障排查；
- Network OSPF 故障排查。

这些 Skill 仍归对应 TechnicalDomain。

### 14.2 跨领域综合故障排查

例如一个问题可能涉及：

```text
Network VLAN / Routing
        ↓
Linux DNS
        ↓
Windows AD
        ↓
Linux Web
```

这种情况不应为了它建立一个单独的 Troubleshooting 技术领域。

更合理的方式是：

> **让 TrainingTask、AssessmentModule 或综合场景同时关联多个 TechnicalDomain 和多个 Skill。**

因此：

> 跨领域的通常是“训练任务、考核场景和比赛模块”，而不一定是 Skill 本体。

---

# 第五部分：技能树

## 15. 技能树按 TechnicalDomain 组织

TMS 中供教练和选手浏览的技能树应主要按技术领域组织，例如：

```text
网络系统管理
│
├── Linux
│   ├── 基础系统管理
│   ├── Storage
│   ├── DNS
│   │   ├── 权威 DNS
│   │   ├── 主从复制
│   │   ├── DNSSEC
│   │   └── 故障排查
│   ├── DHCP
│   ├── Mail
│   ├── Web
│   ├── PKI
│   ├── Security
│   └── Automation
│
├── Windows
│   ├── AD DS
│   ├── DNS
│   ├── DHCP
│   ├── PKI
│   ├── File Services
│   ├── GPO
│   ├── PowerShell
│   └── Troubleshooting
│
└── Network
    ├── Switching
    ├── Routing
    ├── OSPF
    ├── BGP
    ├── VPN
    ├── Security
    ├── Automation
    └── Troubleshooting
```

具体层级以后可以随着训练实践调整。

技能树是组织和浏览结构，而 Skill 是长期分析对象。

---

# 第六部分：教练职责与权限

## 16. 教练职责按 TechnicalDomain 划分

例如：

```text
张三 → Linux
李四 → Windows
王五 → Network
```

每位技术教练主要负责自己领域中的：

- Skill 维护；
- 历届比赛资料整理；
- 评分表确认；
- 考点映射；
- 训练任务制定；
- 选手训练评价；
- 领域内考核；
- 评分结果分析；
- 技能薄弱点判断。

项目负责人可以查看和管理整个项目。

---

## 17. 权限分为“角色权限”和“领域范围”

### 17.1 全局角色权限

继续使用 Django 原生 Group / Permission 表达：

- 项目管理员；
- 技术教练；
- 选手；
- 其他角色。

它回答：

> 用户能不能执行某类操作？

例如：

- 能否维护 Skill；
- 能否制定训练任务；
- 能否导入评分表；
- 能否查看全部评分结果。

### 17.2 TechnicalDomainMembership

再通过技术领域成员关系表达：

> 用户可以在哪些技术领域执行这些操作？

例如：

```text
张三
domain = Linux
role = LEAD_COACH

李四
domain = Windows
role = LEAD_COACH

王五
domain = Network
role = LEAD_COACH
```

项目管理员可以拥有全局管理能力，无须逐个领域绑定。

这样最终形成：

```text
“能否执行该操作”
+
“是否负责该技术领域”
```

两层权限控制。

---

# 第七部分：竞赛、考核和历史资料沉淀

## 18. 竞赛、考核、模拟赛和训练测试属于同一评测体系

从训练主线看：

- 正式竞赛；
- 选拔赛；
- 模拟赛；
- 交流赛；
- 阶段考核；
- 训练测试；

虽然名称不同，但共同特点是：

> 它们都可以用于评价选手的技术表现。

因此 TMS 可以统一抽象为一个评测类领域对象。

中文界面建议使用：

> **竞赛与考核**

内部模型以后可考虑使用：

```text
Assessment
AssessmentModule
AssessmentParticipant
AssessmentDocument
```

是否最终沿用 `Event` 命名可在重构实施阶段决定，但从业务语言上更推荐“竞赛与考核”。

---

## 19. AssessmentModule 与 TechnicalDomain 是映射关系

某届比赛的 Module A/B/C/D 不是长期技术领域。

例如：

```text
Module A → Linux
Module B → Windows
Module C → Network
```

但未来也可能存在：

```text
Module D → Linux + Windows + Network
```

所以：

```text
AssessmentModule
↕
TechnicalDomain
```

应是映射关系。

这保证比赛模块调整不会破坏长期技能体系。

---

# 第八部分：文件与业务对象

## 20. 文件必须跟随业务，而不是成为独立业务中心

TMS 不应将“所有文件”统一抽象成一个全局资料资产中心。

正确原则是：

> **业务对象拥有文件，而不是文件再去寻找业务对象。**

例如：

```text
Assessment
└── AssessmentDocument

TrainingPlan
└── 原始计划文件

TrainingTask
└── 训练任务附件

TaskExecution
└── 训练成果和截图

TrainingLog
└── 正式训练日志文件

Meeting
└── 会议记录文件
```

因此当前独立 `archives` APP 后续可以考虑删除。

---

## 21. 保留统一文件技术能力

删除独立文件业务模型，并不意味着各 APP 重复实现上传。

全站仍然应该在 `core` 中统一提供：

- PrivateMediaStorage；
- UploadSpec；
- 文件类型限制；
- 文件大小限制；
- 文件签名校验；
- 文件清理；
- 文件下载；
- 文件图标；
- 上传组件；
- 通用附件展示组件。

原则是：

> **统一文件处理技术，分散文件业务归属。**

---

# 第九部分：试题、评分表与考点证据

## 22. 现阶段主要结构化评分表

当前阶段优先处理格式规范的评分表。

流程：

```text
AssessmentModule
      ↓
AssessmentDocument(MARKING_SCHEME)
      ↓
评分表解析
      ↓
ScoringScheme
      ↓
ScoringAspect
      ↓
KnowledgeEvidence
      ↓
Skill
```

评分点可以自动形成考点证据。

---

## 23. 试题现阶段主要作为原始资料保存

试题中的描述性内容难以完全依赖普通规则解析。

现阶段：

```text
AssessmentDocument(TEST_PROJECT)
```

负责保存试题原文件。

教练可以根据试题内容：

- 手工增加 KnowledgeEvidence；
- 补充评分表未明确体现的考点；
- 映射到 Skill。

未来引入 AI 后，可以再增加：

```text
试题
↓
AI 解析
↓
结构化试题要求
↓
KnowledgeEvidence
```

因此现阶段不必为了未来 AI 过度设计完整的试题结构化领域。

---

# 第十部分：KnowledgeEvidence——竞赛资料与 Skill 之间的桥梁

## 24. KnowledgeEvidence 的作用

KnowledgeEvidence 表示：

> 某次竞赛、考核、试题、评分表或教练判断证明“某项技能曾经被考查”的证据。

来源可以包括：

- 评分点；
- 试题要求；
- 评分标准；
- 自动评分脚本检查项；
- CMP 回传评分项；
- 教练人工补充；
- 未来 AI 提取结果。

---

## 25. 一个评分点不能直接等于一个 Skill

例如历届比赛中可能出现：

```text
Configure DNS master server
Configure BIND authoritative DNS
Implement primary DNS service
Deploy shanghai.cn DNS service
```

这些不同表述最终可能都对应：

```text
LINUX.DNS.AUTH
部署和配置权威 DNS 服务
```

因此：

```text
评分点
↓
KnowledgeEvidence
↓
Skill
```

而不是：

```text
评分点
=
Skill
```

这样 TMS 才能长期统计：

- Skill 出现过多少次；
- 出现在哪些比赛；
- 累计分值；
- 最近出现频率；
- 不同级别比赛中的权重；
- 哪些选手经常在该 Skill 失分。

---

# 第十一部分：训练周期

## 26. TrainingCycle

TrainingCycle 表示一段训练管理时间范围。

例如：

```text
WSC2026 两年备赛周期
```

可以再包含阶段周期：

```text
WSC2026 备赛周期
├── 基础训练阶段
├── 省选备战阶段
├── 国选备战阶段
├── 国家集训阶段
└── 世赛冲刺阶段
```

因此 TrainingCycle 可以允许父子关系。

第一阶段只需要支持：

```text
总周期
  → 阶段周期
```

两级即可，不必设计无限层级。

---

## 27. TrainingCycle 与标准版本

一个 TrainingCycle 应固定采用某个技能树版本。

这样即使以后标准升级，历史训练仍然可以明确：

> 当时按照哪一版技能体系开展训练。

---

# 第十二部分：训练计划

## 28. TrainingPlan

TrainingPlan 表示一个 TrainingCycle 中某一时间范围的训练安排。

例如：

- 月计划；
- 周计划；
- 冲刺阶段计划；
- 专项训练计划。

不需要分别建立：

```text
MonthlyPlan
WeeklyPlan
DailyPlan
```

TrainingPlan 只需要：

```text
开始日期
结束日期
目标
状态
原始计划文件（可选）
```

月计划、周计划只是不同时间跨度。

---

## 29. 原始月计划文件继续保留

现有 Excel / Word 月训练计划仍可以继续使用。

但它应该成为：

```text
TrainingPlan.source_file
```

或计划附件。

文件是计划的原始载体和归档资料，但系统真正用于统计和分析的是 TrainingTask。

原则：

> **计划文件是附件，TrainingTask 才是结构化训练数据。**

---

# 第十三部分：训练任务

## 30. TrainingTask 是训练执行核心

TrainingTask 是真正可执行的训练单元。

例如：

```text
9月1日
部署 BIND 权威 DNS

9月2日
配置 DNS 主从复制

9月3日
配置 DNSSEC

9月4日
DNS 综合故障排查
```

TrainingTask 至少应包含：

- 训练计划；
- 计划日期；
- 标题；
- 训练要求；
- 预计用时；
- 优先级；
- 相关资料；
- 负责教练；
- TechnicalDomain；
- Skill。

---

## 31. TrainingTask 与 Skill

一个 TrainingTask 可以关联多个 Skill。

第一阶段建议只区分：

```text
PRIMARY
RELATED
```

例如：

```text
DNS综合训练

PRIMARY
- DNS 主从复制

RELATED
- Linux 服务管理
- 防火墙配置
- 故障排查
```

暂时不需要复杂权重。

---

## 32. TrainingTask 可以跨 TechnicalDomain

例如：

```text
综合故障排查训练
```

可以涉及：

- Linux；
- Windows；
- Network。

并同时关联：

- 多个 Skill；
- 多位教练。

因此：

> TrainingTask 可以跨领域，Skill 原则上仍有明确主要领域。

---

# 第十四部分：选手训练执行

## 33. TaskExecution

TaskExecution 表示：

> 某个选手执行某项 TrainingTask 的真实记录。

它同时承担：

- 任务分配状态；
- 实际执行过程；
- 选手反馈；
- 教练反馈。

建议状态：

```text
ASSIGNED
IN_PROGRESS
COMPLETED
PARTIALLY_COMPLETED
BLOCKED
CANCELLED
```

主要记录：

- 选手；
- TrainingTask；
- 状态；
- 开始时间；
- 完成时间；
- 实际训练时长；
- 完成情况；
- 遇到的问题；
- 问题是否解决；
- 解决方法；
- 个人总结；
- 教练评价；
- 教练反馈。

---

## 34. 训练执行附件

如果训练过程中产生：

- 截图；
- 配置文件；
- 网络拓扑；
- 实验报告；
- 故障分析报告；
- 导出结果；
- 其他成果；

应绑定：

```text
TaskExecutionAttachment
```

而不是绑定到一个全局 ArchiveAsset。

---

# 第十五部分：训练日志

## 35. 训练日志不再是原始数据入口

训练日志应该是：

> 对当天或阶段内真实训练事实的正式汇总。

原始事实来自：

```text
TaskExecution
```

例如：

```text
任务 A
完成
120 分钟
问题：zone transfer 失败
原因：ACL 错误

任务 B
部分完成
90 分钟
问题：DNSSEC 信任链理解不清楚
```

TrainingLog 将这些事实汇总为正式日志。

---

## 36. 未来 AI 生成训练日志

未来引入 AI 后：

```text
TaskExecution × N
+ 教练反馈
        ↓
AI 整理
        ↓
TrainingLog 草稿
        ↓
选手 / 教练确认
        ↓
正式训练日志
```

AI 的职责是：

> **整理真实结构化事实，而不是创造训练事实。**

这样可以显著减少选手和教练重复撰写文字材料的时间。

---

# 第十六部分：评测与评分

## 37. 考核是技能掌握情况的主要检验方式

训练完成情况不能直接等于技能掌握情况。

必须区分：

### 训练进度

回答：

> 安排了什么？  
> 完成了什么？  
> 练了多少？  
> 投入多少时间？

来源：

```text
TrainingTask
TaskExecution
```

### 技能表现

回答：

> 在真实考核中得了多少分？  
> 哪些 Skill 失分？  
> 表现趋势怎样？

来源：

```text
ScoringResult
↓
ScoringAspect
↓
KnowledgeEvidence
↓
Skill
```

---

# 第十七部分：Skill 作为训练和评测的统一连接点

## 38. 训练侧

```text
TrainingTask
    ↓
Skill
```

可以统计：

- 最近是否安排训练；
- 训练次数；
- 实际训练时长；
- 完成率；
- 常见问题；
- 教练反馈。

---

## 39. 评测侧

```text
ScoringResult
    ↓
KnowledgeEvidence
    ↓
Skill
```

可以统计：

- 得分率；
- 失分率；
- 最近表现；
- 多次考核趋势；
- 重复失分情况。

---

## 40. Skill 分析页面

最终每个 Skill 可以形成类似以下分析：

```text
DNS 主从复制

所属领域：
Linux

WSOS：
Network and System Operations
Troubleshooting

历史考查：
- 出现 8 次
- 累计 46 分
- 最近 3 届出现 2 次

近期训练：
- 过去 30 天安排 4 次
- 实际训练 9.5 小时
- 主要问题 3 个

近期考核：
- 92%
- 68%
- 75%

常见问题：
- zone transfer
- notify
- ACL

教练判断：
人工填写

下一步训练：
由教练人工调整计划
```

---

# 第十八部分：训练重点与薄弱点

## 41. “重要”与“薄弱”必须分开

一个 Skill 可以：

- 很重要，但选手已经掌握很好；
- 不属于最高权重技能，但选手明显薄弱。

因此至少需要两个不同概念。

### 训练重要度

可以参考：

- WSOS 标准；
- 历史出现次数；
- 累计分值；
- 赛事级别；
- 最近出现情况；
- 教练判断。

### 当前薄弱度

可以参考：

- 个人得分率；
- 多次考核失分率；
- 最近趋势；
- 重复失分；
- 训练过程中反复出现的问题；
- 教练评价。

系统负责提供证据。

最终训练优先级仍由教练决定。

---

# 第十九部分：系统不自动生成训练计划

## 42. 明确的人机边界

TMS 不应根据评分结果自动修改训练计划。

也不应简单使用一个公式自动认定：

```text
Skill 掌握度 = 75%
```

正确流程：

```text
历史竞赛数据
+
训练执行数据
+
最近考核表现
+
WSOS 标准
+
下一阶段比赛特点
        ↓
系统展示分析证据
        ↓
教练判断
        ↓
人工创建或调整 TrainingPlan / TrainingTask
```

这符合竞技训练的实际规律，也保留了技术教练的专业判断。

---

# 第二十部分：建议的核心领域结构

## 43. 主干 APP 建议

后续 TMS 重构时，可围绕以下核心领域进行组织。

### standards

负责：

- SkillProject；
- TechnicalDomain；
- Skill；
- SkillTreeVersion；
- SkillTreeNode；
- WSOSVersion；
- WSOSSection；
- Skill 与 WSOS 映射；
- TechnicalDomainMembership。

### assessments

负责：

- 正式竞赛；
- 选拔赛；
- 交流赛；
- 模拟赛；
- 阶段考核；
- 训练测试；
- AssessmentModule；
- AssessmentParticipant；
- AssessmentDocument；
- 模块与 TechnicalDomain 映射；
- 模块教练责任。

### scoring

负责：

- 评分表解析；
- ScoringScheme；
- ScoringAspect；
- ScoringParticipant；
- ScoringResult；
- 评分结果导入。

### evidence

负责：

- KnowledgeEvidence；
- EvidenceSkillMap；
- 历史考点统计；
- Skill 历史考查分析。

### training

负责：

- TrainingCycle；
- TrainingPlan；
- TrainingTask；
- TrainingTaskSkill；
- TrainingTaskCoach；
- TaskExecution；
- TaskExecutionAttachment；
- TrainingLog。

### core

只负责真正的跨业务技术能力：

- 私有文件存储；
- 文件上传；
- 文件校验；
- 文件清理；
- 权限公共工具；
- 通用列表筛选；
- HTMX 公共组件；
- 通用模板组件；
- 其他基础能力。

---

# 第二十一部分：建议删除或重新定位的现有设计

## 44. archives

建议后续删除独立 `archives` APP。

原因：

- 文件天然属于具体业务；
- 全局文件资产容易产生业务归属模糊；
- GenericForeignKey 会增加业务查询复杂度；
- 用户真实操作路径通常都是从业务页面上传文件。

需要保留的是 `core` 中的统一文件技术能力。

---

## 45. examcontent

现阶段可以考虑删除独立 `examcontent` APP。

原因：

- 当前主要结构化对象是评分表；
- 试题暂时以原始文件为主；
- 未引入 AI 前，教练可直接手工补充 KnowledgeEvidence；
- 没必要为了未来能力提前长期维护复杂的试题结构化模型。

未来真正需要 AI 解析试题时，再根据实际需求决定是否新增专门领域。

---

## 46. events

现有 `events` 的业务语义偏泛。

后续可考虑重构为：

```text
assessments
```

使其更加贴近：

> 竞赛与考核

这个真正的训练主线语义。

最终是否改名，可以在重构 Plan 阶段根据代码影响范围决定。

---

# 第二十二部分：TMS 两种核心使用视角

## 47. 技术教练视角

主要按 TechnicalDomain 工作。

例如 Linux 教练看到：

```text
Linux

我的 Skill
我的训练任务
我的考核模块
待确认评分表
待映射考点
选手 Linux 表现
最近失分 Skill
待评价 TaskExecution
```

它回答的是：

> 我负责什么？  
> 今天要做什么？  
> 选手最近哪里存在问题？  
> 下一阶段要练什么？

---

## 48. 项目负责人视角

项目负责人可以跨领域查看：

```text
Linux
Windows
Network
```

并同时查看 WSOS 维度：

```text
Data Transfer Networks
Network and System Operations
Infrastructure Automation
Troubleshooting
...
```

可以回答：

> 整个项目技能体系是否完整？  
> WSOS 覆盖是否合理？  
> 三个领域训练是否平衡？  
> Automation 在三个领域分别训练到什么程度？  
> Troubleshooting 是否得到足够训练？  
> 哪些 Skill 是项目整体薄弱点？  
> 各教练负责领域的训练执行情况如何？

---

# 第二十三部分：最终训练体系定义

## 49. 一句话定义

> **TMS 以长期稳定的 Skill 为核心，以 Linux、Windows、Network 等 TechnicalDomain 组织教练职责和训练工作，以 WSOS 作为项目标准映射维度；通过历届竞赛、考核和评分表沉淀 Skill 的考查证据，通过训练周期、训练计划、训练任务和 TaskExecution 记录训练事实，再通过考核评分结果评价选手 Skill 表现，最终由教练依据系统分析人工调整下一阶段训练计划，形成持续迭代的闭环训练体系。**

---

## 50. 最核心的设计原则

后续任何重构或新功能，都应遵循以下原则：

1. **Skill 是长期稳定的核心业务对象。**
2. **TechnicalDomain 是训练组织和教练职责的主轴。**
3. **WSOS 是标准映射维度，不直接承担训练组织职责。**
4. **比赛模块是临时结构，不能代替长期 TechnicalDomain。**
5. **评分点是考点证据，不等于 Skill。**
6. **训练任务必须能够关联 Skill。**
7. **训练完成情况不等于技能掌握情况。**
8. **技能表现主要通过真实考核和评分结果反推。**
9. **系统提供分析证据，不替代教练专业判断。**
10. **训练计划由教练人工制定和调整，不自动生成。**
11. **AI 主要用于信息提取、整理和文字生成，不负责创造训练事实。**
12. **文件始终跟随业务对象，统一的是文件处理技术，而不是文件业务模型。**
13. **技术领域内部应尽量保持清晰责任边界，跨领域协作通过任务、模块和场景表达。**
14. **历史数据必须能够长期追踪到稳定 Skill，不能因为技能树版本更新而失去连续性。**
15. **先保证训练主干稳定，再在其外围建设通知、反馈、论坛、会议等扩展功能。**

---

# 结语

本方案的核心不是重新设计一套复杂的软件模型，而是先把网络系统管理项目真实的训练规律表达清楚。

最终 TMS 应当能够让所有参与者围绕同一套 Skill 体系工作：

```text
项目负责人
    ↓
TechnicalDomain
    ↓
技术教练
    ↓
Skill
    ↓
训练任务
    ↓
选手训练
    ↓
竞赛 / 考核
    ↓
Skill 表现
    ↓
教练复盘
    ↓
下一阶段训练
```

同时从另一条标准维度：

```text
WorldSkills WSOS
      ↓
WSOSSection
      ↕
     Skill
```

保证日常训练体系始终能够与世界技能大赛官方能力要求保持对应。

当这两条主线稳定以后，TMS 才真正具备长期积累训练知识、竞赛数据和选手成长轨迹的价值。

---

## 后续工作

本方案确认后，下一阶段再单独制定：

> **TMS 训练主线领域重构实施 Plan**

实施 Plan 将基于本方案，具体分析当前 `develop` 分支中的：

- `standards`
- `events`
- `archives`
- `examcontent`
- `knowledge`
- `scoring`
- `training`

并确定：

- APP 保留、删除、重命名和拆分方案；
- 模型重构；
- 数据关系；
- 权限模型；
- 页面工作流；
- 数据迁移策略；
- 测试范围；
- 分阶段实施顺序。

该实施 Plan 与本设计方案分离，避免业务设计与代码实施细节混杂。
