# TMS 技能与技能树简化及树形工作台实施 Plan

> **文档性质**：可供 Codex 直接执行的工程实施计划  
> **目标仓库**：`hdaojin/tms`  
> **目标分支**：`feature/training-domain-refactor`  
> **基线状态**：截至 2026-08-20，该分支相对 `develop` ahead 1 / behind 0；`develop` 基线提交为 `b343872`  
> **实施性质**：在尚未合并的训练主线重构分支上继续完成标准体系收敛；允许按原重构计划进行破坏性 schema 调整，当前不要求兼容旧训练主线开发数据  
> **核心目标**：把“技能树节点”从带业务类型的对象收缩为“稳定 Skill 在某一技能树版本中的位置关系”，并把技能树详情页升级为可直接录入、调整、移除 Skill 的树形工作台。

---

# 0. 执行契约

本 Plan 的业务设计已经确定。Codex 执行时不得重新讨论或重新发明以下语义：

1. `Skill` 是跨技能树版本长期稳定的核心业务对象。
2. `Skill` 可以是任意粒度的能力单元，不要求一定是叶子技能。
3. 一个 Skill 可以在某一技能树版本中拥有子 Skill；是否存在子节点不改变它“仍然是 Skill”的身份。
4. 不再在模型层定义“分类 / 主题 / 分组 / 技能节点”等节点类型。
5. 技术领域 `TechnicalDomain` 是技能树的视觉与权限分区，不是一个 `SkillTreeNode`。
6. 一个技能树版本在每个技术领域下可以有多个根 Skill；树深度不设业务上限。
7. `SkillTreeNode` 只负责：
   - 技能树版本；
   - 技术领域中的放置位置；
   - 父子关系；
   - 同级顺序；
   - 指向稳定 Skill。
8. 技能树父子关系只表达组织、归类、细化关系，不自动表达：
   - 分数汇总；
   - 掌握度汇总；
   - `is_assessable` 继承；
   - `difficulty` 继承；
   - `is_core` 继承。
9. `Skill.is_assessable` 与是否有子 Skill 完全独立；父 Skill 也可以是可考核 Skill。
10. 删除技能树中的节点，默认只删除 `SkillTreeNode` 位置关系，不删除对应长期 `Skill`。
11. Skill 改名属于修改长期 Skill，本次不做节点级名称快照；改名会反映到引用该 Skill 的所有技能树版本。
12. 同一个 Skill 在同一个 `SkillTreeVersion` 中仍只允许挂载一次；同一个 Skill 可以挂载到不同技能树版本。
13. 技能树父子边保持在同一 `TechnicalDomain`；跨领域相关性继续通过 `Skill.primary_domain / related_domains` 表达。
14. 跨技术领域移动一个节点/子树时，不得静默修改 Skill 的领域归属；只有当整棵子树中的 Skill 已允许目标领域时才可移动。
15. 本次不新增 MPTT、treebeard、第三方树组件或大型前端框架；继续使用 Django 自关联邻接表。
16. 本次不实现拖拽排序；先完成稳定、可测试的“树内快速新增 + 移动 + 上下调整 + 移除”交互。
17. 本次不新增 SkillTreeVersion 冻结/发布状态；“被 TrainingCycle 引用后何时冻结版本”列为后续独立设计议题。
18. 本次不调整 `Skill.difficulty / is_core / is_assessable / tags / order / is_active` 的业务定义，避免扩大范围。
19. 不升级 Django、HTMX、Tailwind、DaisyUI、Alpine、Iconify 等依赖版本；最新官方文档只作为实现语义参考，实际依赖以仓库 lock/package 配置为准。

---

# 1. 开始执行前的基线确认

先从仓库根目录执行：

```bash
git fetch origin
git switch feature/training-domain-refactor
git pull --ff-only origin feature/training-domain-refactor
git status --short
git log -1 --oneline
git rev-list --left-right --count develop...HEAD
```

要求：

- 当前分支必须是 `feature/training-domain-refactor`；
- 不覆盖用户已有未提交修改；
- 若 `git status --short` 非空，先识别是否属于本任务，不得直接 `git reset --hard`；
- 若分支已不再是 ahead 1 / behind 0，则先检查新的相关改动并吸收到本 Plan，不要覆盖后续有效修改。

开始编码前必须阅读：

```text
AGENTS.md
CONTEXT.md
docs/adr/
docs/agents/plan/TMS-训练主线重构实施Plan.md
```

当前原训练主线 Plan 已明确：当前没有重要业务数据，允许重建受影响 APP 的 migration history，也允许开发/测试环境重建数据库，但必须保证空数据库从零 `migrate` 成功。因此本 Plan 不为当前开发数据编写复杂兼容迁移。

---

# 2. 先做一次精确依赖审计

在修改模型前执行：

```bash
rg -n \
  "display_code|SkillTreeNode\.NodeType|NodeType\.|node_type|uniq_skilltreenode_version_code|node\.code|get_node_type_display|display_name|get_full_path|SkillTreeNodeForm|SkillTreeNodeTable|node_list|node_create|node_detail|node_edit|SK-[0-9]|SK-待生成" \
  standards core training assessments evidence scoring docs \
  --glob '!**/__pycache__/**'
```

同时检查：

```bash
rg -n "SkillTreeNode|skilltreenode" . \
  --glob '!media/**' \
  --glob '!media-private/**' \
  --glob '!.uv-cache/**' \
  --glob '!node_modules/**'
```

目的：

- 找出所有 Skill 编号展示；
- 找出所有固定 CATEGORY / TOPIC / SKILL 逻辑；
- 找出树节点代码 `code` 的排序、路径、模板和测试依赖；
- 找出节点独立 CRUD 路由与导航；
- 找出权限包中的 SkillTreeNode 权限；
- 找出其他 APP 是否直接依赖节点字段。

不要只修改 `standards/models.py` 后依赖测试偶然发现遗漏。

---

# 3. Phase 1：简化 Skill 的用户身份

## 3.1 删除 `Skill.display_code`

修改 `standards/models.py`：

删除：

```python
@property
def display_code(self):
    return f"SK-{self.pk:06d}" if self.pk else "SK-待生成"
```

将：

```python
def __str__(self):
    return f"{self.display_code} - {self.name}"
```

改为：

```python
def __str__(self):
    return self.name
```

