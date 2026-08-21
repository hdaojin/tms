# TMS 技能树工作台交互修正 Plan（Workbench v2）

> **文档性质**：可供 Codex 直接执行的工程实施计划  
> **目标仓库**：`hdaojin/tms`  
> **目标分支**：`feature/training-domain-refactor`  
> **基线状态**：截至 2026-08-21，GitHub 对比显示该分支相对 `develop` 为 **ahead 2 / behind 0**；`develop` 基线提交为 `b343872fbf7fc48d25c0cd4c266470f1d888b883`。  
> **任务性质**：对已完成的 Skill / SkillTreeNode 领域模型重构进行 **Workbench v2 交互修正**。  
> **核心约束**：**不要再次重构 Skill / SkillTreeNode 领域模型，不要新增 schema migration，不要重新发明分类/主题/分组节点。** 本任务重点是树形工作台 UI、HTMX、JS、表单复用与回归测试。

---

# 0. 为什么需要这次修正

当前分支已经基本正确完成：

- `Skill.display_code` 删除；
- `SkillTreeNode` 删除 `code / node_type / name / description / is_active`；
- 每个树节点都必须关联稳定 `Skill`；
- Skill 可作为根、父节点和叶子节点；
- 树支持任意深度；
- 同一 Skill 在同一树版本只出现一次；
- SkillTreeNode 只负责版本化位置、父子关系和排序；
- 已实现创建、挂载、移动、同级重排、移除、跨域校验等 service；
- 已实现树形展示、HTMX 局部刷新和基础测试；
- `CONTEXT.md` 与 ADR 0005 已同步最终领域语义。

这些内容 **不要推翻**。

当前主要偏差在于：技能树页面虽然“显示成树”，但交互仍然像一个 CRUD 后台：

```text
▾ 用户与权限管理
  查看技能 编辑技能 新增子技能 移动 ↑ ↓ 从树中移除
  ├─ sudo
  │  查看技能 编辑技能 新增子技能 移动 ↑ ↓ 从树中移除
  └─ PAM
     查看技能 编辑技能 新增子技能 移动 ↑ ↓ 从树中移除
```

“快速新增”实际使用 DaisyUI dropdown，完整表单预渲染在每个节点下；这与既定目标“直接编辑技能树、类似思维导图”不同。

目标体验应更接近：

```text
Linux

▾ 系统管理                              +  ⋯
│
├─ ▾ 用户与权限管理                     +  ⋯
│  ├─ 用户和用户组管理                     ⋯
│  ├─ sudo 权限管理                        ⋯
│  ├─ PAM                                  ⋯
│  └─ [ 输入或搜索技能名称…… ]
│
└─ 网络服务                              +  ⋯
```

本任务就是把当前“树形 CRUD 页面”修正为真正的“树形工作台”。

---

# 1. 执行契约

Codex 开始编码前必须接受以下约束，不得再次讨论或改写。

## 1.1 不改领域模型

本次默认 **禁止修改**：

```text
standards/models.py 中 Skill / SkillTreeNode 的字段定义和核心不变量
standards/migrations/0004_simplify_skill_tree_nodes.py
docs/adr/0005-skill-tree-as-versioned-skill-hierarchy.md 的领域决策
```

除非代码存在明确 bug 且不修改无法完成本任务，否则：

- 不增加 `node_type`；
- 不增加 `code`；
- 不增加 `is_group`；
- 不增加“分类 / 主题 / 分组”；
- 不限制树深度；
- 不把 parent 放到 `Skill`；
- 不增加 SkillTreeVersion 冻结状态；
- 不增加拖拽依赖；
- 不引入 MPTT/treebeard；
- 不设计父 Skill 汇总算法。

## 1.2 保留现有 service 语义

当前以下 service 是正确基线：

```text
attach_existing_skill_to_tree()
create_skill_in_tree()
move_skill_tree_node()
reorder_skill_tree_node()
remove_skill_tree_node()
save_skill()
find_skill_candidates()
```

原则：

- 优先复用，不重写；
- 允许为“完整 SkillForm 创建 + 原子挂树”补一个非常薄的 service；
- 不把业务写回 View；
- 不复制一套新的 Skill 去重逻辑。

## 1.3 本任务的重点

优先修改：

```text
standards/forms.py
standards/views.py
standards/templates/standards/tree_detail.html
standards/templates/standards/partials/skill_tree_*.html
static/js/app.js
static/css/main.css（只在确有需要时）
standards/test_skill_tree.py
```

必要时少量修改：

```text
standards/services.py
```

原则上不要修改其他 APP。

---

# 2. 开始前确认最新基线

从仓库根目录执行：

```bash
git fetch origin
git switch feature/training-domain-refactor
git pull --ff-only origin feature/training-domain-refactor
git status --short
git log -3 --oneline
git rev-list --left-right --count develop...HEAD
```

