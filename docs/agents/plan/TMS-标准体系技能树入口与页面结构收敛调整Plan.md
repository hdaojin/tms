# TMS 标准体系技能树入口与页面结构收敛调整 Plan

> 面向 Codex 的可执行实施计划  
> 基线分支：`feature/training-domain-refactor`  
> 基线日期：2026-08-21  
> 仓库：`hdaojin/tms`

---

## 0. 执行建议

### 推荐 Codex 配置

**首选：GPT-5.6 Terra + High reasoning**

原因：

- 本任务不是重新设计领域模型，而是在已经确定的 `Skill / SkillTreeVersion / SkillTreeNode / TechnicalDomain` 模型上做信息架构与页面链路收敛；
- 修改会跨 `selectors.py / views.py / urls.py / templates / navigation.yml / tests / docs`，需要较好的跨文件一致性和回归判断；
- 已有详细 Plan、ADR 和现有实现约束，降低了使用最高能力模型持续探索的必要性；
- Terra 在能力、速度与额度消耗之间更适合作为这类“中等复杂度、跨文件、规则明确”的默认执行模型；
- `High` 比 `Medium` 更适合本任务中 URL 兼容、权限边界、HTMX 局部刷新、跨领域移动等容易遗漏的联动点；
- 不建议默认使用 `xhigh / max / Ultra`，收益通常不足以抵消额外额度；如果实现中出现难以定位的跨领域树状态问题、权限回归或复杂测试失败，再临时升级。

### 升级策略

只在以下场景临时切换为 **GPT-5.6 Sol + High**：

1. `standards` 目标测试无法通过，且失败涉及多个 selector/service/view 的业务不变量；
2. 跨领域移动、HTMX 重定向或历史版本/当前版本路由出现难以解释的状态错乱；
3. 实现结束后需要一次高质量代码 review，而不是继续扩大开发范围。

简单模板文案、测试补齐、文档同步等后续小修可降为 **GPT-5.6 Terra + Medium**；不建议为了省额度在本次主体实现阶段直接使用 Luna。

---

# 1. 任务目标

当前标准体系已经完成核心领域模型重构，但前台仍保留两套相互重叠的 Skill 维护工作流：

1. `技能目录 -> 技术领域 -> 技能条目列表 -> 新增/编辑 Skill`
2. `技能树版本 -> 技能树工作台 -> 新增/编辑/挂载 Skill -> 调整树结构`

本次调整目标是：

> **保留 Skill 作为长期稳定业务实体，但取消“技能条目列表”作为独立日常管理工作台；把标准体系的日常维护统一收敛到“按技术领域展示的当前技能树”。**

最终用户心智应简化为：

```text
技能项目
└── 技术领域
    └── 当前标准技能树
        └── Skill
```

同时继续保留：

```text
技能项目
├── 历史技能树版本
└── WSOS 版本
```

---

# 2. 当前代码基线与必须遵守的既有决策

开始实现前必须阅读并遵守：

- `AGENTS.md`
- `CONTEXT.md`
- `docs/adr/0005-skill-tree-as-versioned-skill-hierarchy.md`
- `docs/user-manual/standards/overview.md`

重点保持以下既有业务不变量。

## 2.1 不修改 Skill / SkillTreeNode 的核心语义

继续保持：

- `Skill` 是跨技能树版本长期稳定的业务实体；
- `SkillTreeNode` 只表示某个 `Skill` 在某个 `SkillTreeVersion` 中的位置、父子关系、技术领域和顺序；
- 从树中移除节点不能删除 `Skill`；
- 调整树结构不能改变 Evidence、TrainingTask、评分结果等长期业务关联；
- 同一个 `Skill` 在同一个 `SkillTreeVersion` 中最多挂载一次；
- 技能树层级不设置业务上限。

**本次不修改这些模型语义，不重新设计树结构。**

## 2.2 保留 TechnicalDomain 的权限与组织轴语义

继续保持：

- `TechnicalDomain` 是训练组织与权限范围；
- 技术教练按领域获得管理权限；
- 项目管理员可管理全部领域；
- 浏览权限与管理权限不要因为页面调整而被意外收紧或扩大。

## 2.3 保留跨领域 Skill

继续保留：

```text
Skill.primary_domain
Skill.related_domains
```

树位置表达“结构归属”，`related_domains` 表达“跨领域关联”。

一个 Skill 在一个树版本中仍只有一个正式树位置，不允许因为它属于多个相关领域就在同一版本重复挂载多次。

## 2.4 保留跨领域移动能力

当前 `SkillTreeMoveForm` 与 `move_skill_tree_node()` 已支持：

- 选择目标技术领域；
- 将节点或整个子树移动到另一个技术领域；
- 校验整个子树中的 Skill 是否允许目标领域；
- 同时校验源领域和目标领域管理权限。