原则：

- 不新增替代用户编号；
- 数据库 `pk` 仍是内部标识；
- 将来若确有跨系统稳定公开标识需求，再独立设计 UUID/public id；
- 本次不要用 `pk` 重新包装成其他用户可见编号。

## 3.2 清理全部 Skill 编号展示

至少检查并修改：

```text
standards/admin.py
standards/tables.py
standards/views.py
standards/templates/standards/skill_detail.html
standards/templates/standards/partials/skill_candidates.html
standards/templates/standards/partials/skill_results.html
standards/templates/standards/partials/skill_create_*.html
standards/tests.py
CONTEXT.md
docs/user-manual/standards/overview.md
```

具体要求：

- `SkillAdmin.list_display` 删除 `display_code`；
- `SkillTable` 删除“编号”列；
- 技能详情页标题只显示技能名称；
- 技能详情面包屑最后一级显示技能名称；
- 候选技能卡不再显示 `SK-xxxxxx`；
- 新增成功提示改为：`已新增技能「xxx」。`；
- Form 错误中通过 `__str__` 展示 Skill 时自然显示名称；
- 删除 `test_save_skill_registers_primary_name_and_aliases` 中针对 `display_code` 的断言；
- 新增测试确保页面不再输出旧 Skill 编号语义。

不要删除 `SkillTerm`；正式名称/别名唯一性仍是 Skill 人类识别的核心机制。

---

# 4. Phase 2：把 SkillTreeNode 收缩为纯位置关系

## 4.1 目标模型

将 `SkillTreeNode` 收敛为概念上如下结构：

```python
class SkillTreeNode(models.Model):
    tree_version = models.ForeignKey(
        SkillTreeVersion,
        verbose_name="技能树版本",
        on_delete=models.CASCADE,
        related_name="nodes",
    )
    technical_domain = models.ForeignKey(
        TechnicalDomain,
        verbose_name="技术领域",
        on_delete=models.PROTECT,
        related_name="skill_tree_nodes",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="父技能",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    skill = models.ForeignKey(
        Skill,
        verbose_name="技能",
        on_delete=models.PROTECT,
        related_name="tree_nodes",
    )
    order = models.PositiveIntegerField("排序", default=0)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("最后更新时间", auto_now=True)
```

从 `SkillTreeNode` 删除：

```text
NodeType
node_type
code
name
description
is_active
display_name
is_skill()
```

保留：

```text
skill_project property
get_ancestors()
get_descendants()
get_full_path()
```

但更新其语义：

- `get_full_path()` 只拼接 `node.skill.name`；
- `get_descendants()` 同级排序只使用 `order, pk`；
- `__str__()` 返回 `self.skill.name` 或含树版本/领域的易读字符串，不再返回节点代码。

## 4.2 Meta 与唯一约束

删除：

```text
uniq_skilltreenode_version_code
```

保留并改成无条件唯一约束：

```python
models.UniqueConstraint(
    fields=["tree_version", "skill"],
    name="uniq_skilltreenode_version_skill",
)
```

因为 `skill` 最终不再允许 NULL，所以无需条件 `Q(skill__isnull=False)`。

模型默认 ordering 不要试图表达树的 preorder。可使用稳定、简单的默认顺序，例如：

```python
ordering = [
    "tree_version",
    "technical_domain__order",
    "order",
    "pk",
]
```

真正的树顺序由 selector 在每个 siblings 列表中按：

```text
order, pk
```

构建。

## 4.3 Model 校验

删除所有固定三层类型校验，包括：

```text
根节点只能 CATEGORY
CATEGORY 下只能 TOPIC / SKILL
TOPIC 下只能 SKILL
SKILL 不能有 children
非 SKILL 不能挂 Skill
```

最终保留以下业务不变量：

1. `technical_domain.skill_project == tree_version.skill_project`；
2. `skill.skill_project == tree_version.skill_project`；
3. 节点 `technical_domain` 必须是 Skill 的：
   - `primary_domain`，或
   - `related_domains` 之一；
4. 父节点必须属于同一 `tree_version`；
5. 父节点必须属于同一 `technical_domain`；
6. 父节点不能是自身；
7. 父节点不能是自身后代；
8. 根节点允许任意 Skill；
9. 任意 Skill 节点允许继续拥有子 Skill。

继续保留当前防环逻辑，并补充覆盖任意深度的测试。

本次不要顺手改造整个项目的 `save() -> clean()` 风格；`SkillTreeNode` 当前已依赖保存时校验，保持行为连续并用测试保护即可。跨模型写工作流仍必须通过 service。

---

# 5. Phase 3：迁移策略

## 5.1 不做旧 CATEGORY/TOPIC 数据转换

原训练主线重构 Plan 已明确：当前没有重要业务数据，可以要求开发/测试数据库重建。

因此本次不要为了当前开发库中的 CATEGORY/TOPIC 节点写复杂数据迁移，也不要自动把旧分类/主题转换成 Skill。

原因：

- 旧分类/主题是否应复用已有 Skill 需要业务判断；
- 自动转换容易制造错误的长期 Skill；
- 该分支尚处于领域重构阶段，当前数据不具有保留价值。

## 5.2 新增清晰 schema migration

优先新增下一号 `standards` migration，例如：

```text
standards/migrations/0004_simplify_skill_tree_nodes.py
```

完成：

- 删除 `node_type`；
- 删除 `code`；
- 删除 `name`；
- 删除 `description`；
- 删除 `is_active`；
- 将 `skill` 改为 `null=False, blank=False`；
- 删除节点代码唯一约束；
- 调整 `(tree_version, skill)` 唯一约束；
- 调整 Meta ordering。

不要为非空 `skill` 写伪默认 Skill。

如果现有本地数据库存在旧节点，迁移失败是预期情况；按原重构契约重建开发数据库。

## 5.3 空数据库验证是硬要求

最终必须验证：

```bash
uv run manage.py makemigrations --check --dry-run
uv run manage.py migrate --noinput
```

如果当前开发 DB 因旧节点无法迁移，先按 README/当前重构流程重建本地开发 DB，再验证全新数据库迁移链。

---

# 6. Phase 4：建立技能树读取 Selector，禁止模板递归 N+1

在 `standards/selectors.py` 增加专门的技能树读取逻辑，名称可按现有命名风格确定，例如：