要求：

- 当前分支必须是 `feature/training-domain-refactor`；
- 不覆盖用户已有未提交修改；
- 当前预期相对 `develop` 为 `0 2`（develop 独有 0、当前分支独有 2）；如果实际已变化，先审阅新提交再执行；
- 不重新执行上一轮领域重构；
- 阅读：
  - `AGENTS.md`
  - `CONTEXT.md`
  - `docs/adr/0005-skill-tree-as-versioned-skill-hierarchy.md`
  - `docs/agents/plan/TMS-技能与技能树简化及树形工作台实施Plan.md`

---

# 3. 当前实现审计基线

开始修改前至少确认以下现状。

## 3.1 模型已经正确

`SkillTreeNode` 当前应仅有：

```text
tree_version
technical_domain
parent
skill
order
created_at
updated_at
```

并且：

- `skill` 必填；
- parent 同 tree_version；
- parent 同 technical_domain；
- 防 self/cycle；
- Skill domain 合法；
- 同一 Skill / tree_version 唯一。

如果仍是这样，不改模型。

## 3.2 当前 Workbench 的主要问题

当前：

- `skill_tree_panel.html` 在 TechnicalDomain header 用 dropdown 放 quick add form；
- `skill_tree_node_actions.html` 每个节点显示一整行操作；
- `skill_tree_branch.html` 每个节点视觉像独立 card；
- `skill_tree_quick_add.html` 被每个 node 预渲染；
- `SkillTreeQuickAddForm` 同时承担 name / description / confirm_distinct；
- 高相似候选在 quick-add 小表单里继续填写 description，而不是进入完整 `SkillForm`；
- 没有“新增同级技能”；
- 已存在于当前树的候选只显示路径，没有“定位到节点”；
- move/remove dialog 使用 `<dialog open>`，没有统一使用 `showModal()`；
- 叶子节点 remove 仍显示两种实际上等价的移除方式。

这些是本次修正目标。

---

# 4. Workbench v2 的最终交互模型

## 4.1 树本身就是编辑界面

正常状态：

```text
Linux

▾ 系统管理                              +  ⋯
│
├─ ▾ 用户与权限管理                     +  ⋯
│  ├─ 用户和用户组管理                     ⋯
│  ├─ sudo 权限管理                        ⋯
│  └─ PAM                                  ⋯
│
└─ 网络服务                              +  ⋯
```

要求：

- Skill 名称是视觉主体；
- badges 可以保留，但弱化；
- 高频动作只有 `+`；
- 低频动作放入 `⋯`；
- 不为每个节点常驻显示“查看 / 编辑 / 移动 / 上移 / 下移 / 删除”一整行按钮；
- 不为每个 Skill 行画完整 card 边框；
- TechnicalDomain 可以继续用 section/card；
- domain 内部树要像树，不像嵌套表单卡片。

## 4.2 `+` 的语义

节点上的：

```text
+
```

表示：

```text
添加子技能
```

点击后不打开 dropdown，不打开 drawer，而是在 children 位置直接出现 inline editor。

例如：

```text
用户与权限管理                         +  ⋯
├─ sudo
├─ PAM
└─ ● [ 输入或搜索技能名称…… ]
```

Domain header 的：

```text
+ 添加根技能
```

在该 TechnicalDomain 根列表末尾插入同样的 inline editor。

## 4.3 `⋯` 的语义

使用轻量 dropdown/menu：

```text
查看技能详情
编辑技能
────────────
添加同级技能
移动到……
上移
下移
────────────
从当前技能树移除
```

规则：

- “添加子技能”主要用独立 `+`，不必在 `⋯` 重复；
- “添加同级技能”必须补齐；
- 叶子和父 Skill 都可以新增子 Skill；
- 操作按权限显示；
- 不出现“编辑节点”。

---

# 5. Phase 1：重构树节点视觉结构

重点修改：

```text
standards/templates/standards/partials/skill_tree_panel.html
standards/templates/standards/partials/skill_tree_branch.html
standards/templates/standards/partials/skill_tree_node_label.html
standards/templates/standards/partials/skill_tree_node_actions.html
```

## 5.1 Node row

建议每个节点只有一个紧凑 row：

```text
[chevron] Skill 名称 [核心] [可考核]                  [+] [⋯]
```

视觉要求：

- row 使用轻 hover background；
- 不使用每节点大面积 `border + card`；
- children 通过左侧 guide line + 固定 margin 表达层级；
- 所有 Tailwind class 必须是完整静态 class；
- 不使用 `ml-{{ depth }}`。

## 5.2 展开/折叠

可以继续使用 `<details>/<summary>`，但注意：