**本次领域拆页后不得丢失此功能。**

---

# 3. 本次明确不做的事情

为防止 Codex 扩大范围，本次明确禁止顺带实施以下内容：

- 不删除 `Skill` 模型；
- 不把 Skill 字段搬到 `SkillTreeNode`；
- 不取消 `SkillTreeVersion`；
- 不拆成 Linux / Windows / Network 三个独立技能树版本；
- 不重新设计 WSOS；
- 不修改 Evidence / Training / Scoring 的 Skill 外键关系；
- 不新增“掌握度”字段或自动聚合逻辑；
- 不新增拖拽排序；
- 不实现版本冻结、版本克隆、版本发布状态机；
- 不新增新的全局权限体系；
- 不重构无关 APP；
- 不为了本次页面收敛重写已经工作的 Skill 创建、查重、别名和树节点 service；
- 不创建新的 `.codex/skills`；
- 不做无关全仓 review。

除非实现本计划的必要路径确实暴露阻塞问题，否则遵循最小修改原则。

---

# 4. 目标信息架构

## 4.1 标准体系日常入口

最终前台导航建议：

```text
标准
├── 标准技能树
├── 技能树版本
├── WSOS
└── 技能项目管理
```

其中：

### 标准技能树

日常主要入口。

含义：

> 打开当前技能项目正在使用的 `is_current=True` 标准技能树。

### 技能树版本

用于：

- 查看历史版本；
- 创建新版本；
- 修改版本基本信息；
- 查看指定历史版本中的各技术领域技能树。

### WSOS

继续使用现有 WSOS 版本管理。

### 技能项目管理

用于项目管理员维护：

- 技能项目基本信息；
- 技术领域；
- 领域负责教练；
- 默认项目等。

普通技术教练不需要把“技能项目管理”作为日常工作入口。

---

# 5. 目标页面层级

## 5.1 技能项目详情页兼任项目级标准体系首页

当前：

```text
SkillProjectDetailView
```

仅显示项目基本信息。

当前：

```text
SkillCatalogView
```

又重复显示项目基本信息，并展示技术领域卡片。

本次将二者合并。

### 目标项目详情页

示意：

```text
网络系统管理
Network Systems Administration

当前技能树：2026-v1
当前 WSOS：WSOS 2026

技术领域

[ Linux ]
技能节点 42
负责人：...
[进入技能树]

[ Windows ]
技能节点 35
负责人：...
[进入技能树]

[ Network ]
技能节点 38
负责人：...
[进入技能树]
```

项目详情页承担：

- 项目基本信息；
- 当前技能树版本信息；
- 当前 WSOS 信息；
- 技术领域卡片；
- 技术领域基础状态；
- 技能树入口。

不再展示技能条目表格。

---

## 5.2 每个技术领域独立展示技能树

不要再在一个技能树页面中同时纵向输出全部领域树。

目标：

```text
标准
> 网络系统管理
> Linux

Linux 技能树
当前版本：2026-v1

[Linux] [Windows] [Network]

Linux
├── Linux 基础管理
│   ├── 文件系统
│   └── systemd
├── 网络配置
├── DNS
└── DHCP
```

要求：

- 一个页面只渲染一个 `TechnicalDomain` 的树；
- 领域切换按钮/Tab 可以在页面顶部快速切换；
- 每个领域必须有独立 URL；
- 不使用纯前端 Tab 隐藏三棵已经完整渲染的树；
- 领域切换应是真实链接，以保证刷新、收藏、权限判断和历史版本访问清晰。

---

# 6. 当前版本入口与历史版本入口

必须明确区分“当前技能树”和“指定版本技能树”。

## 6.1 当前领域技能树 URL

新增推荐路由：

```text
/standards/projects/<project_pk>/domains/<domain_pk>/tree/
```

建议 URL name：

```python
standards:domain_current_tree
```

语义：

> 打开指定项目、指定技术领域的当前技能树。

View 内通过已有：

```python
current_skill_tree_for(project)
```

解析 `is_current=True` 的 SkillTreeVersion。

如果项目没有当前技能树：

- 不抛出难以理解的 500；
- 不自动创建版本；
- 页面显示明确空状态：
  - “当前技能项目尚未设置当前技能树版本。”
- 对有权限用户提供：
  - “查看技能树版本”
  - “新增技能树版本”

---

## 6.2 指定历史版本领域树 URL

新增：

```text
/standards/trees/<tree_pk>/domains/<domain_pk>/
```

建议 URL name：

```python
standards:tree_domain_detail
```

语义：

> 打开明确指定的 SkillTreeVersion 中某个 TechnicalDomain 的技能树。

必须校验：

- tree 存在；
- domain 存在；
- domain.skill_project == tree.skill_project；
- 用户具有查看技能树版本权限；
- 停用领域的历史树结构仍按现有业务规则可查看。