```python
skill_tree_structure(...)
```

目标：

一次性读取：

```python
SkillTreeNode.objects.filter(tree_version=tree_version).select_related(
    "skill",
    "technical_domain",
    "parent",
)
```

必要时预取：

```text
skill.related_domains
```

然后在 Python 内存中构建：

```text
TechnicalDomain
  roots[]
    node
      children[]
```

要求：

1. TechnicalDomain 只作为视觉分组，不创建伪节点；
2. 同级节点按 `order, pk`；
3. 根节点 `parent_id is None`；
4. 模板不调用 `node.children.all`；
5. 模板不在递归过程中继续访问数据库；
6. 任意深度可渲染；
7. 即使 Skill 已停用，只要它存在于该技能树版本中仍必须显示，并加“已停用”提示，不能静默从历史结构中消失；
8. 返回结构中应能给模板提供：
   - Skill；
   - SkillTreeNode id；
   - children；
   - 是否有 children；
   - 当前用户是否有该节点对应操作权限。

不要引入 django-mptt/treebeard；当前规模使用邻接表 + 单次查询 + 内存构树足够。

---

# 7. Phase 5：树节点写操作统一进入 standards/services.py

不要继续让通用 `CreateView/UpdateView` 直接操作 `SkillTreeNode`。

新增明确的领域 service。命名可按现有 service 风格微调，但职责必须清晰。

## 7.1 创建新 Skill 并挂入树

概念接口：

```python
create_skill_in_tree(
    *,
    tree_version,
    technical_domain,
    parent,
    name,
    actor,
    description="",
    confirm_distinct=False,
    ...,
)
```

行为：

1. 校验 actor 拥有 `standards.add_skill`；
2. 校验 actor 拥有 `standards.add_skilltreenode`；
3. 校验 actor 有权维护目标 TechnicalDomain；
4. 校验 parent（若有）属于同一 tree_version/domain；
5. 调用现有 `find_skill_candidates()`；
6. 精确命中已有 Skill 时：
   - 不创建重复 Skill；
   - 转入“挂载已有 Skill”流程；
7. 高相似但非精确命中时：
   - 不允许无提示直接创建；
   - 要求走已有 `SkillForm` 的 `confirm_distinct + description` 规则；
8. 确认是新 Skill 时，通过现有 `save_skill()` 创建 Skill 与 SkillTerm；
9. 新 Skill 默认：
   - `skill_project = tree_version.skill_project`；
   - `primary_domain = technical_domain`；
   - 其他字段使用当前模型默认值；
10. 创建 `SkillTreeNode`；
11. 节点 `order` 默认取同级最大 order + 10；
12. 整个过程使用 `transaction.atomic()`；
13. 任一步失败不得留下孤立 Skill。

## 7.2 挂载已有 Skill

概念接口：

```python
attach_existing_skill_to_tree(...)
```

必须验证：

- Skill 与树属于同一 SkillProject；
- Skill 为 active 才允许新增挂载；
- 目标 TechnicalDomain 是其 primary/related domain；
- Skill 尚未在当前 SkillTreeVersion 中存在；
- parent 合法；
- actor 有节点新增权限与目标领域维护范围。

如果 Skill 已经在当前版本中存在，返回中文业务错误，并提供现有节点路径供 UI 提示，不得创建第二个节点。

## 7.3 移动/重新归类

概念接口：

```python
move_skill_tree_node(
    *,
    node,
    new_parent,
    target_domain,
    actor,
)
```

支持：

- 移动为同领域根节点；
- 移动到任意同领域 Skill 下；
- 在满足条件时将整棵子树移动到另一个 TechnicalDomain。

校验：

1. `new_parent` 不能是 node 自身；
2. `new_parent` 不能是 node 后代；
3. `new_parent` 必须属于同一个 tree_version；
4. 若跨域移动：
   - actor 必须同时有源领域和目标领域的管理范围；
   - node 与所有 descendants 的 Skill 都必须已经允许目标 TechnicalDomain；
   - 不得自动修改任一 Skill 的 `primary_domain / related_domains`；
5. 跨域移动成功后，在事务中统一更新整棵子树的 `technical_domain`；
6. 移动后默认放到目标 siblings 末尾；
7. 不改变 Skill 本体。

## 7.4 同级排序

增加简单、稳定的上移/下移操作，不实现拖拽。

可采用：

```python
move_tree_node_up(...)
move_tree_node_down(...)
```

或统一 reorder service。

要求：

- 只在同一 parent + technical_domain + tree_version 的 siblings 内调整；
- 使用事务；
- 必要时把 siblings order 归一化为 `10, 20, 30...`；
- 不依赖节点代码。

## 7.5 从树中移除

概念接口：

```python
remove_skill_tree_node(*, node, mode, actor)
```

支持两种模式：

### `promote_children`

“仅从树中移除当前 Skill，并提升子技能”

```text
A
└─ B
   ├─ C
   └─ D
```

移除 B 后：

```text
A
├─ C
└─ D
```

若 B 是根节点，则 C/D 成为该 TechnicalDomain 的根节点。

### `subtree`

“从当前技能树版本中移除整个分支”

删除 B 及所有 descendant 的 `SkillTreeNode`。

无论哪种模式：

- 都不得删除 `Skill`；
- 有 children 的节点不能通过无提示的普通 `DELETE` 直接级联；
- UI 必须明确显示将影响多少个子节点；
- `subtree` 必须二次确认；
- 需要 `standards.delete_skilltreenode` 权限。

保留 `parent.on_delete=CASCADE`，因为删除整个 SkillTreeVersion 或明确删除 subtree 时仍有意义；默认单节点移除由 service 先重新挂接 children，再删除节点。

---

# 8. Phase 6：删除独立“技能节点 CRUD”用户入口

`SkillTreeNode` 已变成内部结构对象，不应该继续作为一个独立业务模块让用户理解。

## 8.1 删除通用 Form

删除：

```text
SkillTreeNodeForm
```

改成针对工作台动作的普通 Form，例如：

```text
SkillTreeQuickAddForm
SkillTreeMoveForm
SkillTreeRemoveForm（如确有需要）
```

Form 只暴露用户真正需要填写的内容。

快速新增时：

```text
用户输入：name
系统上下文：tree_version / technical_domain / parent
```

不要要求用户重新选择已经由页面上下文确定的：