- 不要把 `+` 和 `⋯` 作为 `<summary>` 的交互子元素，避免点击操作时同时触发折叠；
- 可以通过 wrapper / absolute action area 让按钮视觉上与 summary 同行；
- 也可以保留现有 details 并重新布局；
- 不需要新增前端 tree library。

要求：

- 有 children 的节点才显示 chevron；
- 叶子无无意义 chevron；
- 默认展开；
- 新建成功后自动展开 ancestors；
- 键盘可访问。

## 5.3 操作区域

删除当前独立 actions row 的视觉形式。

可保留模板文件名，但渲染结果应成为：

```text
+    ⋯
```

而不是：

```text
查看技能 编辑技能 新增子技能 移动 ↑ ↓ 删除
```

---

# 6. Phase 2：真正的 inline editor

这是本任务最重要的部分。

## 6.1 不再预渲染每个节点的完整 quick-add form

当前页面存在：

```text
每个 node
└─ dropdown
   └─ 完整 SkillTreeQuickAddForm
```

必须取消。

页面初始状态：

- 允许每个 node 保留一个极轻量空 host；
- 不得为每个 node 预渲染 `<form>`；
- 不得为每个 node 预渲染 candidate container + textarea + checkbox；
- 页面任意时刻通常只有一个活动 inline editor。

允许：

```html
<div id="skill-tree-child-editor-host-123"></div>
```

不允许：

```html
<div hidden>
  <form>完整 quick add...</form>
</div>
```

## 6.2 Editor GET

将当前 quick-add endpoint 调整为支持：

```text
GET  → 返回 inline editor fragment
POST → 提交 inline editor
```

或者新增非常薄的 editor GET endpoint。

要求：

- node `+`：GET child editor；
- domain “添加根技能”：GET root editor；
- `⋯ → 添加同级技能`：GET sibling editor；
- server 根据 URL 中的 tree/domain/node 计算 parent；
- 不信任客户端 hidden parent/domain。

推荐 URL 语义可以是：

```text
trees/<tree_pk>/domains/<domain_pk>/quick-add/
trees/<tree_pk>/nodes/<node_pk>/quick-add-child/
trees/<tree_pk>/nodes/<node_pk>/quick-add-sibling/
```

可以沿用当前 root/child URL 并补 sibling，只要语义清楚。

## 6.3 Inline editor 内容

普通情况下只显示：

```text
● [ 输入或搜索技能名称…… ]   [×]
```

不要默认显示：

```text
description
confirm_distinct
difficulty
aliases
related_domains
```

输入框：

- autofocus；
- placeholder：`输入或搜索技能名称……`；
- Enter 提交；
- Esc 取消；
- 输入约 350ms 触发候选查询；
- 提交前后继续使用 HTMX。

## 6.4 一次只允许一个 editor

在 `static/js/app.js` 实现轻量控制：

- 用户打开新的 inline editor 前，关闭页面上已有 editor；
- Esc 只关闭当前 editor；
- 取消按钮删除 editor；
- 不需要维护复杂全局状态；
- HTMX swap 后重新初始化仍保持幂等。

---

# 7. Phase 3：补齐“添加同级技能”

当前缺失，必须实现。

语义：

```text
当前 node = B
parent(B) = A
```

“添加同级技能”应创建：

```text
parent = A
```

如果当前 node 是 TechnicalDomain 根：

```text
parent = None
```

插入位置：

- 第一版可以追加到当前 siblings 末尾；
- 不要求插入到当前 node 后面；
- 如果实现成本低，可以默认插入当前 node 后；但不要为此大幅改 service；
- 当前核心要求是语义正确。

权限：

- 与添加 child/root 相同；
- 需要 `add_skilltreenode + domain scope`；
- 创建全新 Skill 还需要 `add_skill + domain scope`。

---

# 8. Phase 4：重新定义 SkillTreeQuickAddForm

当前：

```text
name
description
confirm_distinct
existing_skill_id
```

Workbench v2 中 inline editor 应收缩为：

```text
name
existing_skill_id（如果仍需要，可以 hidden）
```

`description / confirm_distinct` 不再属于 inline form。

原因：

> inline editor 是“输入或选择 Skill”的快速入口，不是第二套 SkillForm。

当存在高相似候选时，inline editor 不直接创建“高相似但不同”的 Skill，而是引导用户进入完整 SkillForm drawer。

---

# 9. Phase 5：候选 Skill 的三态流程

继续复用：

```text
find_skill_candidates()
normalize_skill_term()
SkillTerm
save_skill()
```

不要写第二套匹配算法。

## 9.1 无明显候选

输入：

```text
ACL 权限管理
```

无明显候选：

```text
Enter
→ create_skill_in_tree()
→ Skill + SkillTerm + SkillTreeNode 原子创建
→ 刷新 #skill-tree-panel
→ skillTreeNodeCreated
→ 展开 ancestors + scroll + highlight
```