---

## 6.3 原 `trees/<pk>/` 的处理

当前 `SkillTreeVersionDetailView` 会把全部领域一起渲染。

本次调整后：

```text
/standards/trees/<pk>/
```

不要继续渲染全部领域树。

建议：

1. 查找该版本项目下第一个可展示技术领域；
2. 重定向到：
   ```text
   /trees/<tree_pk>/domains/<domain_pk>/
   ```
3. 如果没有任何可展示领域，则保留一个极简版本详情空状态页。

版本基本信息编辑继续通过：

```text
/trees/<pk>/edit/
```

完成。

---

# 7. 技能目录的处理方式

## 7.1 删除“技能目录”作为独立工作台

当前以下用户路径不再作为正式工作流：

```text
技能目录
-> 技术领域
-> 技能条目列表
-> 新增技能
```

需要取消：

- 导航中的“技能目录”；
- `SkillCatalogView` 的领域卡片独立页面；
- `TechnicalDomainDetailView` 的 Skill 表格工作台职责。

## 7.2 不删除 Skill 数据层

“取消技能目录页面”不等于删除 Skill。

继续保留：

- `Skill`
- `SkillTerm`
- `SkillDetailView`
- `SkillUpdateView`
- Skill 名称/别名查重
- SkillForm
- Skill 与 Evidence / Training / Scoring 的长期关联
- 在技能树中创建新的 Skill
- 在技能树中挂载已有 Skill
- 技能详情分析页面

## 7.3 概念上改称“技能库”

如果需要描述项目中全部长期 Skill 的集合，统一使用：

> **技能库**

而不是继续把一个独立页面叫“技能目录”。

技能库是数据概念，不是新的一级管理页面。

建议同步修改 `SkillForm` 中：

```text
技能目录排序
```

为更中性的：

```text
排序
```

帮助文本同步移除“技能目录列表”表述。

不修改数据库字段，不产生 migration。

---

# 8. 旧 URL 兼容策略

本次属于 feature 分支中的信息架构收敛，但保留低成本 URL 兼容可以降低模板、测试、收藏链接断裂风险。

建议：

## 8.1 `/catalog/`

原：

```python
standards:skill_catalog_entry
```

改为兼容重定向入口：

- 有默认启用项目 -> `project_detail`
- 只有一个启用项目 -> `project_detail`
- 多项目且无默认 -> 项目选择页

不再渲染“技能目录”。

## 8.2 `/projects/<project_pk>/skills/`

原：

```python
standards:skill_list
```

改为：

```text
redirect -> standards:project_detail
```

## 8.3 `/projects/<project_pk>/domains/<domain_pk>/`

原：

```python
standards:domain_detail
```

原先是技能条目列表。

改为兼容重定向：

```text
redirect -> standards:domain_current_tree
```

或者直接把其语义改成当前领域技能树，但推荐新增显式 `/tree/` 路由并保留旧路径重定向，使 URL 语义清楚。

这些兼容入口：

- 不出现在新导航；
- 不再维护旧工作台模板；
- 测试只保证正确重定向，不继续测试旧页面内容。

---

# 9. Selector 调整

重点修改：

```text
standards/selectors.py
```

## 9.1 复用当前版本选择

已有：

```python
current_skill_tree_for(project)
```

继续复用，不另写一套 `is_current=True` 查询。

## 9.2 让技能树结构支持单领域读取

当前：

```python
skill_tree_structure(*, tree_version, user)
```

一次构造整个项目的全部领域树。

建议做最小兼容扩展：

```python
skill_tree_structure(
    *,
    tree_version,
    user,
    domain=None,
)
```

行为：

- `domain is None`：
  - 保持原行为，便于过渡和已有测试；
- `domain is not None`：
  - 只查询该 domain 的 SkillTreeNode；
  - 只返回该领域；
  - 仍复用原有 children 构造、权限装饰、descendant_count、move up/down 等逻辑；
  - 不复制第二套树装饰逻辑。

完成页面迁移后，如果确认项目中不再需要“全领域一次构造”，可以再决定是否进一步收敛；本次不要为了追求纯粹而重写 selector。

## 9.3 技术领域列表读取

项目详情页和领域树顶部切换都需要同一组领域。

如果当前 view 中已有重复逻辑，提取一个小型 selector，例如：

```python
project_domains_for_view(*, project, user)
```

语义沿用当前行为：

- 默认显示启用领域；
- 对有管理权限的用户允许看到其可管理的停用领域；
- 不因为本次 UI 调整改变领域浏览范围。

不要创建复杂 policy 框架。

---

# 10. “未纳入当前技能树”的 Skill

删除技能条目工作台后，必须保证长期 Skill 即使当前没有树位置也不会变成“无法发现的孤儿对象”。

## 10.1 定义