```text
技能项目
技能树版本
技术领域
父节点
节点类型
节点代码
order
```

## 8.2 删除 django-tables2 节点表

删除：

```text
SkillTreeNodeTable
```

技能树不再用 flat table 作为主要呈现。

django-tables2 继续用于项目、技能目录、技能树版本等真正的列表页，不要为了“统一技术栈”强行用表格渲染树。

## 8.3 删除独立节点 View / URL / Template

删除或废弃用户入口：

```text
SkillTreeNodeListView
SkillTreeNodeDetailView
SkillTreeNodeCreateView
SkillTreeNodeUpdateView

/nodes/
/nodes/create/
/nodes/<pk>/
/nodes/<pk>/edit/

standards/templates/standards/node_detail.html
```

所有树结构维护从：

```text
/trees/<tree_pk>/
```

进入。

不要为旧节点 CRUD 保留重定向兼容层；该分支尚未合并，避免形成第二套长期入口。

---

# 9. Phase 7：把 tree_detail.html 改造成“技能树工作台”

## 9.1 页面总体结构

页面示意：

```text
网络系统管理技能树 · 2026
当前版本

Linux                                      + 新增根技能
├─ 系统管理                                  ⋯
│  ├─ 用户与权限管理                          +  ⋯
│  │  ├─ 用户和用户组管理                     ⋯
│  │  ├─ sudo 权限管理                        ⋯
│  │  └─ PAM                                 ⋯
│  └─ 软件包管理                              ⋯
└─ 网络服务                                   ⋯
   ├─ DNS                                    +  ⋯
   │  ├─ 权威 DNS                             +  ⋯
   │  │  ├─ 主服务器配置                       ⋯
   │  │  └─ 从服务器配置                       ⋯
   │  └─ DNSSEC                               ⋯
   └─ DHCP                                    ⋯

Windows                                    + 新增根技能
...

Network                                    + 新增根技能
...
```

视觉上只有：

```text
TechnicalDomain
└─ Skill
   └─ Skill
      └─ Skill
```

不要再出现：

```text
CATEGORY
TOPIC
SKILL node type
节点代码
```

## 9.2 模板拆分

建议：

```text
standards/templates/standards/tree_detail.html
standards/templates/standards/partials/skill_tree_panel.html
standards/templates/standards/partials/skill_tree_domain.html
standards/templates/standards/partials/skill_tree_branch.html
standards/templates/standards/partials/skill_tree_quick_add.html
standards/templates/standards/partials/skill_tree_candidates.html
standards/templates/standards/partials/skill_tree_remove_dialog.html
standards/templates/standards/partials/skill_tree_move_dialog.html
```

允许根据最终实现减少文件数量，但必须避免把整个工作台堆成单个超长模板。

## 9.3 递归显示

可使用 Django 模板递归 include，但递归对象必须来自 selector 已构造好的内存 children 列表。

每层固定使用可被 Tailwind 静态扫描的 class，例如：

```html
<ul class="ml-5 border-l border-base-300 pl-3">
```

禁止：

```html
<div class="ml-{{ depth }}">
<div class="pl-{{ depth|... }}">
```

因为 Tailwind 4 按源文本静态检测 class，不支持这种运行时拼接。

## 9.4 展开/折叠

优先使用原生 `<details>/<summary>` 配合 DaisyUI 5 collapse 或简洁自定义样式。

要求：

- 有 children 的 Skill 可展开/折叠；
- 默认首次进入全部展开，方便录入时观察完整结构；
- 新增节点后自动展开其祖先；
- 叶子节点不渲染无意义折叠控件；
- 保持键盘可访问性。

不要为了折叠引入第三方 JS tree library。

## 9.5 节点视觉信息

每个 Skill 行至少展示：

- Skill.name；
- 可选 badge：核心 / 可考核 / 已停用；
- children 展开控制；
- `+` 新增子技能；
- `⋯` 操作菜单。

操作菜单按权限显示：

```text
查看技能详情
编辑技能
新增子技能
新增同级技能
移动
上移
下移
从树中移除
```

不要显示数据库 id。

使用 Iconify Tailwind 4 的静态完整 class，例如：

```text
icon-[tabler--plus]
icon-[tabler--target]
icon-[tabler--chevron-right]
icon-[tabler--dots]
icon-[tabler--arrow-up]
icon-[tabler--arrow-down]
icon-[tabler--trash]
```

不要动态拼 Iconify class。

---

# 10. Phase 8：实现“思维导图式”树内快速新增

## 10.1 交互目标

用户点击任意节点的 `+`：

```text
用户与权限管理
├─ sudo 权限管理
├─ PAM
└─ [ 输入技能名称…… ]
```

输入名称后按 Enter 即可创建/挂载。

点击 TechnicalDomain 标题右侧“新增根技能”时，在该领域根部出现同样的输入框。

必须支持：

```text
Enter  提交
Esc    取消
```

本次不强制实现全局 Tab/Enter 思维导图快捷键；避免与页面其他输入控件冲突。

## 10.2 HTMX 工作流

推荐每次树写操作完成后刷新整个 `#skill-tree-panel`：

- 当前规模足够小；
- selector 是单次读取 + 内存构树；
- 比维护复杂局部分支 OOB 一致性更可靠。

响应使用：

```text
hx-target="#skill-tree-panel"
hx-swap="outerHTML"
```

必要时可使用 `hx-swap-oob` 同时更新提示区，但不要把整个交互做成多层 OOB 拼装。

创建成功后设置：

```text
HX-Trigger-After-Swap: skillTreeNodeCreated
```

事件 detail 至少包含：

```json
{"nodeId": 123}
```

前端脚本：

1. 找到 `#skill-tree-node-123`；
2. 打开所有祖先 `<details>`；
3. `scrollIntoView({behavior: "smooth", block: "center"})`；
4. 临时加高亮 outline/background；
5. 焦点回到合理位置。

复用 `static/js/app.js` 里现有 `skillCreated` / `htmx:afterSwap` 的组织方式，不要另起一套页面级 bundle。

## 10.3 候选 Skill 与去重

快速输入时复用：

```text
find_skill_candidates()
normalize_skill_term()
SkillTerm
save_skill()
```

交互规则：

### 精确命中

如果输入正式名称或别名精确命中现有 Skill：