## 9.2 候选可复用

例如：

```text
输入：sudo 管理

已有：
sudo 权限管理
别名：sudo 管理
```

显示：

```text
sudo 权限管理
主要领域：Linux

[使用已有技能]
```

点击：

```text
attach_existing_skill_to_tree()
```

不创建重复 Skill。

## 9.3 Skill 已存在于当前树版本

现在只显示路径，本次补：

```text
已在当前版本：
系统管理 / 用户与权限管理 / sudo 权限管理

[定位到已有技能]
```

按钮不得发起新的写请求。

前端：

```text
找到 #skill-tree-node-{nodeId}
打开 ancestors
scrollIntoView()
临时高亮
focus
```

优先复用已有 `skillTreeNodeCreated` 的 locate/highlight 代码，提取成：

```text
focusSkillTreeNode(nodeId)
```

不要复制两套 scroll/highlight。

## 9.4 高相似但用户认为是不同 Skill

例如：

```text
输入：Linux 用户和组管理

已有候选：
Linux 用户管理
Linux 用户与组管理
```

inline 区域显示：

```text
可能已有相近技能

Linux 用户管理           [使用已有]
Linux 用户与组管理       [使用已有]

确实是新的技能？
[完整创建新技能]
```

**不要**在 inline editor 中继续显示 description / confirm checkbox。

点击“完整创建新技能”：

```text
→ HTMX 打开 SkillForm side-dialog
```

---

# 10. Phase 6：树内完整 SkillForm drawer

这是修正“第二套半功能表单”的关键。

## 10.1 必须复用现有 SkillForm

完整创建应继续使用：

```text
SkillForm
save_skill()
SkillTerm
现有候选 / alias / related domain 规则
```

不要复制：

```text
SkillTreeDetailedForm
TreeSkillForm
```

除非只是非常薄的 subclass/mixin 用于隐藏 tree context 已确定字段。

## 10.2 Tree context

从树中进入完整创建时，以下上下文由服务端固定：

```text
skill_project = tree.skill_project
primary_domain = 当前 TechnicalDomain
tree_version = 当前 tree
parent = 当前 placement 计算结果
```

用户不应重新选择：

```text
技能项目
主要技术领域
树版本
父节点
```

完整表单允许编辑：

```text
name
aliases
description
related_domains
difficulty
is_core
is_assessable
tags
is_active（按现有 SkillForm 规则决定是否展示）
order（见后面建议）
```

## 10.3 原子创建 + 挂树

如果现有 service 不能直接接受完整 `SkillForm` 数据，允许在 `standards/services.py` 增加一个薄 service，例如：

```python
@transaction.atomic
def create_detailed_skill_in_tree(
    *,
    tree_version,
    technical_domain,
    parent,
    skill,
    aliases,
    related_domains,
    actor,
):
    ...
```

要求：

1. 校验 `add_skill + domain scope`；
2. 校验 `add_skilltreenode + domain scope`；
3. 固定 skill project / primary domain；
4. `save_skill(...)`；
5. `attach_existing_skill_to_tree(...)`；
6. 任一步失败整笔回滚；
7. 不在 View 中手写事务流程；
8. 不改变现有 `SkillTreeNode` 模型。

## 10.4 保存成功

成功后：

- 关闭 drawer；
- 替换整个 `#skill-tree-panel`；
- 触发 `skillTreeNodeCreated`；
- 自动定位新节点；
- 不跳转到技能目录页。

---

# 11. Phase 7：节点 `⋯` 操作菜单

使用 DaisyUI dropdown/menu 很合适；**dropdown 只用于低频操作菜单，不再用于承载每节点常驻 quick form**。

建议：

```text
⋯
├─ 查看技能详情
├─ 编辑技能
├─────────────
├─ 添加同级技能
├─ 移动到……
├─ 上移
├─ 下移
├─────────────
└─ 从当前技能树移除
```

要求：

- 使用 `details/summary` 或 DaisyUI v5 支持的 dropdown 方式；
- menu 中按钮文字完整清晰；
- 上移/下移可保留 icon；
- 到达首/尾 sibling 时可以隐藏或 disabled；
- 不必为了判断首尾增加额外 N+1 查询；selector 构树时可顺带标记。

可在 selector decoration 中增加：

```text
node.can_move_up
node.can_move_down
```

由 sibling list 索引计算，不额外查数据库。

---

# 12. Phase 8：权限语义修正

当前 `node.can_add_child` 只看 `add_skilltreenode`，但用户可能只有“挂已有 Skill”的权限，没有 `add_skill`。

Workbench v2 需要明确拆分：

```text
can_add_tree_position
can_create_skill
```

建议：