某技术领域中的“未纳入当前技能树 Skill”建议定义为：

- `skill.skill_project == tree.skill_project`
- `skill.primary_domain == 当前 domain`
- `skill.is_active == True`
- 当前 `SkillTreeVersion` 中不存在任何：
  ```python
  SkillTreeNode(tree_version=tree, skill=skill)
  ```

注意：

- 判断是否已纳入时必须看整个 tree version，而不是只看当前 domain；
- 如果一个主要归属 Linux 的 Skill 已经因 `related_domains` 被放到 Network 树中，它不应再被算作 Linux 的“未纳入”；
- 这样不会在多个领域重复统计同一个 Skill。

## 10.2 新增 selector

建议：

```python
unmounted_primary_skills_for_tree_domain(
    *,
    tree_version,
    domain,
    user,
)
```

要求：

- 复用 `visible_skills_for()` 的可见性规则；
- 用 `Exists` / `exclude` 等数据库查询完成；
- 不在 Python 循环中逐个 `.exists()`；
- 默认只返回启用 Skill；
- 支持按名称/别名搜索可放在 view 层做轻量过滤，或 selector 接收可选 query；
- 排序按现有 Skill 的稳定排序规则。

## 10.3 UI

领域技能树页面显示一个轻量入口：

```text
未纳入当前树：3
```

点击后使用 HTMX 打开抽屉/对话框/折叠面板均可，优先复用现有 DaisyUI + HTMX 交互模式。

列表至少显示：

- Skill 名称；
- 主要领域；
- 核心技能/可考核状态（如现有组件已有简洁展示可复用）；
- “查看”；
- “添加到当前技能树”。

不要重新做完整技能表格筛选页。

## 10.4 挂载位置

为“未纳入 Skill -> 加入树”新增一个轻量位置选择表单。

建议：

```python
SkillTreeAttachExistingForm
```

字段：

```text
new_parent
```

因为当前页面已经确定：

- tree_version
- technical_domain
- skill

无需再次让用户选择项目或技术领域。

父节点选择：

- 空值 = 作为领域根技能；
- 其他 = 当前领域内任意合法节点。

提交时必须调用已有：

```python
attach_existing_skill_to_tree(...)
```

不要复制 service 写入逻辑。

建议 endpoint：

```text
/trees/<tree_pk>/domains/<domain_pk>/skills/<skill_pk>/attach/
```

成功后刷新当前领域树 panel，并关闭对话框。

---

# 11. View 调整

重点：

```text
standards/views.py
```

## 11.1 `SkillProjectDetailView`

扩展 context：

```text
project
current_tree
current_wsos
domains
```

每个 domain 增加页面所需展示信息：

- 是否可编辑；
- 负责人；
- 当前树中的节点数量；
- 必要时未纳入数量。

节点数量优先一次 annotation / aggregate，不要 domain 循环查询。

增加 page actions：

- 项目管理员：编辑项目；
- 有权限时：新增技术领域；
- 当前树不存在且有权限：新增技能树版本。

## 11.2 删除/退役 `SkillCatalogView`

不要继续维护：

```python
SkillCatalogView
```

作为正式页面。

可将原入口改为 redirect view/function。

## 11.3 删除/退役 `TechnicalDomainDetailView` 的列表职责

原类承担：

- Skill table；
- 搜索；
- active/core/assessable/related 筛选；
- 分页；
- 新增 Skill dialog。

这些能力不再作为领域主页面。

不要把这些逻辑全部搬到新领域技能树页面。

领域树页面只保留树维护相关能力。

## 11.4 新增 CurrentDomainSkillTreeView

建议职责：

```python
CurrentDomainSkillTreeView
```

处理：

1. 获取 project；
2. 获取 domain，并校验属于 project；
3. 获取 current tree；
4. current tree 存在时：
   - 构造当前 domain 树；
   - 构造领域快速切换数据；
   - 提供未纳入 Skill 数量；
5. current tree 不存在时：
   - 显示空状态；
6. context 标明：
   ```text
   is_current_tree = True
   ```

## 11.5 新增 VersionDomainSkillTreeView

处理明确的：

```text
tree_pk + domain_pk
```

context：

```text
tree
domain
tree_domains/navigation domains
is_current_tree
```

模板与 CurrentDomainSkillTreeView 共用。

不要复制两套页面模板。

---

# 12. 技能树 HTMX panel 调整

当前：

```text
standards/templates/standards/partials/skill_tree_panel.html
```

一次循环：

```django
{% for domain in tree_domains %}
```

渲染所有领域。

本次应收敛为单领域 panel。

建议新命名：

```text
standards/partials/skill_tree_domain_panel.html
```

或者直接修改原文件语义；如果修改原文件，应同步所有引用和测试。

目标 context：

```text
tree
domain
```

内部只渲染：