- 不创建新 Skill；
- 若该 Skill 可挂入当前领域且尚未在当前版本中存在：显示/执行“使用已有技能”；
- 若已存在于当前树版本：提示现有路径并提供“定位到节点”；
- 若 Skill 已停用：显示已停用，不直接挂载。

### 高相似候选

如果存在高相似但非精确候选：

- 在输入框下方显示候选；
- 用户可“使用已有技能”；
- 若确认必须创建新 Skill，进入完整创建面板/抽屉；
- 完整创建继续使用现有 `SkillForm` 的：
  - `confirm_distinct`；
  - description 必填边界说明；
  - aliases；
  - 领域校验。

### 无明显候选

直接使用名称创建 Skill + SkillTreeNode；其他 Skill 属性使用当前模型默认值，用户可后续进入技能详情编辑。

---

# 11. Phase 9：完整 Skill 编辑与“树位置编辑”严格分开

这是避免用户误解的关键。

## 11.1 编辑 Skill 本体

操作“编辑技能”修改的是：

```text
name
description
primary_domain
related_domains
difficulty
is_core
is_assessable
tags
is_active
aliases
```

这些都是长期 Skill 属性，会影响所有引用该 Skill 的技能树版本和其他业务页面。

如果在技能树页使用侧边抽屉编辑，必须在抽屉顶部明确提示：

```text
正在编辑长期技能属性；技能名称等修改会同步反映到其他技能树版本。
```

尽量复用当前技能目录已有：

```text
SkillForm
skill_form_panel.html
tms-side-dialog
现有 drawer JS 模式
```

不要复制第二套 Skill 表单业务逻辑。

若复用成本明显高于价值，可以第一版继续链接现有 `standards:skill_edit` 完整页面；但树内“快速新增”必须留在同一页面。

## 11.2 编辑树位置

“移动 / 上移 / 下移 / 从树移除”只修改 `SkillTreeNode`，不得修改 Skill 本体。

页面文案必须区分：

```text
编辑技能
调整树位置
从当前技能树移除
```

不要继续使用模糊的“编辑节点”。

---

# 12. Phase 10：树移动与删除 UI

## 12.1 移动

点击“移动”打开轻量对话框/侧边面板。

字段：

```text
目标技术领域
目标父技能（可为空，表示根）
```

父技能下拉项显示完整路径，例如：

```text
系统管理 / 用户与权限管理
网络服务 / DNS / 权威 DNS
```

候选列表必须排除：

```text
自身
自身 descendants
其他 tree_version
不合法 technical_domain
```

如果跨域子树有 Skill 不允许目标领域，服务端拒绝，并在 UI 列出阻止移动的 Skill 名称；不要自动把目标领域加入 related_domains。

## 12.2 从树移除

叶子 Skill：

```text
从当前技能树移除「sudo 权限管理」？
该操作不会删除技能本身及其训练、考核、Evidence 数据。
```

有 children 的 Skill：

必须让用户选择：

```text
A. 仅移除当前技能，并将 4 个子技能提升一级（推荐）
B. 移除整个分支，共 12 个树节点
```

B 必须二次确认。

任何文案都不要写成“删除技能”，除非用户真的进入 Skill 本体删除流程；本次不新增 Skill 硬删除入口。

---

# 13. Phase 11：URL 与 View 设计

保留：

```text
/trees/
/trees/create/
/trees/<pk>/
/trees/<pk>/edit/
```

新增工作台动作路由，具体 path 名称可按现有风格微调，但建议保持 tree scope，例如：

```text
/trees/<tree_pk>/quick-add/
/trees/<tree_pk>/candidates/
/trees/<tree_pk>/nodes/<node_pk>/move/
/trees/<tree_pk>/nodes/<node_pk>/reorder/
/trees/<tree_pk>/nodes/<node_pk>/remove/
/trees/<tree_pk>/panel/
```

路由语义重点是：

- 所有节点动作都明确属于某个 tree；
- 不恢复独立 `/nodes/` 业务模块；
- 所有 POST endpoint 做服务器端权限和上下文校验；
- 不信任 hidden input 中传回的 tree/domain/parent。

`SkillTreeVersionDetailView`：

- 使用 selector 构建树；
- full request 返回完整页面；
- panel endpoint/HTMX 返回 tree partial；
- View 保持薄，不在 View 内写移动、删除、重排算法。

---

# 14. Phase 12：权限收敛

当前权限体系不要被本次 UI 重构破坏。

## 14.1 保持角色语义

当前：

- 技术教练 bundle 对 Skill 有维护权限，但对 SkillTreeNode 主要是查看；
- 项目管理员 / 标准维护者拥有 SkillTreeNode 增改权限。

本次不要擅自把树结构维护权授予所有技术教练。

## 14.2 补齐删除节点权限

因为工作台新增“从树移除”，更新：

```text
core/config/permission_bundles.yml
```

至少给真正承担标准维护职责的 bundle 补充：

```text
standards.delete_skilltreenode
```

重点检查：

```text
training.project_admin
standards.maintain_standard
```

不要机械添加到：

```text
training.coach
```

除非现有权限设计明确要求。

## 14.3 对象范围

即使用户拥有 Django model permission，写操作仍要检查 TechnicalDomain 范围。

复用现有：

```text
can_manage_domain()
manageable_domains_for()
can_manage_skill()
is_project_admin()
```

规则：

- 新建 Skill：`add_skill + domain scope`；
- 挂载节点：`add_skilltreenode + domain scope`；
- 移动：`change_skilltreenode + source/target domain scope`；
- 删除树位置：`delete_skilltreenode + domain scope`；
- 编辑 Skill：`change_skill + can_manage_skill`。

模板隐藏按钮只是 UX；服务端必须重复校验。

---

# 15. Phase 13：导航清理

修改：

```text
core/config/navigation.yml
```

标准体系主导航收敛为：

```text
技能项目
新增技能项目（按现有策略保留）
技能目录
标准技能树版本
新增标准技能树版本
WSOS 版本
新增 WSOS 版本
```

删除主导航：

```text
技能节点
新增技能节点
```

用户应通过：

```text
标准技能树版本 → 进入具体版本 → 技能树工作台
```

维护树。

---

# 16. Phase 14：Admin 调整

修改 `standards/admin.py`：

## SkillAdmin

移除：

```text
display_code
```

保留名称、项目、主要领域、启用状态等。