```text
can_add_tree_position
= add_skilltreenode + domain scope

can_create_skill
= add_skill + domain scope
```

UI：

### 两者都有

```text
+ 添加子技能
输入或搜索技能名称
```

允许：

- 复用已有；
- 创建全新。

### 只有 add_skilltreenode

仍可：

```text
+ 添加子技能
```

但 inline editor 明确是：

```text
搜索已有技能……
```

当没有候选时提示：

```text
你可以将已有技能挂入此位置，但没有创建新技能的权限。
```

不要出现用户输入全新名称后才得到 403 的体验。

所有服务端权限检查继续保留；模板权限不是安全边界。

---

# 13. Phase 9：统一 side-dialog 的真正 modal 行为

当前 move/remove partial 使用：

```html
<dialog class="tms-side-dialog" open>
```

需要修正。

原因：

- `<dialog open>` 是非模态打开；
- 不进入浏览器 top layer；
- 页面其他区域不会自动 inert；
- `::backdrop` 不具有 `showModal()` 的真实 modal 语义；
- 与已有 Skill drawer 的 `showModal()` 行为不一致。

## 13.1 统一方式

Move / Remove / Tree full create / Tree skill edit 使用：

```html
<dialog class="tms-side-dialog" data-skill-tree-dialog ...>
```

不要硬编码 `open`。

HTMX 将 dialog fragment 放到：

```text
#skill-tree-dialog
```

之后 JS：

```javascript
dialog.showModal()
```

要求：

- 使用现有 `.tms-side-dialog` / `.tms-side-dialog-panel` CSS；
- body overflow lock；
- Esc 可关闭；
- 显式关闭按钮；
- backdrop 点击行为与现有 Skill drawer 保持一致；
- close 后清理 `#skill-tree-dialog` 内容；
- 不重复实现两套完全不同的 drawer controller。

可以提取小型通用 helper，但不要在本任务抽象成大型全站 modal framework。

---

# 14. Phase 10：编辑 Skill 本体

Workbench 的 `⋯ → 编辑技能` 修改的是长期 Skill。

优先方案：

```text
HTMX 打开 side drawer
复用 SkillForm
```

抽屉顶部必须提示：

```text
正在编辑长期技能属性。
名称、领域等修改会反映到引用该 Skill 的其他技能树版本和业务记录。
```

保存后：

- 刷新当前 tree panel；
- 同一个 Skill 在当前树中的名称/badge 立即更新；
- 不修改 SkillTreeNode.parent/order；
- 如果修改领域会使既有树位置失效，继续由现有 `set_skill_related_domains()` 拒绝；
- 不自动移动树节点。

如果复用现有 Skill edit 成本非常高，可以暂时保留跳转完整页面，但本 Plan 推荐完成 drawer 统一，以符合此前“routine create inline、full properties drawer”的产品约定。

---

# 15. Phase 11：Remove UI 精简

保留现有 service：

```text
remove_skill_tree_node(mode=promote_children/subtree)
```

只修 UI。

## 15.1 叶子 Skill

如果：

```text
descendant_count == 0
```

不要显示两个等价选项。

直接：

```text
从当前技能树移除「sudo 权限管理」？

此操作只移除当前版本中的树位置，不会删除长期 Skill，
也不会删除训练任务、Evidence 或评分关联。

[取消] [确认移除]
```

提交时直接使用安全的单节点移除模式。

## 15.2 有 children

才显示：

```text
○ 仅移除当前技能，并将 N 个直接子技能提升一级（推荐）
○ 移除整个分支，共 M 个树位置
```

选择 subtree 时：

- 显示二次确认；
- 必须明确总影响节点数；
- 不使用“删除技能”字样。

---

# 16. Phase 12：Move UI 微调

保留当前 service 和跨域校验。

Side drawer：

```text
调整树位置
Skill 名称

目标技术领域
目标父技能

[取消] [确认移动]
```

改进：

- parent choice 显示完整路径；
- 排除 self / descendants；
- 跨域失败时完整显示阻止移动的 Skill 名称；
- 不自动增加 related_domains；
- 成功后关闭 drawer + 刷新 panel + 定位刚移动的节点；
- 可以为 move 成功增加通用 node focus 事件，复用 locate helper。

---

# 17. Phase 13：Inline editor 的 HTMX 响应设计

本轮继续采用：

```text
成功写操作 → 刷新整个 #skill-tree-panel
```

这是当前规模下最可靠的策略。

HTMX 支持 `outerHTML` swap，当前无需为了“更高级”改成复杂 OOB branch patch。

## 17.1 Editor GET

返回：

```text
standards/partials/skill_tree_inline_editor.html
```

## 17.2 Candidate GET

只替换 editor 内候选区域：

```text
#skill-tree-inline-candidates
```

如果页面同时只能有一个 editor，可以使用稳定单一 ID。