```text
domain.tree_roots
```

保留既有：

- 根技能新增；
- 子技能新增；
- 同级技能新增；
- 查看 Skill；
- 编辑 Skill；
- 移动；
- 上移/下移；
- 移除；
- quick add；
- candidate reuse；
- detailed create。

尽量不改：

- `skill_tree_branch.html`
- `skill_tree_node_actions.html`
- inline editor
- move/remove dialogs

除非其 URL/context 因领域路由变化确实需要调整。

---

# 13. HTMX mutation 响应

这是本次最容易产生回归的部分。

## 13.1 同领域操作

以下操作成功后：

- 新增根节点；
- 新增子节点；
- 新增同级节点；
- 编辑 Skill；
- 同领域移动；
- 同级排序；
- 移除节点；
- 挂载未纳入 Skill；

应只重新渲染：

```text
当前领域 skill tree panel
```

不要重新计算和返回三棵领域树。

继续保留现有 `HX-Trigger` 事件（如果当前 JS/交互依赖）。

## 13.2 跨领域移动

当前 `move_skill_tree_node()` 支持从 Linux 移到 Network。

领域独立页面后，如果：

```text
source_domain != target_domain
```

只刷新源领域 panel 会导致用户看不到移动后的节点。

建议处理：

- POST 成功；
- 返回 HTTP 200；
- 设置：
  ```text
  HX-Location
  ```
  或现有项目更合适的 HTMX 导航响应；
- 导航到目标领域的同一技能树版本页面。

优先使用 `HX-Location`，因为它适合 htmx 导航并更新浏览器历史；不要在 302 响应上期待 HTMX 响应头生效。

如果请求不是 HTMX：

- 使用正常 Django redirect 到目标领域页面。

必须增加测试覆盖。

---

# 14. Template 调整

主要文件：

```text
standards/templates/standards/project_detail.html
standards/templates/standards/tree_detail.html
standards/templates/standards/partials/skill_tree_panel.html
standards/templates/standards/domain_detail.html
standards/templates/standards/skill_catalog.html
```

## 14.1 `project_detail.html`

合并原 `skill_catalog.html` 中有价值的领域卡片设计。

展示：

- 项目基本信息；
- 默认项目 badge；
- 当前技能树；
- 当前 WSOS；
- 技术领域 cards；
- domain code；
- description；
- 负责人；
- 当前树节点数量；
- “进入技能树”按钮；
- “编辑领域”按权限显示。

避免重复大段说明。

## 14.2 新增 `domain_tree.html`

建议新增：

```text
standards/templates/standards/domain_tree.html
```

负责：

- 面包屑；
- 项目 / 领域标题；
- 当前或历史版本标识；
- 领域切换；
- 当前领域树 panel；
- 未纳入 Skill 入口；
- 必要的 tree version 编辑入口。

## 14.3 `tree_detail.html`

不再承担全领域树工作台。

可以：

- 仅用于“无领域时的版本详情空状态”；或
- 如果重定向逻辑完全覆盖，则删除模板前先确认无引用。

## 14.4 删除旧工作台模板

只有在确认无引用后再删除：

```text
skill_catalog.html
skill_results.html
skill_create_dialog.html
skill_create_response.html
skill_catalog_notice.html
```

注意：

`SkillForm` 和技能树 detailed create 仍可能复用：

```text
skill_candidates.html
skill_domain_fields.html
skill_form_panel.html
```

不得仅凭文件名判断后直接删除。

删除前使用搜索确认全部模板 include / render / HTMX target 引用。

---

# 15. URL 调整

重点：

```text
standards/urls.py
```

建议最终主要路由：

```python
path("", ..., name="project_list")

path("projects/<int:pk>/", ..., name="project_detail")
path("projects/<int:project_pk>/domains/create/", ..., name="domain_create")
path("projects/<int:project_pk>/domains/<int:domain_pk>/edit/", ..., name="domain_edit")

path(
    "projects/<int:project_pk>/domains/<int:domain_pk>/tree/",
    ...,
    name="domain_current_tree",
)

path("skills/<int:pk>/", ..., name="skill_detail")
path("skills/<int:pk>/edit/", ..., name="skill_edit")

path("trees/", ..., name="tree_list")
path("trees/create/", ..., name="tree_create")
path("trees/<int:pk>/", ..., name="tree_detail")
path("trees/<int:pk>/edit/", ..., name="tree_edit")

path(
    "trees/<int:tree_pk>/domains/<int:domain_pk>/",
    ...,
    name="tree_domain_detail",
)
```

所有现有技能树 action URL 继续包含 `tree_pk`，并在需要时保留 `domain_pk`。

不要把树修改 action 改成“current tree only”，否则历史/草稿版本将无法维护。

---

# 16. 导航调整

修改：

```text
core/config/navigation.yml
```