## SkillTreeNode

不要继续依赖默认 `admin.site.register()` 产生难以理解的表单。

建议显式注册 `SkillTreeNodeAdmin`，至少：

```text
list_display = tree_version, technical_domain, skill, parent, order
list_filter = tree_version, technical_domain
search_fields = skill__name
```

Admin 不是树结构主要维护入口。

如果直接通过 Admin 修改 parent，模型校验仍必须防止跨版本、跨领域和环。

---

# 17. Phase 15：测试计划

本次是模型 + service + 权限 + HTMX + 模板的纵向重构，必须新增/修改测试。

## 17.1 Model tests

新增或改写：

1. root node 可以直接挂 Skill；
2. Skill 节点可以有 child Skill；
3. 支持 4 层以上任意深度；
4. 同一 Skill 在同一 tree_version 只能出现一次；
5. 同一 Skill 可以出现在不同 tree_version；
6. parent 必须同 tree_version；
7. parent 必须同 technical_domain；
8. skill 必须同 SkillProject；
9. node technical_domain 必须是 Skill primary/related domain；
10. self-parent 被拒绝；
11. ancestor cycle 被拒绝；
12. `get_full_path()` 只由 Skill 名称组成；
13. `get_descendants()` 按 order/pk 稳定返回。

删除所有依赖：

```text
CATEGORY
TOPIC
node_type
node code
Skill.display_code
```

的旧断言。

## 17.2 Service tests

覆盖：

1. 快速新增无候选时原子创建 Skill + SkillTerm + SkillTreeNode；
2. Skill 保存失败时不留下 SkillTreeNode；
3. Node 保存失败时不留下孤立 Skill；
4. 精确命中已有 Skill 不重复创建；
5. 高相似候选要求明确确认；
6. 已停用 Skill 不可新增挂载；
7. 已存在于当前版本的 Skill 不可重复挂载；
8. 新节点默认 order = siblings max + 10；
9. 上移/下移顺序正确；
10. 移动到自身/后代被拒绝；
11. 同领域移动成功；
12. 合法跨领域移动整棵子树成功；
13. 任一 descendant 不允许目标领域时跨域移动整体回滚；
14. `promote_children` 只删节点、不删 Skill；
15. `subtree` 只删树节点、不删 Skill；
16. 删除整个 subtree 后历史 Evidence / TrainingTask 等 Skill 关联仍存在。

## 17.3 Permission tests

覆盖：

- 没有 `add_skilltreenode` 不能挂载；
- 没有 `add_skill` 但有节点权限时，可以挂载已有 Skill，但不能创建新 Skill；
- 没有 `change_skilltreenode` 不能移动；
- 没有 `delete_skilltreenode` 不能移除；
- 有 Django permission 但无 TechnicalDomain scope 仍被拒绝；
- project admin 可维护全部领域；
- `training.coach` 不因本次变更自动获得树编辑权限。

## 17.4 View/HTMX tests

覆盖：

1. tree detail 按 TechnicalDomain 分组；
2. arbitrary depth 正确渲染；
3. 页面不出现“分类/主题/节点代码”；
4. 页面不出现 Skill `SK-xxxxxx`；
5. HTMX quick add 成功返回 tree panel；
6. 响应包含 `skillTreeNodeCreated` trigger；
7. exact candidate 可以挂载已有 Skill；
8. duplicate current-tree Skill 返回可定位错误；
9. remove/move/reorder HTMX 响应正确；
10. 无权限按钮不展示，直接 POST 仍被拒绝。

## 17.5 查询数测试

为树详情增加至少一个代表性查询数保护：

- 构造多个领域、多层节点；
- 确保节点数量增加不会出现每个 node 一次查询的 N+1；
- 不需要追求极端固定数字，但要能证明 selector 不是递归 ORM 查询。

---

# 18. Phase 16：前端实现约束

当前仓库：

```text
Django >= 6.0
Python >= 3.13
django-htmx >= 1.23.2
django-tables2 >= 2.7.5
Tailwind CSS ^4.1.12
DaisyUI ^5.0.50
@alpinejs/csp ^3.15.12
@iconify/tailwind4 ^1.0.6
```

执行时遵循：

## HTMX

- 使用 `request.htmx`；
- 权限与业务规则全部在服务端；
- 树操作返回 fragment；
- 可用 `HX-Trigger-After-Swap` 做新增后定位；
- 只有确有必要时使用 `hx-swap-oob`。

## Tailwind CSS 4

- 所有 class 使用完整静态字符串；
- 不按 `depth` 拼接 class；
- 递归缩进靠每层固定嵌套 markup；
- 修改模板/Iconify class 后执行 `npm run build:css`。

## DaisyUI 5

- 可使用 `<details>` + collapse 模式完成树枝折叠；
- 不需要额外 accordion/tree library。

## Alpine CSP

本页面优先复用现有 `static/js/app.js` 的原生 JS + data attribute 模式。

如果确实使用 Alpine：

- 只使用 CSP build 支持的简单表达式；
- 复杂逻辑提取到 JS/`Alpine.data()`；
- 不引入依赖 unsafe-eval 的写法。

## Iconify

使用静态完整类名：

```html
<span class="icon-[tabler--target] size-4"></span>
```

不要运行时拼接 icon class。

---

# 19. Phase 17：文档与领域语义同步

## 19.1 更新 CONTEXT.md

将当前：

```text
技能编号由数据库主键统一显示为 SK-000123
节点分为分类、主题和技能节点
```

替换为新的稳定定义：

### Skill

建议语义：

```text
Skill 是跨技能树版本长期存在的稳定能力单元，可具有不同粒度。
Skill 可以在某一技能树版本中作为父技能或叶子技能；是否有子技能不改变其 Skill 身份。
Skill 不设置用户可见业务编号，正式名称和别名由 SkillTerm 在项目范围内统一维护。
```

### SkillTreeVersion / SkillTreeNode

建议语义：

```text
SkillTreeVersion 表达某一时期 Skill 的组织结构。
SkillTreeNode 只表示稳定 Skill 在该版本、该技术领域中的位置、父子关系和顺序。
技能树不限固定层级，所有实际节点都关联 Skill；不存在分类/主题/分组节点类型。
树父子关系表达组织与细化，不自动产生评分、掌握度或属性继承关系。
```