## 17.3 Quick POST 成功

返回：

```text
skill_tree_panel.html
```

并：

```text
HX-Retarget: #skill-tree-panel
HX-Reswap: outerHTML
HX-Trigger-After-Swap:
{
  "skillTreeNodeCreated": {"nodeId": 123}
}
```

## 17.4 Quick POST 需要用户选择候选

返回 editor 本身：

- 保留输入值；
- 显示 candidates；
- 不创建 Skill；
- 不刷新整棵树。

---

# 18. Phase 14：前端 JS 收敛

当前已有：

```text
initSkillTreeWorkbench()
skillTreeNodeCreated
```

不要另建独立 bundle。

建议重构为几个小函数：

```text
focusSkillTreeNode(nodeId)
removeSkillTreeInlineEditor()
initSkillTreeInlineEditor(root)
initSkillTreeDialog(root)
initSkillTreeWorkbench(root)
```

## 18.1 `focusSkillTreeNode(nodeId)`

统一处理：

- locate existing；
- create success；
- move success（可选）；
- 打开 ancestors `<details>`；
- scroll；
- focus；
- 临时 highlight。

不要复制三份 scroll 逻辑。

## 18.2 Inline editor

支持：

```text
Esc
取消
打开新 editor 时关闭旧 editor
HTMX swap 后 autofocus
```

Enter：

- 普通 input 的 Enter 允许 form submit；
- candidate button 等不受破坏；
- textarea 只存在完整 drawer，不在 inline editor。

## 18.3 Dialog

动态 fragment 插入后：

```javascript
dialog.showModal()
```

close 时：

- body 恢复；
- 清理 dialog host；
- 焦点尽量返回触发按钮。

---

# 19. Phase 15：Skill.order 的轻量 UX 处理

本次不要删除 `Skill.order`，但避免用户误认为它控制技能树顺序。

至少完成一种：

### 推荐

在 `SkillForm` 中把 label 改成：

```text
技能目录排序
```

help text：

```text
仅影响技能目录等普通列表，不影响技能树中的位置和顺序。
```

或者：

- 普通前台 SkillForm 隐藏 order，使用默认值；
- admin 继续可维护。

本次不要迁移/删除字段。

---

# 20. Phase 16：模板文件建议

建议最终结构：

```text
standards/templates/standards/tree_detail.html

standards/templates/standards/partials/
  skill_tree_panel.html
  skill_tree_branch.html
  skill_tree_node_label.html
  skill_tree_node_actions.html
  skill_tree_inline_editor.html
  skill_tree_candidates.html
  skill_tree_move_dialog.html
  skill_tree_remove_dialog.html
  skill_tree_skill_form_dialog.html   # 如需要
```

删除或停止使用：

```text
skill_tree_quick_add.html
```

如果保留文件名，也必须改变语义为真正 inline editor，不能继续作为 dropdown 中的预渲染 form。

---

# 21. Phase 17：View 结构

保持 View 薄。

可以引入小型内部 helper：

```text
_resolve_tree_placement(...)
_tree_editor_context(...)
_render_tree_panel(...)
_tree_candidates(...)
```

但不要创造复杂 class hierarchy。

树动作仍属于：

```text
/trees/<tree_pk>/...
```

不要恢复独立：

```text
/nodes/
/nodes/create/
```

需要新增的 sibling/editor/full-create 路由必须 tree-scoped。

---

# 22. Phase 18：测试修正

现有 model/service 测试大部分保留。

本轮重点增加 **UX contract tests**，避免再次出现“功能通过但产品形态偏离”。

## 22.1 初始 tree detail 不预渲染 quick forms

构造多个节点，GET tree detail：

断言：

- 有 Skill rows；
- 有 `+`；
- 有 `⋯`；
- 没有每节点常驻完整 quick-add form；
- 没有旧 actions row；
- 没有 `description` / `confirm_distinct` quick form 字段。

不要使用过于脆弱的完整 HTML snapshot；用稳定 data attributes。

建议增加明确 markers：

```text
data-skill-tree-node-row
data-skill-tree-add-child
data-skill-tree-node-menu
data-skill-tree-inline-editor
```

## 22.2 Editor GET

测试：

- root editor GET 返回 inline editor；
- child editor GET 返回 inline editor；
- sibling editor GET 返回 inline editor；
- 正确 tree/domain/parent；
- 只有 name/input；
- 不含 description/confirm_distinct；
- 无权限 403。

## 22.3 无候选快速创建

POST：

```text
name=ACL 权限管理
```

断言：

- Skill created；
- SkillTerm created；
- SkillTreeNode correct parent；
- panel returned；
- `skillTreeNodeCreated` header。

## 22.4 Existing Skill

候选：