当前“标准体系”下包括：

- 技能项目
- 新增技能项目
- 技能目录
- 标准技能树版本
- 新增标准技能树版本
- WSOS 版本
- 新增 WSOS 版本

本次收敛。

建议普通入口：

```text
标准技能树
技能树版本
WSOS
```

管理入口：

```text
技能项目管理
```

“新增……”类入口尽量放到对应列表页 page action，不需要全部占据主导航。

至少移除：

```text
技能目录
```

这个主导航项。

### 标准技能树入口

新增一个轻量 entry view：

```python
CurrentSkillTreeEntryView
```

行为参考当前 `SkillCatalogEntryView`：

1. 找启用 SkillProject；
2. 有默认项目 -> project detail；
3. 只有一个项目 -> project detail；
4. 多项目无默认 -> 项目选择页；
5. 无项目 -> 404 / 合理空状态。

导航：

```yaml
label: 标准技能树
url_name: standards:current_tree_entry
```

项目详情页再通过领域卡片进入具体树。

---

# 17. 权限要求

本次不得重写权限模型。

## 17.1 查看

继续使用现有 Django Permission：

```text
standards.view_skillproject
standards.view_skilltreeversion
standards.view_skill
```

对象范围沿用 selector。

## 17.2 管理

继续使用：

```text
manageable_domains_for()
can_manage_domain()
can_manage_skill()
```

树中按钮根据已有装饰字段控制：

```text
can_add_tree_position
can_create_skill
can_move
can_remove
can_edit_skill
```

## 17.3 跨领域移动

继续要求：

- 源领域 change_skilltreenode；
- 目标领域 change_skilltreenode；
- Skill/子树允许目标技术领域。

不因 UI 拆分减少后端权限校验。

---

# 18. `SkillTable` 与旧列表代码清理

当前：

```text
standards/tables.py
```

存在 `SkillTable`，主要服务领域技能条目列表。

实现结束后：

1. 全仓搜索 `SkillTable`；
2. 如果仅旧 `TechnicalDomainDetailView` 使用：
   - 删除 `SkillTable`；
   - 删除对应 import；
3. 如果其他业务仍使用：
   - 保留，不无关重构。

同理处理：

- 旧筛选 helper；
- `filter_names`；
- 分页逻辑；
- list-only HTMX partial；
- highlight create result 等。

原则：

> 删除已经没有调用方的旧工作台代码，但不要为了“清洁”删除仍被技能树 SkillForm 使用的公共能力。

---

# 19. 文档与术语同步

## 19.1 `docs/user-manual/standards/overview.md`

重写当前操作流程。

删除：

```text
进入具体技术领域，在“技能条目”区域搜索、筛选和分页浏览技能
```

改成：

```text
从技能项目选择技术领域，直接进入该领域的当前标准技能树；
在树中创建、复用、编辑和组织 Skill。
```

明确：

- Skill 是长期本体；
- 技能树是日常标准维护入口；
- 历史版本从“技能树版本”进入；
- 未纳入当前树的 Skill 仍保留在技能库；
- 从树移除不删除 Skill；
- 跨领域关联仍使用主要领域/关联领域。

## 19.2 ADR 0005

不改变决策。

如果其中“技能目录”容易被理解为必须存在的 UI 页面，只做术语澄清，例如：

```text
项目级 Skill 集合（技能库）
```

不要重写 ADR。

## 19.3 `CONTEXT.md`

如果当前稳定术语仍把“技能目录”定义为主要工作流，则同步成：

- Skill：长期技能本体；
- 技能库：项目中长期 Skill 的集合；
- 标准技能树：Skill 在某版本、某领域中的层级组织；
- 当前标准技能树：日常维护入口。

仅更新与本次决策直接相关的段落。

---

# 20. 测试计划

重点修改：

```text
standards/tests.py
standards/test_skill_tree.py
core/tests.py
```

不要机械运行或修改无关 APP 测试。

## 20.1 项目详情测试

覆盖：

- 项目详情显示技术领域；
- 显示 current SkillTreeVersion；
- 显示 current WSOS；
- 每个领域链接到 `domain_current_tree`；
- 当前树节点计数正确；
- 无当前树时显示空状态；
- 停用领域按现有权限规则显示/隐藏。

## 20.2 当前技能树入口测试

覆盖：

- 默认项目存在 -> 自动进入项目详情；
- 只有一个启用项目 -> 自动进入；
- 多项目且无默认 -> 项目选择；
- 无启用项目 -> 合理响应。

## 20.3 领域当前树测试

覆盖：

- 正确解析 current tree；
- 只显示当前领域节点；
- 不把其他领域根节点渲染到 DOM；
- 页面存在其他领域切换链接；
- domain 与 project 不匹配 -> 404；
- 项目无 current tree -> 空状态而非异常。

## 20.4 历史版本领域树测试