业务不变量新增：

```text
- 一个 Skill 在同一 SkillTreeVersion 中只出现一次；
- 删除 SkillTreeNode 不等于删除 Skill；
- Skill 名称属于长期 Skill，不做节点级名称快照。
```

## 19.2 新增 ADR 0005

新增：

```text
docs/adr/0005-skill-tree-as-versioned-skill-hierarchy.md
```

记录：

- Context：固定 CATEGORY/TOPIC/SKILL 增加认知负担并限制任意层级；
- Decision：所有节点都是 Skill，SkillTreeNode 仅保存版本化位置关系；
- Decision：取消 Skill/node 用户编号；
- Decision：Skill 可拥有子 Skill；
- Decision：树关系不自动决定考核/统计汇总；
- Decision：同一 Skill 在同一版本只挂一次；
- Consequences：技能目录包含各种粒度 Skill；父 Skill 仍可被 Evidence/TrainingTask 直接引用；树结构变化不改变长期 Skill；
- Non-goals：不做 SkillTreeVersion 冻结、不做拖拽、不做聚合算法。

## 19.3 用户手册

更新：

```text
docs/user-manual/standards/overview.md
```

说明用户流程：

```text
技能目录：查看和维护长期 Skill
技能树：组织 Skill 的层次结构，并可在树上直接新增 Skill
```

删除旧“分类/主题/技能节点”“节点代码”等说明。

不要把旧 `docs/agents/plan/TMS-训练主线重构实施Plan.md` 大规模重写；它是上一阶段实施记录。新的 ADR + CONTEXT + 本 Plan 负责表达本轮决策。

---

# 20. Phase 18：代码清理与全局回归检索

完成修改后执行：

```bash
rg -n \
  "display_code|SkillTreeNode\.NodeType|NodeType\.|node_type|uniq_skilltreenode_version_code|get_node_type_display|node\.code|SkillTreeNodeForm|SkillTreeNodeTable|standards:node_list|standards:node_create|standards:node_detail|standards:node_edit|SK-待生成" \
  standards core docs \
  --glob '!**/__pycache__/**'
```

预期：

- 不再有本次已删除领域概念的有效业务引用；
- migration 历史中若保留旧字段名属于正常历史，不要为了让 `rg` 绝对为零而破坏 migration；
- ADR/历史计划中提及旧方案也允许保留上下文，但当前稳定文档不得继续宣称旧语义。

同时执行：

```bash
rg -n "技能分类|能力主题|新增技能节点|技能节点列表|节点代码" \
  standards/templates core/config docs/user-manual CONTEXT.md
```

确保用户可见层已收敛。

---

# 21. 验证顺序

按风险分层验证，不要一上来每改一行都跑全量测试。

## 21.1 模型与 service 完成后

```bash
uv run pytest standards
uv run ruff check standards
uv run manage.py makemigrations --check --dry-run
```

## 21.2 跨 APP 回归

因为 Evidence / TrainingTask / Scoring 等都指向长期 Skill，本次虽不改变这些 FK，但会改变 `Skill.__str__` 和树模型，运行：

```bash
uv run pytest assessments evidence scoring training
```

## 21.3 URL / 权限 / 项目检查

```bash
uv run manage.py check
```

## 21.4 前端模板与 JS 完成后

```bash
npm run build:css
```

确认 `static/css/output.css` 正常生成，不存在因为动态 Tailwind/Iconify class 导致样式缺失。

## 21.5 最终合并级验证

本次属于标准核心模型重构，最终执行一次全量：

```bash
uv run pytest
uv run ruff check .
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
npm run build:css
```

如果 CI 还有仓库既有独立步骤，按当前 `.github/workflows/` 执行，不为了无关历史失败扩大修改范围。

---

# 22. 关键验收场景

Codex 完成后至少人工/测试验证以下用户场景。

## 场景 A：从空树开始

```text
Linux
└─ + 新增根技能
```

输入：

```text
系统管理
```

结果：

```text
Linux
└─ 系统管理
```

数据库一次事务创建：

```text
Skill("系统管理")
SkillTerm(NAME, "系统管理")
SkillTreeNode(skill=系统管理, parent=NULL)
```

## 场景 B：任意层级继续细化

依次创建：

```text
系统管理
└─ 用户与权限管理
   └─ sudo 权限管理
      └─ sudoers 规则
         └─ NOPASSWD
```

必须成功，不存在“最多三层”限制。

## 场景 C：原父 Skill 仍是可考核 Skill

```text
DNS (is_assessable=True)
├─ 权威 DNS
└─ DNSSEC
```

必须允许；不能因为 DNS 有 children 自动改 `is_assessable=False`。

## 场景 D：复用已有 Skill

技能目录已有：

```text
sudo 权限管理
```

在树上输入同名/精确别名：

- 不创建重复 Skill；
- 直接挂载已有 Skill；
- 若本版本已存在，则定位到已有节点。

## 场景 E：重新归类

```text
用户与权限管理
└─ sudo 权限管理
```

移动为：

```text
系统安全
└─ sudo 权限管理
```

只更新 `SkillTreeNode.parent/order`；Skill 本体不变。

## 场景 F：父 Skill 下面继续拆子 Skill

```text
用户与权限管理
```

后来拆成：

```text
用户与权限管理
├─ 用户和用户组管理
├─ sudo 权限管理
├─ PAM
└─ ACL
```

原“用户与权限管理”Skill id、Evidence、TrainingTask、历史数据全部保持不变。

## 场景 G：移除父节点但保留孩子

```text
系统管理
└─ 用户与权限管理
   ├─ sudo
   └─ PAM
```

选择“仅移除当前技能并提升子技能”后：

```text
系统管理
├─ sudo
└─ PAM
```

仅删除“用户与权限管理”对应的 `SkillTreeNode`；其 Skill 本体仍存在技能目录中。

## 场景 H：移除整个分支

选择删除一个包含 10 个 descendant 的 subtree：

- UI 明确提示数量；
- 二次确认；
- 只删除 11 个 `SkillTreeNode`；
- 11 个 Skill 本体仍存在；
- Evidence/TrainingTask/评分关联不受影响。

## 场景 I：跨域移动被正确阻止

Linux 子树包含一个只属于 Linux 的 Skill；尝试移动到 Windows：