- attachable → “使用已有技能”；
- already in tree → “定位到已有技能” + node id；
- inactive → 不可挂；
- wrong domain → 明确提示；
- node-only permission → 可以复用已有，但不能创建新 Skill。

## 22.5 高相似

断言：

- inline candidate fragment 不再显示 description textarea；
- 不再显示 confirm_distinct checkbox；
- 显示“完整创建新技能”；
- 点击 full-create endpoint 返回 `SkillForm` drawer；
- full form 保存后 Skill + TreeNode 原子创建；
- aliases / related_domains 等正常保存。

## 22.6 添加同级

分别测试：

```text
root sibling → parent=None
child sibling → parent=current.parent
```

## 22.7 Locate contract

服务器 fragment 至少提供：

```text
data-skill-tree-locate-node="<id>"
```

或者等价稳定 data attribute，供 JS 使用。

## 22.8 Remove

测试：

- leaf dialog 不显示两种 mode；
- parent dialog 显示两种；
- subtree 仍要求二次确认；
- 文案不出现“删除 Skill”误导语义。

## 22.9 Dialog

模板断言：

- `<dialog>` 不硬编码 `open`；
- 有 `data-skill-tree-dialog`；
- JS 包含 `showModal()` 初始化路径。

不需要引入浏览器 E2E 框架。

## 22.10 Query / DOM 规模

保留当前 query count 测试。

补一个轻量结构测试：

- 例如 30 个节点；
- tree detail 初始 HTML 中 quick-add `<form>` 数量不能与节点数线性增长；
- 初始页面不预渲染 30 份 quick form。

---

# 23. Phase 19：验证命令

本轮主要影响 standards + frontend。

按 `AGENTS.md` 的比例验证原则执行。

先：

```bash
uv run pytest standards/test_skill_tree.py -q
uv run ruff check standards
uv run manage.py check
```

因为模板/JS/Tailwind/Iconify 发生变化：

```bash
npm run build:css
```

再运行：

```bash
uv run pytest standards -q
```

如果本轮没有改模型：

```bash
uv run manage.py makemigrations --check --dry-run
```

必须确认：

```text
No changes detected
```

如果出现新的 migration：

> 先停止，不要自动接受。  
> 本 Workbench v2 正常情况下不应该产生 schema migration。

准备合并前根据影响范围再运行：

```bash
uv run pytest
uv run ruff check .
```

---

# 24. 明确禁止的过度实现

本次不要：

1. 修改 SkillTreeNode schema；
2. 修改 `0004_simplify_skill_tree_nodes.py`；
3. 恢复 CATEGORY/TOPIC；
4. 新增 Group 类型；
5. 新增 Skill code；
6. 新增 Node code；
7. 引入 SortableJS；
8. 实现 drag & drop；
9. 引入 React/Vue/Svelte tree；
10. 引入 MPTT/treebeard；
11. 实现 SkillTreeVersion freeze/publish；
12. 实现版本克隆；
13. 实现父 Skill 分值/掌握度汇总；
14. 实现大树虚拟化；
15. 实现 Tab/F2/Delete 全套思维导图快捷键；
16. 无关重构其他 APP；
17. 因为“可能未来使用”而新增通用 tree framework；
18. 将 HTMX 页面改成 SPA。

---

# 25. 关键验收场景

## 场景 A：空领域创建根 Skill

页面：

```text
Linux
+ 添加根技能
```

点击：

```text
Linux
● [ 输入或搜索技能名称…… ]
```

输入：

```text
系统管理
```

Enter：

```text
Linux
└─ 系统管理                           + ⋯
```

没有 dropdown form。

## 场景 B：直接创建子 Skill

```text
系统管理                               + ⋯
```

点 `+`：

```text
系统管理                               + ⋯
└─ ● [ 输入或搜索技能名称…… ]
```

输入“用户与权限管理”，Enter 后：

```text
系统管理
└─ 用户与权限管理                      + ⋯
```

## 场景 C：新增同级

```text
用户与权限管理                         + ⋯
└─ sudo
```

在 sudo 的 `⋯`：

```text
添加同级技能
```

出现：

```text
用户与权限管理
├─ sudo
└─ ● [ 输入或搜索技能名称…… ]
```

输入 PAM 后：

```text
用户与权限管理
├─ sudo
└─ PAM
```

## 场景 D：复用已有 Skill

已有技能目录：

```text
sudo 权限管理
```

树中输入：

```text
sudo
```

显示：

```text
可能已有：
sudo 权限管理     [使用已有技能]
```

点击后不创建新 Skill。

## 场景 E：已经存在于本版本

输入一个已经挂在其他分支的 Skill：

```text
已在当前版本：
系统管理 / 用户与权限管理 / sudo 权限管理

[定位到已有技能]
```

点击：