覆盖：

- 指定 tree version 正确展示；
- 即使不是 current 也能查看；
- domain 必须属于 tree.skill_project；
- `trees/<pk>/` 正确重定向到第一个领域；
- 无领域时正确空状态。

## 20.5 未纳入 Skill 测试

覆盖：

- primary_domain 为当前领域且未挂载 -> 出现；
- 已挂载在当前领域 -> 不出现；
- 已挂载在其他 related domain -> 也不出现；
- 停用 Skill 默认不出现在可挂载列表；
- 无查看权限的 Skill 不泄露；
- attach 成功后从未纳入列表消失并出现在树中；
- 重复 attach 继续由 service 拒绝。

## 20.6 权限测试

覆盖：

- 领域教练只能编辑其可管理领域；
- 项目管理员可管理全部；
- 用户可查看但无管理权限时不显示编辑/新增/移动按钮；
- 未纳入 Skill attach 后端同样做权限校验。

## 20.7 HTMX 测试

覆盖：

### 同领域

成功后响应为当前领域 panel，而不是全部领域 panel。

### 跨领域 move

假设：

```text
Linux -> Network
```

并且 Skill/子树已关联 Network。

验证：

- service 成功；
- HTMX 请求返回 2xx；
- 响应包含正确的 `HX-Location`（或项目最终采用的等价 HTMX 导航头）；
- 导航目标是 Network 的同一 tree version 页面；
- 普通非 HTMX POST 返回正常 redirect；
- 数据库中整个子树 technical_domain 已更新。

不要使用“302 + HX-Location”组合期待 HTMX 处理响应头。

## 20.8 导航测试

`core/tests.py` 更新：

- 不再出现“技能目录”；
- 存在“标准技能树”；
- “技能树版本”仍存在；
- WSOS 仍存在；
- 技能项目管理按配置权限可见。

---

# 21. Migration 边界

本次设计原则上：

> **不需要数据库 migration。**

因为不修改：

- Skill 字段；
- SkillTreeNode 字段；
- constraint；
- FK；
- M2M；
- permissions Meta。

如果 Codex 在实施过程中发现“必须修改模型才能完成本计划”，先重新检查设计；大概率说明实现方向偏离。

最终执行：

```bash
uv run python manage.py makemigrations --check
```

应无新 migration。

---

# 22. 前端实现约束

继续遵守项目当前技术栈：

- Django 6 templates；
- django-htmx；
- Tailwind CSS 4；
- DaisyUI 5；
- Alpine.js CSP build；
- Iconify。

原则：

- 领域切换优先真实 `<a>` 链接，不用 Alpine 管理核心路由状态；
- HTMX 负责局部树刷新；
- 后端负责所有权限和业务校验；
- 不引入新的前端框架；
- 不为本次页面收敛写复杂 client-side tree state；
- 使用已有 DaisyUI card / tabs / badge / drawer/dialog 风格；
- Iconify 沿用当前 `icon-[tabler--...]`。

如果模板新增了此前未出现在扫描源中的 Tailwind utility，运行 CSS build。

---

# 23. 建议实施顺序

## Phase 1：读取与确认

Codex 开始执行时：

1. 阅读 `AGENTS.md`；
2. 阅读 `CONTEXT.md`；
3. 阅读 ADR 0005；
4. 检查：
   ```text
   standards/models.py
   standards/selectors.py
   standards/services.py
   standards/forms.py
   standards/views.py
   standards/urls.py
   standards/tables.py
   standards/templates/standards/
   standards/tests.py
   standards/test_skill_tree.py
   core/config/navigation.yml
   core/tests.py
   docs/user-manual/standards/overview.md
   ```
5. 搜索旧 skill catalog 相关 URL/template 的全仓引用。

不要先改代码再猜引用关系。

---

## Phase 2：读取层

先实现/调整：

- project domains selector（如确有复用需要）；
- 单领域 `skill_tree_structure(...)`；
- 未纳入 Skill selector；
- project current tree / current WSOS 数据。

先补 selector 单元/页面测试。

---

## Phase 3：新领域树路由与页面

实现：

- `domain_current_tree`
- `tree_domain_detail`
- project detail enrich
- `domain_tree.html`
- 单领域 tree panel

确保已有树增删改操作继续工作。

---

## Phase 4：HTMX action 收敛

将各 tree action 的成功响应从：

```text
全部 tree_domains
```

收敛为：

```text
当前 domain
```

特别处理跨领域 move。

不要同时重写 service。

---

## Phase 5：未纳入 Skill 辅助入口

实现：

- 未纳入计数；
- HTMX 列表；
- attach dialog/form；
- 调用已有 `attach_existing_skill_to_tree()`。

保持功能轻量，不恢复成第二套 Skill table workbench。

---

## Phase 6：删除旧技能目录 UI