- 服务端拒绝；
- 提示哪个 Skill 未关联 Windows；
- 不自动修改 `related_domains`；
- 整个操作回滚。

---

# 23. 明确不做的内容

为了防止 Codex 过度实现，本次禁止自行扩展：

1. 不实现拖拽树；
2. 不引入 MPTT/treebeard；
3. 不实现无限滚动/懒加载树；
4. 不给 Skill 重新设计业务编号；
5. 不给 SkillTreeNode 重新设计自动分级编号；
6. 不恢复 Group/Category/Topic 类型；
7. 不给 Skill 增加 `is_group`；
8. 不根据 children 自动修改 `is_assessable`；
9. 不自动汇总父 Skill 分值/掌握度；
10. 不自动修改 Skill 的 primary/related domain 来满足拖动；
11. 不修改 Evidence / TrainingTask 绑定逻辑，除非因编译/测试直接受本次改动影响；
12. 不新增 Skill 硬删除 UI；
13. 不在本次新增 SkillTreeVersion 锁定/发布状态；
14. 不在本次实现“从当前版本一键克隆新技能树版本”；
15. 不升级前端/后端依赖；
16. 不无关重构其他 APP。

---

# 24. 后续独立议题（本次不实施）

完成本 Plan 后，可另行讨论：

## 24.1 SkillTreeVersion 生命周期与冻结

当前 `TrainingCycle.skill_tree_version` 使用 `PROTECT` 固定引用技能树版本，但 `SkillTreeVersion` 本身只有 `is_current`，没有 frozen/published 状态。

后续需明确：

- 版本何时允许继续修改；
- 被 ACTIVE/COMPLETED TrainingCycle 使用后是否冻结；
- 新版本是否从当前版本克隆；
- 结构调整是否必须创建新版本。

这是版本治理问题，不与本次“树节点模型简化”混在一起。

## 24.2 大规模树的高级交互

当实际树规模证明有必要时，再评估：

- 拖拽排序；
- 键盘 Tab/Enter 思维导图快捷键；
- 仅刷新局部 branch；
- 搜索并展开命中节点；
- 折叠状态持久化；
- 大树虚拟化。

当前不要预实现。

---

# 25. 官方实现参考

执行时参考当前官方文档，且以仓库现有依赖版本可用能力为准：

- Django 6 模型与递归自关联：  
  https://docs.djangoproject.com/en/6.0/topics/db/models/  
  https://docs.djangoproject.com/zh-hans/6.0/ref/models/fields/
- django-htmx middleware / `request.htmx`：  
  https://django-htmx.readthedocs.io/
- htmx `hx-swap-oob`：  
  https://htmx.org/attributes/hx-swap-oob/
- Tailwind CSS 4 source scanning：  
  https://tailwindcss.com/docs/detecting-classes-in-source-files
- DaisyUI 5 Collapse：  
  https://daisyui.com/components/collapse/
- Alpine CSP build：  
  https://alpinejs.dev/advanced/csp
- Iconify Tailwind CSS 4：  
  https://iconify.design/docs/usage/css/tailwind/tailwind4/
- django-tables2：  
  https://django-tables2.readthedocs.io/

不要因为文档网站显示的最新版高于仓库 package 版本，就在本任务中升级依赖。

---

# 26. 完成定义（Definition of Done）

只有同时满足以下条件才算完成：

- [ ] `Skill.display_code` 已删除，用户界面不再显示 `SK-xxxxxx`。
- [ ] `Skill.__str__()` 直接使用名称。
- [ ] `SkillTreeNode` 已删除 `node_type/code/name/description/is_active`。
- [ ] 每个 `SkillTreeNode` 必须关联一个稳定 Skill。
- [ ] Skill 可作为根节点、父节点或叶子节点。
- [ ] 技能树支持任意深度。
- [ ] 同一个 Skill 在同一技能树版本只出现一次。
- [ ] tree detail 已从平面表格改为真正树形结构。
- [ ] TechnicalDomain 只作为树的视觉/权限分区，不是伪节点。
- [ ] 用户可以在技能树页面直接新增根 Skill / 子 Skill。
- [ ] 快速新增会复用 SkillTerm 候选检测，不制造明显重复 Skill。
- [ ] 新增 Skill + SkillTreeNode 是原子事务。
- [ ] 支持移动、同级顺序调整、从树移除。
- [ ] 删除树位置不会删除长期 Skill。
- [ ] 有 children 的移除操作区分“提升 children”与“删除 subtree”。
- [ ] 跨域移动不会静默修改 Skill 领域属性。
- [ ] 独立 `/nodes/` CRUD 与主导航已清理。
- [ ] SkillTreeNode 写操作进入 service，不散落在 View。
- [ ] 树读取没有递归 N+1。
- [ ] 权限包补齐标准维护者的 `delete_skilltreenode`，不擅自扩大技术教练权限。
- [ ] CONTEXT.md 已同步新的 Skill / SkillTreeNode 定义。
- [ ] 新增 ADR 0005 记录本次长期架构决策。
- [ ] 用户手册标准体系说明已同步。
- [ ] `uv run pytest standards` 通过。
- [ ] `uv run pytest assessments evidence scoring training` 通过。
- [ ] 最终 `uv run pytest` 通过。
- [ ] `uv run ruff check .` 通过。
- [ ] `uv run manage.py check` 通过。
- [ ] `uv run manage.py makemigrations --check --dry-run` 无漂移。
- [ ] 全新数据库迁移链可成功执行。
- [ ] `npm run build:css` 通过。
- [ ] 最终全局 `rg` 不再存在有效旧节点类型、节点代码和 Skill display code 业务引用。

---

# 27. 推荐提交边界

保持一个功能分支、多个可验证提交。建议：

```text
refactor(standards): simplify skills and skill tree nodes
feat(standards): add skill tree services and hierarchical selector
feat(standards): build inline skill tree workbench
refactor(standards): remove standalone node CRUD and navigation
refactor(permissions): align skill tree maintenance permissions
docs(standards): document versioned skill hierarchy
test(standards): cover arbitrary-depth skill tree workflows
```

允许根据实际修改合并相邻提交，但不要把所有模型、UI、权限、文档、测试塞进一个无法审阅的超大提交。

提交、push、PR 仍按仓库现有授权流程执行；本 Plan 本身不代表用户已经授权 Codex 自动 push 或创建 PR。