- 关闭 inline editor；
- 打开 ancestors；
- 滚动；
- 高亮已有 node。

## 场景 F：高相似新 Skill

输入：

```text
Linux 用户和组管理
```

候选：

```text
Linux 用户管理          [使用已有]
Linux 用户与组管理      [使用已有]

[完整创建新技能]
```

点完整创建：

- side drawer；
- 完整 SkillForm；
- aliases / description / related_domains / difficulty / core / assessable / tags 可维护；
- 保存成功后直接挂到原 placement；
- 返回树并高亮。

## 场景 G：只有挂载权限

用户拥有：

```text
add_skilltreenode
```

没有：

```text
add_skill
```

可以：

```text
搜索已有 → 使用已有
```

不能：

```text
输入一个新名称 → 最后才 403
```

页面应提前提示无创建权限。

## 场景 H：节点视觉

有 100 个节点时：

- Skill 名称仍是主体；
- 没有 100 行“查看/编辑/新增/移动/↑/↓/删除”；
- 没有 100 份预渲染 quick form；
- 每行只有必要的 `+ / ⋯`；
- 初始 DOM 保持轻量。

## 场景 I：Move / Remove 真正 modal

点击移动或移除：

- 使用 `showModal()`；
- 有 backdrop；
- 页面其余区域 inert；
- Esc 正常关闭；
- close 后焦点合理返回；
- 不使用单纯 `<dialog open>`。

---

# 26. Definition of Done

只有同时满足以下条件才算完成：

- [ ] Skill / SkillTreeNode 模型未被重新设计。
- [ ] 没有新增 schema migration。
- [ ] 技能树初始页面不再为每个 node 预渲染 quick-add form。
- [ ] Domain root add 使用树内 inline editor。
- [ ] Node `+` 使用树内 inline child editor。
- [ ] 已补“添加同级技能”。
- [ ] Inline editor 默认只包含名称输入/候选，不包含 description/confirm_distinct。
- [ ] 无候选时仍可一键原子创建 Skill + TreeNode。
- [ ] Existing Skill 可直接复用。
- [ ] Current-tree duplicate 提供“定位到已有技能”。
- [ ] 高相似但新建时进入完整 SkillForm drawer。
- [ ] 完整创建成功后自动挂回原树位置。
- [ ] Node UI 收敛为 Skill 信息 + `+` + `⋯`。
- [ ] 不再常驻显示一整排 CRUD actions。
- [ ] Move / Remove / Full Create drawer 使用 `showModal()`。
- [ ] Leaf remove UI 已简化。
- [ ] Parent remove 仍支持 promote/subtree 且 subtree 二次确认。
- [ ] node-only permission 用户不会被误导为可创建新 Skill。
- [ ] 新增/定位/移动后的 node 可自动展开、滚动和高亮。
- [ ] 查询数没有新增递归 N+1。
- [ ] 大节点数页面不线性预渲染大量 form。
- [ ] `uv run pytest standards/test_skill_tree.py -q` 通过。
- [ ] `uv run pytest standards -q` 通过。
- [ ] `uv run ruff check standards` 通过。
- [ ] `uv run manage.py check` 通过。
- [ ] `uv run manage.py makemigrations --check --dry-run` 无新 migration。
- [ ] `npm run build:css` 通过。

---

# 27. 推荐提交边界

建议拆为 3～5 个可审阅提交：

```text
refactor(standards): render compact skill tree node rows
feat(standards): add true inline skill tree editing
feat(standards): reuse full skill form from tree workflow
fix(standards): unify tree dialogs and removal UX
test(standards): lock workbench v2 interaction contracts
```

不要再次把模型、其他训练主线 APP、工作台 UI 全塞进一个新的超大提交。

---

# 28. 实现参考与版本原则

本任务继续使用仓库当前依赖，不做版本升级：

```text
Django 6
Python 3.13
django-htmx
django-tables2
Tailwind CSS 4
DaisyUI 5
Alpine CSP
Iconify
```

实现时遵循当前官方能力：

- HTMX：fragment + `hx-target` / `hx-swap="outerHTML"` / response trigger；
- DaisyUI：dropdown 适合低频 `⋯` 菜单，不用于承载每节点常驻 quick form；
- 原生 `<dialog>`：动态加载后通过 `showModal()` 打开真正 modal；
- Tailwind CSS 4：class 使用可静态扫描的完整字符串；
- Iconify：使用完整静态 `icon-[...]` class；
- Alpine CSP：本页没有必要为简单树编辑额外引入 Alpine 状态；优先延续当前 `app.js` + data attributes。

最终原则：

> **树结构本身就是工作界面。常规新增必须直接发生在树上；复杂 Skill 属性才进入 drawer。**
>
> **不要再把“在树上编辑”实现成“在树旁边打开很多 CRUD 表单”。**