确认新路径完整后：

- 导航去掉技能目录；
- 原 catalog URL 改 redirect；
- 原 domain detail list 改 redirect；
- 删除无引用旧 view/template/table/filter 代码；
- 保留 Skill 详情/编辑及树工作台仍需要的 SkillForm 相关 partial。

---

## Phase 7：文档同步

更新：

- `docs/user-manual/standards/overview.md`
- 必要时 `CONTEXT.md`
- ADR 0005 仅做术语澄清

不要新增一份重复架构文档。

---

## Phase 8：验证

优先目标验证：

```bash
uv run python manage.py check
uv run python manage.py makemigrations --check
uv run python manage.py test standards
uv run python manage.py test core.tests
```

如果项目实际测试标签/模块组织略有不同，按仓库现状调整，但只扩展到本次直接受影响测试。

模板发生 Tailwind class 变化时：

```bash
npm run build:css
```

如果仅移动模板、复用已有 class 且 AGENTS 当前规则允许跳过 CSS build，则不机械执行完整 frontend build。

不要因为本任务自动运行所有 APP 的全量测试，除非目标测试暴露跨 APP 回归证据。

---

# 24. 完成验收标准

实现完成后必须同时满足以下条件。

## 信息架构

- [ ] 主导航不再存在“技能目录”；
- [ ] 有明确“标准技能树”日常入口；
- [ ] 技能树版本仍作为历史/版本管理入口；
- [ ] 项目详情页直接展示技术领域；
- [ ] 技术领域直接进入对应技能树。

## 技能树

- [ ] 每个页面只展示一个技术领域的树；
- [ ] Linux / Windows / Network 等领域可通过真实 URL 切换；
- [ ] 三个领域仍属于同一个 SkillTreeVersion；
- [ ] 当前版本与历史版本使用同一领域树模板；
- [ ] 所有现有新增、编辑、移动、排序、移除能力保留；
- [ ] 跨领域 move 正常工作。

## Skill

- [ ] Skill 模型与稳定身份不变；
- [ ] SkillDetail / SkillUpdate 继续可访问；
- [ ] Skill 名称/别名查重继续工作；
- [ ] Evidence / Training / Scoring 关联不受影响；
- [ ] 树中可创建新 Skill；
- [ ] 树中可复用已有 Skill；
- [ ] 当前未挂载 Skill 可被发现并重新挂载；
- [ ] 从树移除不会删除 Skill。

## 权限

- [ ] 教练领域管理范围不变；
- [ ] 项目管理员权限不变；
- [ ] 页面按钮与后端 service 权限一致；
- [ ] 不通过隐藏按钮代替服务端校验。

## 技术质量

- [ ] 无新增数据库 migration；
- [ ] 无重复 tree selector 实现；
- [ ] 无明显 N+1；
- [ ] HTMX 响应只刷新必要领域；
- [ ] 跨领域 HTMX 移动不会留下陈旧 UI；
- [ ] 无旧技能目录页面残留导航入口；
- [ ] 无无引用旧模板/view/table 代码（经搜索确认后清理）。

## 文档

- [ ] 用户手册不再指导用户去“技能条目列表”维护 Skill；
- [ ] 技能库/技能树/Skill 三者职责描述一致；
- [ ] ADR 0005 的核心决策未被破坏。

---

# 25. Codex 最终交付说明要求

执行完成后只需要给出与本任务匹配的简洁总结：

1. 实际修改了哪些页面/入口；
2. 是否删除/保留了哪些旧兼容 URL；
3. 当前树与历史树如何访问；
4. 未纳入 Skill 如何处理；
5. 跨领域移动如何处理；
6. 执行了哪些测试及结果；
7. 是否存在本计划范围内仍未完成的问题。

不要重复整份 Plan，不进行新的全仓架构 review，也不要顺带提出大量无关优化。

---

# 26. 最终目标状态

完成本 Plan 后，标准体系的用户心智应稳定为：

```text
标准
└── 标准技能树
    └── 网络系统管理
        ├── Linux
        │   └── 当前 Linux 技能树
        ├── Windows
        │   └── 当前 Windows 技能树
        └── Network
            └── 当前 Network 技能树
```

版本管理：

```text
标准
└── 技能树版本
    ├── 2025-v1
    │   ├── Linux
    │   ├── Windows
    │   └── Network
    └── 2026-v1（当前）
        ├── Linux
        ├── Windows
        └── Network
```

数据关系继续保持：

```text
Skill（长期稳定业务本体）
    │
    ├── SkillTreeNode（某版本中的位置）
    ├── Evidence（历史考点）
    ├── TrainingTask（训练任务）
    └── Scoring / 分析结果
```

**最终原则：树负责“组织”，Skill 负责“身份”，技术领域负责“责任边界”，版本负责“历史结构”。**
