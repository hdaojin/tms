# TMS 标准体系第二阶段优化 Codex 实施计划

> 目标分支：`feature/training-domain-refactor`
>
> 目标仓库：`hdaojin/tms`
>
> 适用技术栈：Django 6、Python 3.13、django-htmx、django-tables2、Tailwind CSS 4、DaisyUI 5、Alpine.js、Iconify
>
> 执行前必须阅读：`AGENTS.md`、`CONTEXT.md`，并以当前分支实际代码、迁移和测试为准。

---

## 1. 本轮已确认的业务决策

本轮只实现以下已经确认的设计，不再重新讨论方向。

### 1.1 技能树采用“树形视图 + 列表视图”

不恢复独立的“技能目录 / 技能列表”日常维护入口。

技能树仍是标准技能维护的主入口，同一个技术领域、同一个技能树版本提供两种视图：

- **树形视图**
  - 展示父子层级；
  - 新增根技能、子技能、同级技能；
  - 编辑 Skill；
  - 调整同级顺序；
  - 在同一技术领域树内移动节点；
  - 搜索并快速定位技能；
  - 不提供会破坏树语义的任意排序。

- **列表视图**
  - 展示与树形视图相同的当前树节点；
  - 支持搜索、筛选、排序；
  - 展示完整技能路径；
  - 主要用于查找、分析和快速进入技能详情/编辑；
  - 不成为另一套技能维护数据源。

“未纳入当前树”的长期 Skill 继续使用现有机制单独查看和重新挂载，不把未挂载 Skill 混入普通树节点列表。

### 1.2 技能树版本下沉到 TechnicalDomain

`SkillTreeVersion` 不再属于整个 `SkillProject`，而属于一个明确的 `TechnicalDomain`。

最终语义：

```text
SkillProject
└── TechnicalDomain
    ├── SkillTreeVersion V1
    ├── SkillTreeVersion V2
    └── SkillTreeVersion V3 [current]
```

Linux、Windows、Network 可以分别拥有独立的当前版本和历史版本。

一个领域调整技能树，不再要求其他领域同步创建新版本。

### 1.3 WSOS 本轮只做到 Section

本轮保持以下层级：

```text
WSOSVersion
└── WSOSSection
    └── SkillWSOSMap -> Skill
```

明确不增加 `WSOSItem`、子条目或更细粒度层级。

世赛分析粒度暂时只到 `WSOSSection`。

`Skill` 与 `WSOSSection` 保持多对多关系：

- 一个 Skill 可以映射多个 WSOSSection；
- 一个 WSOSSection 可以映射多个 Skill；
- WSOS 不直接关联 TechnicalDomain；
- TechnicalDomain 仍是训练组织与权限轴，WSOS 是标准映射轴。

---

# 2. 推荐的最终领域模型

## 2.1 SkillTreeVersion

将当前：

```text
SkillTreeVersion
- skill_project
- version
- name
- description
- is_current
```

调整为：

```text
SkillTreeVersion
- technical_domain -> TechnicalDomain
- based_on -> SkillTreeVersion（可空，记录版本来源）
- version
- name
- description
- is_current
- created_by
- created_at
- updated_at
```

建议：

- `technical_domain` 使用 `PROTECT`；
- 删除持久化字段 `skill_project`；
- 提供只读属性：

```python
@property
def skill_project(self):
    return self.technical_domain.skill_project
```

数据库约束调整为：

```text
UniqueConstraint(technical_domain, version)

UniqueConstraint(
    technical_domain,
    condition=is_current=True
)
```

含义：

- 同一技术领域内版本号唯一；
- 每个技术领域最多一个当前技能树；
- 不同技术领域可以同时存在 `V1`、`2026.1` 等相同版本号。

---

## 2.2 SkillTreeNode

将当前：

```text
SkillTreeNode
- tree_version
- technical_domain
- parent
- skill
- order
```

调整为：

```text
SkillTreeNode
- tree_version
- parent
- skill
- order
```

删除持久化字段 `technical_domain`。

节点所属技术领域唯一由：

```text
node.tree_version.technical_domain
```

确定。

如现有模板和业务代码频繁需要，可保留只读便利属性：

```python
@property
def technical_domain(self):
    return self.tree_version.technical_domain
```

以及必要时只读 `technical_domain_id`，但禁止再允许节点独立修改技术领域。

继续保留：

```text
UniqueConstraint(tree_version, skill)
```

同一 Skill：

- 在同一个领域的同一个树版本中只能出现一次；
- 如果 Skill 的 `primary_domain / related_domains` 允许，可以分别出现在不同技术领域各自的技能树中；
- 不再通过“一个项目级树版本”人为阻止跨领域展示共享 Skill。

节点校验只需要保证：

1. Skill 与树所属 SkillProject 一致；
2. 树所属 TechnicalDomain 必须属于 Skill 的 `primary_domain` 或 `related_domains`；
3. parent 必须属于同一个 `tree_version`；
4. 不能形成循环；
5. 不再进行“节点 technical_domain 与 parent technical_domain 是否一致”的冗余校验。

---

## 2.3 TrainingCycle 与技能树版本

这是本次模型调整必须同步处理的跨 APP 影响。

当前：

```text
TrainingCycle
- skill_project
- skill_tree_version   # 单个项目级版本
```

不能继续保留，因为改造后一个训练周期可能同时使用：

```text
Linux   -> Tree V3
Windows -> Tree V2
Network -> Tree V4
```

推荐改为：

```text
TrainingCycle
└── TrainingCycleSkillTreeVersion
    ├── technical_domain
    └── skill_tree_version
```

建议增加：

```python
class TrainingCycleSkillTreeVersion(models.Model):
    training_cycle = ForeignKey(...)
    technical_domain = ForeignKey(
        "standards.TechnicalDomain",
        on_delete=PROTECT,
    )
    skill_tree_version = ForeignKey(
        "standards.SkillTreeVersion",
        on_delete=PROTECT,
    )
```

并让 `TrainingCycle` 提供：

```python
skill_tree_versions = ManyToManyField(
    "standards.SkillTreeVersion",
    through="TrainingCycleSkillTreeVersion",
    related_name="training_cycles",
)
```

`technical_domain` 在 through 模型中虽然可以从 `skill_tree_version` 推导，但建议显式保留，因为它允许数据库直接实现：

```text
UniqueConstraint(training_cycle, technical_domain)
UniqueConstraint(training_cycle, skill_tree_version)
```

从而保证一个训练周期对同一技术领域最多固定一个版本。

模型 / service 校验必须保证：

```text
link.technical_domain.skill_project
    == training_cycle.skill_project

link.skill_tree_version.technical_domain
    == link.technical_domain
```

不要增加“必须是当前版本”的限制。

训练周期建立后必须允许固定历史版本，因为其职责就是保存训练期间使用的标准快照。

### TrainingCycleForm

将原来的单个 `skill_tree_version` 改为“各技术领域技能树版本”选择能力。

推荐 UI：

- 先确定 SkillProject；
- 按技术领域显示版本选择；
- 每个领域最多选择一个版本；
- 新建周期时，默认带出各启用技术领域的当前技能树版本；
- 没有当前版本的领域显示“尚无当前技能树”，不伪造版本；
- 编辑历史周期时必须继续显示已绑定的历史/停用领域版本。

### TrainingTask

训练任务可选择的 TechnicalDomain 必须受 TrainingCycle 已固定版本约束：

```text
TrainingTask.domain_links
    ⊆ TrainingCycle 已绑定技能树版本的技术领域
```

即：

- 周期没有固定某领域的树版本，就不能在该周期内发布该领域的训练任务；
- 不要再简单列出项目下所有启用 TechnicalDomain。

这样才能继续保证“训练周期固定训练期间标准版本”的业务语义。

---

# 3. 技能树 service / selector 重构

## 3.1 current tree selector

将当前项目级：

```python
current_skill_tree_for(project)
```

调整为领域级：

```python
current_skill_tree_for(domain)
```

查询：

```text
SkillTreeVersion(
    technical_domain=domain,
    is_current=True
)
```

全仓搜索并更新所有调用点。

---

## 3.2 tree structure selector

`skill_tree_structure()` 不再需要额外传入 `domain` 来过滤，因为一个 `SkillTreeVersion` 天然只属于一个领域。

建议收敛为：

```python
skill_tree_structure(
    *,
    tree_version,
    user,
)
```

内部：

- 一次读取当前 tree_version 全部节点；
- `select_related("skill", "skill__primary_domain", "parent", ...)`；
- 构造 `children_by_parent`；
- 计算 `full_path`；
- 计算 descendant_count；
- 装饰权限；
- 禁止递归过程中发数据库查询。

如果现有模板需要 domain 容器，可以返回由：

```python
tree_version.technical_domain
```

装饰后的单个 domain 对象，不再返回“一个版本中的多个领域”。

---

## 3.3 unmounted skills

将：

```python
unmounted_primary_skills_for_tree_domain(
    tree_version,
    domain,
    user,
)
```

收敛为：

```python
unmounted_primary_skills_for_tree(
    tree_version,
    user,
)
```

domain 直接从：

```python
tree_version.technical_domain
```

取得。

仍只列：

- SkillProject 一致；
- `primary_domain` 为当前树所属领域；
- 启用；
- 尚未挂入当前 `tree_version`；
- 当前用户可见。

---

## 3.4 tree write services

所有写 service 都应减少“tree_version + technical_domain”这种可产生矛盾状态的双参数。

例如推荐从：

```python
attach_existing_skill_to_tree(
    tree_version=tree,
    technical_domain=domain,
    ...
)
```

收敛为：

```python
attach_existing_skill_to_tree(
    tree_version=tree,
    ...
)
```

service 内统一：

```python
domain = tree_version.technical_domain
```

同样调整：

- `create_skill_in_tree`
- `create_detailed_skill_in_tree`
- parent 校验；
- sibling order；
- permission scope；
- Skill/domain compatibility 校验。

目的：让不合法状态在函数签名层面就无法表达。

---

## 3.5 节点移动

技能树版本下沉到 TechnicalDomain 后，单个 `tree_version` 内不再存在跨领域节点。

因此 `move_skill_tree_node()` 应改为：

- 只允许在当前 tree_version 内改变 parent；
- 只允许根节点 / 同树节点之间移动；
- 删除 `target_domain` 参数；
- `SkillTreeMoveForm` 删除目标技术领域字段；
- sibling order 只需要按 `tree_version + parent` 计算。

**不再提供“直接把一个分支从 Linux 树拖到 Windows 树”的跨领域移动。**

如果确实需要改变某 Skill 在标准树中的领域位置，采用显式动作：

1. 从原领域树移除树位置；
2. 确保 Skill 的 primary/related domain 已允许目标领域；
3. 从目标领域的“未纳入当前树”中重新挂载。

这样避免一次操作跨两个独立版本修改历史结构。

---

## 3.6 Skill related domain 校验

更新 `set_skill_related_domains()`。

当前基于：

```text
SkillTreeNode.technical_domain
```

判断已有树位置。

改为基于：

```text
tree_nodes__tree_version__technical_domain
```

判断。

只要某个既有树位置所属领域将不再是 Skill 的 primary/related domain，就继续阻止该修改，并提示先移动/移除对应树位置。

---

# 4. 技能树双视图

## 4.1 页面结构

每个领域技能树页顶部增加视图切换：

```text
[树形视图] [列表视图]
```

两种视图属于同一个“领域 + 技能树版本”上下文。

不要恢复：

```text
/projects/<project>/skills/
```

作为正式技能列表入口。

现有 legacy URL 可以继续重定向，或在确认无引用后移除；不得重新赋予其技能维护功能。

---

## 4.2 推荐 URL / View 结构

保持 current tree 和 historical tree 的概念，但利用“tree 已经知道 domain”简化版本级 URL。

推荐：

```text
/projects/<project_pk>/domains/<domain_pk>/tree/
    -> 当前树树形视图

/projects/<project_pk>/domains/<domain_pk>/tree/list/
    -> 当前树列表视图

/trees/<tree_pk>/
    -> 指定历史/当前版本树形视图

/trees/<tree_pk>/list/
    -> 指定版本列表视图
```

版本级 URL 不再重复携带 `domain_pk`。

同步简化：

- panel；
- unmounted skills；
- root quick add；
- candidate search；
- create child/sibling；
- edit；
- move；
- reorder；
- remove。

如果为了兼容暂时保留旧 URL，可仅做 redirect，不应让两个 URL 维护两套逻辑。

---

# 5. 树形视图搜索

树形视图只增加“搜索与快速定位”，不要加入任意排序。

建议在树工作台头部增加搜索框：

```text
搜索技能名称、别名或描述
```

行为：

1. HTMX 延迟搜索；
2. 搜索范围仅限当前 `tree_version` 中已经挂载的 Skill；
3. 匹配：
   - Skill.name；
   - SkillTerm alias；
   - Skill.description；
4. 返回少量候选：
   - 技能名称；
   - 完整路径；
5. 点击结果：
   - 打开必要的祖先 `<details>`；
   - scrollIntoView 当前节点；
   - 短暂高亮节点。

现有树节点已经有：

```text
id="skill-tree-node-<pk>"
```

应复用，不再建立第二套 DOM 标识。

Alpine.js 只负责：

- 展开祖先；
- 定位；
- 高亮状态。

搜索、权限和结果范围由 Django 服务端负责。

---

# 6. 技能列表视图

## 6.1 数据源

列表数据源必须是：

```text
SkillTreeNode
WHERE tree_version = 当前页面 tree
```

不是整个 `Skill` 库。

这样树形与列表视图永远展示同一批树节点。

---

## 6.2 SkillTreeNodeTable

在 `standards/tables.py` 增加专用表格，例如：

```python
SkillTreeNodeTable
```

建议列：

| 列 | 是否排序 |
|---|---|
| 技能名称 | 是 |
| 完整路径 | 否 |
| 难度 | 是 |
| 核心技能 | 是 |
| 可考核 | 是 |
| 启用状态 | 是 |
| 当前 WSOS 映射 | 否 |
| 更新时间 | 是 |
| 操作 | 否 |

技能名称链接到 SkillDetail。

编辑操作必须继续遵守领域权限。

完整路径由 selector 一次性计算，禁止逐行调用递归 QuerySet 造成 N+1。

---

## 6.3 搜索

复用现有：

```text
core.utils.listing.FilterableListMixin
ListFilterSpec
```

不要再新写一套通用筛选组件。

搜索：

```text
q
```

至少覆盖：

- `skill__name`
- `skill__description`
- `skill__terms__term`

涉及 SkillTerm 时正确使用 `distinct()`。

---

## 6.4 筛选

第一版建议支持：

- 难度：1–5；
- 核心技能：全部 / 是 / 否；
- 可考核：全部 / 是 / 否；
- 启用状态：全部 / 启用 / 停用；
- 当前 WSOS 映射：全部 / 已映射 / 未映射。

“当前 WSOS 映射”以该 SkillProject 的：

```python
current_wsos_for(project)
```

为准。

不要把历史所有 WSOS 版本混成一个“已映射”判断。

如当前 SkillProject 尚无 current WSOS：

- 不显示该筛选项，或显示不可用提示；
- 不报错。

---

## 6.5 排序

使用 django-tables2 原生排序。

至少支持：

- 技能名称；
- 难度；
- 核心；
- 可考核；
- 启用状态；
- 更新时间。

不要对树形视图应用这些排序结果。

树中 `order` 始终只表示结构中的兄弟顺序。

---

# 7. 技能树版本页面

## 7.1 SkillTreeVersionListView

全局“技能树版本”列表仍可保留用于历史查询。

表格调整为：

```text
技能项目
技术领域
版本
名称
当前版本
更新时间
操作
```

其中“技能项目”从：

```python
tree.technical_domain.skill_project
```

取得。

建议增加：

- SkillProject 筛选；
- TechnicalDomain 筛选；
- 当前版本筛选。

---

## 7.2 创建版本

日常创建版本的首选入口改为“技术领域上下文”。

例如：

```text
/projects/<project>/domains/<domain>/trees/create/
```

domain 由 URL 确定，避免用户在表单中选择错误领域。

当某技术领域没有当前技能树时，当前树页面直接显示：

```text
新增技能树版本
```

并创建该领域版本。

全局版本列表如果继续保留“新增版本”，必须明确选择 TechnicalDomain，不能再只选择 SkillProject。

---

## 7.3 ProjectDetail

当前 `SkillProjectDetailView` 不再只有一个：

```text
current_tree
```

应改为每个 TechnicalDomain 分别显示：

```text
Linux
当前技能树：V3

Windows
当前技能树：V2

Network
当前技能树：V4
```

领域卡片直接进入本领域当前技能树。

项目级仍只保留一个：

```text
current_wsos
```

---


---

# 7A. 技能树版本迭代与克隆

这是本轮正式需求，不作为可选增强。

## 7A.1 业务目标

创建新的技能树版本时，必须支持：

1. **基于当前版本创建新版本**；
2. **基于指定历史版本创建新版本**；
3. **创建空白版本**。

默认推荐：

```text
基于当前版本创建新版本
```

因为日常标准维护主要是版本迭代，而不是每次从空树重新建立。

---

## 7A.2 SkillTreeVersion 增加 based_on

在 `SkillTreeVersion` 增加：

```python
based_on = models.ForeignKey(
    "self",
    verbose_name="基于版本",
    on_delete=models.SET_NULL,
    related_name="derived_versions",
    null=True,
    blank=True,
)
```

业务约束：

- `based_on` 必须属于同一个 `TechnicalDomain`；
- 不能指向自身；
- 不允许形成版本来源循环；
- `based_on` 仅用于记录版本来源，不形成运行时继承；
- 新版本创建完成后与来源版本完全独立；
- 后续修改来源版本不会同步到派生版本。

示例：

```text
Linux
├── V1
├── V2  based_on=V1
└── V3  based_on=V2
```

---

## 7A.3 克隆内容

从旧版本创建新版本时，只复制“版本内组织结构”。

复制：

- `SkillTreeNode`
- parent 父子关系
- order 顺序
- Skill 引用

不复制：

- Skill 本体
- SkillTerm
- Evidence
- TrainingTask
- ScoringResult
- WSOS mapping
- 任何业务历史数据

示例：

```text
V1                              V2

Node A -> Skill #10       ->    Node A' -> Skill #10
  ├─ Node B -> Skill #11         ├─ Node B' -> Skill #11
  └─ Node C -> Skill #12         └─ Node C' -> Skill #12
```

因此：

- V2 调整父子结构不影响 V1；
- V2 删除节点不影响 V1；
- V2 增加节点不影响 V1；
- V1 与 V2 仍共同引用稳定的 Skill。

---

## 7A.4 新版本默认不是 current

通过克隆创建的新版本默认：

```python
is_current = False
```

不要在创建瞬间自动替换当前版本。

推荐流程：

```text
V2 [当前]
    ↓
基于 V2 创建 V3
    ↓
V3 [非当前，编辑中]
    ↓
完成调整与检查
    ↓
“设为当前版本”
    ↓
V2.is_current = False
V3.is_current = True
```

“创建版本”和“设为当前版本”必须保持为两个独立动作。

如表单保留“创建后设为当前版本”选项，也必须默认不勾选，并继续通过事务保证同一 TechnicalDomain 最多一个 current。

---

## 7A.5 创建版本 UI

技术领域上下文中的“新增技能树版本”表单建议：

```text
版本：        V3
版本名称：    2026-08 调整版

创建方式：
  ● 基于当前版本创建
  ○ 基于已有版本创建
  ○ 创建空白版本

基于版本：
  Linux / V2 / 当前版本

□ 创建完成后设为当前版本
```

规则：

- 如果当前领域已有 current tree，默认选择“基于当前版本创建”；
- 如果没有 current tree，但存在历史版本，可默认选择最近一个历史版本，或要求用户明确选择；
- 如果领域还没有任何版本，自动退化为“创建空白版本”；
- `based_on` 的可选 queryset 必须限定为当前 TechnicalDomain；
- 历史/停用领域版本在编辑既有对象时仍必须能够正确展示。

---

## 7A.6 克隆 Service

新增明确的业务 service，例如：

```python
clone_skill_tree_version(
    *,
    source_version,
    version,
    name,
    description,
    actor,
    make_current=False,
)
```

或使用语义等价命名。

必须使用：

```python
transaction.atomic()
```

职责：

1. 锁定来源版本；
2. 校验 actor 对来源 TechnicalDomain 的管理权限；
3. 校验新版本号在 TechnicalDomain 内唯一；
4. 创建新的 `SkillTreeVersion`；
5. 设置 `based_on=source_version`；
6. 默认 `is_current=False`；
7. 一次性读取来源版本全部节点；
8. 复制节点并建立 `old_node_id -> new_node` 映射；
9. 第二阶段恢复 parent 关系；
10. 保留 order；
11. 不复制 Skill；
12. 如 `make_current=True`，事务内切换 current。

不要在 View 中直接实现节点复制逻辑。

---

## 7A.7 克隆实现要求

由于 parent 必须指向新版本中的新节点，禁止简单复制数据库行。

推荐两阶段策略：

### 第一阶段

复制所有节点：

```text
old node id -> new node
```

初始 parent 为空。

### 第二阶段

根据旧节点 parent：

```text
new_node.parent = old_to_new[old_node.parent_id]
```

批量更新 parent。

应避免：

- 每个节点单独查询；
- 递归数据库读取；
- N+1；
- 复制旧 PK；
- 临时破坏 UniqueConstraint。

如果 Django `bulk_create()` 返回 PK 的行为在当前数据库环境可稳定使用，可合理利用；否则采用安全、可测试的实现。

---

## 7A.8 历史版本语义

技能树版本保存的是：

```text
Skill 在某个时期如何组织
```

不是：

```text
Skill 当时全部字段的快照
```

因此继续保持：

```text
Skill              长期稳定本体
SkillTreeVersion   结构版本
SkillTreeNode      某个版本中的位置
```

修改 Skill 名称、描述等长期属性后，所有引用该 Skill 的历史技能树版本都会看到新的 Skill 信息。

本轮不要增加：

- SkillVersion；
- 节点级 Skill 名称快照；
- Skill description snapshot。

---

## 7A.9 与 TrainingCycle 的关系

TrainingCycle 固定的是具体的领域技能树版本。

例如：

```text
2026-07 训练周期
Linux -> V2

2026-08
Linux -> V3 [current]
```

V3 发布后：

```text
2026-07 TrainingCycle
```

仍然固定 V2，不自动迁移到 V3。

新建 TrainingCycle 时：

- 默认选择各 TechnicalDomain 当前版本；
- 历史周期继续保留原来的版本绑定。

这也是为什么“创建新版本”不能自动修改已有 TrainingCycle。

---

## 7A.10 版本克隆测试

至少增加：

1. 可以基于当前版本创建新版本；
2. 可以基于历史版本创建新版本；
3. 可以创建空白版本；
4. 新版本 `based_on` 正确；
5. `based_on` 不能跨 TechnicalDomain；
6. `based_on` 不能形成循环；
7. 克隆后节点数量一致；
8. parent 结构一致；
9. order 一致；
10. 新旧节点 PK 不同；
11. 新旧节点引用同一个 Skill；
12. 修改新版本结构不影响来源版本；
13. 删除新版本节点不影响来源版本；
14. 新版本默认 `is_current=False`；
15. 显式设为 current 时旧 current 被取消；
16. 克隆不会改变已有 TrainingCycle 的版本绑定；
17. 无领域权限用户不能克隆；
18. 同领域重复版本号被数据库/表单拒绝。

---

## 7A.11 Definition of Done 补充

在原 Definition of Done 基础上增加：

- [ ] 新技能树版本可基于当前版本克隆；
- [ ] 可基于指定历史版本克隆；
- [ ] 可创建空白版本；
- [ ] `SkillTreeVersion.based_on` 正确记录来源；
- [ ] 克隆只复制树结构，不复制 Skill；
- [ ] 新版本默认不是 current；
- [ ] 可显式将新版本设为 current；
- [ ] 来源版本与派生版本后续结构互不影响；
- [ ] 已有 TrainingCycle 不随 current tree 切换而改变绑定。


# 8. WSOS Section 功能补全

当前代码已经存在：

- `WSOSVersion`
- `WSOSSection`
- `SkillWSOSMap`
- `WSOSSectionForm`
- `SkillWSOSMapForm`

但业务页面只完成 WSOSVersion CRUD。

本轮补齐 UI 和业务入口，不增加 WSOSItem。

---

## 8.1 WSOSVersionDetail 页面

把现有简单章节列表升级为 WSOS 工作台。

显示：

```text
WSOS 2026
描述
当前版本状态

章节权重合计：100%
```

每个 Section 显示：

- code；
- name；
- description；
- weight；
- mapped skill count；
- order；
- 编辑；
- 管理技能映射。

权重总计不等于 100% 时显示醒目提示，但第一版不强制阻止保存，以允许 WSOS 编辑过程中存在未完成状态。

---

## 8.2 Section CRUD

增加：

- `WSOSSectionCreateView`
- `WSOSSectionUpdateView`
- 删除确认能力

Section 创建入口固定在一个 WSOSVersion 下，不让用户重复选择版本。

建议 URL：

```text
/wsos/<wsos_pk>/sections/create/
/wsos/sections/<section_pk>/edit/
/wsos/sections/<section_pk>/delete/
```

删除规则：

- 无 Skill 映射时允许删除；
- 已存在 SkillWSOSMap 时禁止直接删除，并提示先解除映射；
- 不要静默级联删除大量 Skill 映射。

建议将：

```text
SkillWSOSMap.wsos_section
```

调整为 `PROTECT`，使数据库层与 UI 规则一致。

---

## 8.3 Section -> Skill 映射

在每个 Section 下直接管理 Skill 映射。

第一版推荐 HTMX 交互，而不是一次加载全项目所有技能 checkbox。

流程：

```text
Section
  -> 已关联技能列表
  -> “添加技能映射”
      -> 搜索技能
      -> 可按 TechnicalDomain 过滤
      -> 点击“关联”
  -> 已关联技能旁“解除关联”
```

搜索范围：

- 当前 WSOSVersion 所属 SkillProject；
- Skill 名称；
- alias；
- description。

TechnicalDomain 过滤用于查找，不改变 WSOS 的领域语义。

映射写入继续使用：

```text
SkillWSOSMap
```

不要创建直接 ManyToMany 自动中间表。

推荐增加 service：

```python
map_skill_to_wsos_section(...)
unmap_skill_from_wsos_section(...)
```

或语义等价的明确写操作。

需要：

- project 一致性校验；
- permission 校验；
- 幂等：重复添加同一映射返回已有映射或友好提示，不制造 500；
- 删除只删除明确的这一条映射。

---

## 8.4 SkillDetail

保留现有“WSOS 映射”区域，但改进展示为：

```text
WSOS 2026 · 4 Network and System Operations
WSOS 2026 · 6 Troubleshooting
```

避免只显示 `4 - ...` 而不知道属于哪个 WSOSVersion。

如方便，可链接回对应 WSOS 页面中的 Section anchor。

本轮不要求在 Skill 编辑表单中直接维护 WSOS 映射；主要维护入口放在 WSOS 工作台，避免两套编辑交互。

---

# 9. Migration 策略

这是高风险 schema 重构，必须使用前向 migration，不能静默丢弃现有标准和训练周期数据。

不要简单删除旧字段后重新创建数据。

## 9.1 推荐迁移顺序

建议拆成可审查的 staged migrations。

### A. standards prepare migration

1. 给 `SkillTreeVersion` 增加 nullable `technical_domain`；
2. 暂时保留 `skill_project`；
3. 移除旧的：
   - `(skill_project, version)` unique constraint；
   - project 级 current unique constraint；
4. 暂时保留 `SkillTreeNode.technical_domain`。

### B. training prepare migration

1. 创建 `TrainingCycleSkillTreeVersion`；
2. 增加 `TrainingCycle.skill_tree_versions` through M2M；
3. 暂时保留旧 `TrainingCycle.skill_tree_version`。

### C. data migration：拆分项目级技能树版本

对每个旧 `SkillTreeVersion`：

1. 获取其 `skill_project` 下 TechnicalDomain；
2. 将旧“项目级版本”拆成各领域独立版本；
3. 每个新领域版本复制：
   - version；
   - name；
   - description；
   - is_current；
   - created_by；
   - 尽可能保留 created_at / updated_at；
4. 按旧 `SkillTreeNode.technical_domain` 将节点移动到对应的新领域版本；
5. 对引用旧版本的每个 TrainingCycle，为各领域版本创建 `TrainingCycleSkillTreeVersion`；
6. 原旧 tree record 可作为其中一个领域版本复用，其他领域创建 clone，避免无必要破坏 PK；
7. 对旧版本中某领域没有节点的情况，也要考虑旧“项目级版本”语义本来覆盖整个项目：
   - 默认应为该项目已有 TechnicalDomain 建立对应空版本；
   - 这样当前版本和 TrainingCycle 的标准快照不会因为“该领域当时刚好没有节点”而消失；
8. 如果发现旧 SkillTreeVersion 对应 SkillProject 连一个 TechnicalDomain 都没有，migration 必须明确失败并提示修复数据，禁止静默删除版本。

如果历史数据规模或实际状态使上述策略需要微调，Codex 应先通过 ORM / migration state 验证当前分支数据约束，再保持“零静默丢失”的原则实现。

### D. standards finalize migration

数据迁移成功后：

1. `SkillTreeVersion.technical_domain` 改为 non-null；
2. 添加：
   - unique(technical_domain, version)
   - conditional unique current per technical_domain
3. 删除 `SkillTreeVersion.skill_project`；
4. 删除 `SkillTreeNode.technical_domain`；
5. 更新相关索引/ordering。

### E. training finalize migration

确认 through 数据完整后：

1. 删除旧 `TrainingCycle.skill_tree_version`；
2. 保留新的 through M2M；
3. 增加 through model 最终约束。

---

# 10. 权限

继续遵循：

```text
Django Permission
+
TechnicalDomainMembership 对象范围
```

## SkillTree

所有树写操作由：

```text
tree_version.technical_domain
```

确定权限范围。

不再允许客户端提交 domain 来扩大操作范围。

领域教练：

- 只能维护有 membership 的领域树；
- 只能编辑其主要领域允许管理的 Skill；
- shared Skill 的修改仍遵循现有 `can_manage_skill()` 规则。

## WSOS

WSOS 是 SkillProject 级标准，不是 TechnicalDomain 权限轴。

因此：

- WSOSVersion / Section 管理由 Django model permission 控制；
- 不按某一个 TechnicalDomainMembership 限制整个 WSOSSection；
- Skill 搜索中的 domain 仅为过滤条件，不是 WSOS ownership。

---

# 11. CONTEXT.md / 文档同步

必须更新 `CONTEXT.md`，因为当前文件仍描述：

```text
每个技术领域通过独立页面展示同一版本中的本领域结构
TrainingCycle 固定一个技能树版本
```

调整为：

### SkillTreeVersion / SkillTreeNode

- SkillTreeVersion 属于一个 TechnicalDomain；
- 每个 TechnicalDomain 独立维护 current version；
- SkillTreeNode 不再存 technical_domain；
- 同一个 Skill 可以在其允许的多个技术领域各自的树版本中出现；
- 历史 Evidence / TrainingTask / Scoring 仍只关联稳定 Skill，不关联节点。

### TrainingCycle

改为：

> TrainingCycle 固定训练周期内各相关 TechnicalDomain 使用的 SkillTreeVersion，每个技术领域最多一个版本。

### WSOS

明确：

> 当前 WSOS 建模粒度止于 WSOSSection。Skill 与 WSOSSection 为多对多映射；WSOS 不承担训练组织权限。

不要新增 WSOSItem 规划描述。

---

# 12. 导航与文案

`core/config/navigation.yml`：

建议把：

```text
WSOS 版本
```

导航文案改为：

```text
WSOS
```

因为该入口完成后管理的是完整 WSOS 版本及 Section 内容，而不只是版本壳。

“技能树版本”可以继续保留作为历史版本查询入口。

“标准技能树”继续作为日常维护入口。

---

# 13. 测试要求

## 13.1 standards model tests

至少覆盖：

1. 不同 TechnicalDomain 可使用相同版本号；
2. 同一 TechnicalDomain 版本号唯一；
3. 每个 TechnicalDomain 最多一个 current；
4. 不同领域可分别有 current；
5. SkillTreeNode domain 正确从 tree_version 推导；
6. Skill 不允许挂入未关联的 TechnicalDomain tree；
7. parent 必须同 tree_version；
8. 同一 Skill 同 tree_version 只能一次；
9. shared Skill 在允许的两个不同领域版本中可分别挂载；
10. 修改 Skill related_domains 时不能使既有树位置失效。

## 13.2 tree service tests

覆盖：

- add root；
- add child；
- add sibling；
- reorder；
- same-tree move；
- remove/promote；
- remove subtree；
- attach unmounted Skill；
- 权限；
- 不再存在跨领域 move 参数/路径。

## 13.3 list view tests

覆盖：

- 只列当前 tree_version 节点；
- name search；
- alias search；
- description search；
- difficulty filter；
- core filter；
- assessable filter；
- active filter；
- 当前 WSOS mapped/unmapped；
- django-tables2 sort；
- 搜索关系不会产生重复 row；
- 无权限用户不可借筛选参数看到其他对象。

## 13.4 tree search tests

覆盖：

- 结果只来自当前 tree；
- alias 能命中；
- 返回 full path；
- 同项目但未挂入当前 tree 的 Skill 不出现在树搜索结果。

## 13.5 WSOS tests

覆盖：

- Section create/edit；
- code 在同 WSOSVersion 内唯一；
- weight 范围；
- 一个 Skill 映射多个 Section；
- 一个 Section 映射多个 Skill；
- cross-project mapping 被拒绝；
- 重复 mapping 不产生重复记录；
- 已映射 Section 不能直接删除；
- 添加/解除映射权限；
- WSOS detail 正确显示 section 和 mapped skill count；
- 权重总计显示。

## 13.6 TrainingCycle tests

覆盖：

- 一个周期可固定多个领域不同版本；
- 同领域不能固定两个版本；
- tree version 必须与 link domain 一致；
- domain/tree 必须属于 cycle SkillProject；
- 新周期默认选择各领域 current tree；
- 历史 tree version 可以继续绑定；
- TrainingTask 只能选择 cycle 已绑定版本的领域；
- 编辑旧周期能够保留历史版本。

## 13.7 migration test

本次属于结构性数据迁移，建议增加 migration test 或等价的可重复迁移验证。

至少构造：

```text
1 SkillProject
3 TechnicalDomain
2 个旧 project-level SkillTreeVersion
各领域 SkillTreeNode
1 TrainingCycle -> 旧 current tree
```

迁移后验证：

```text
每个旧版本被拆成 3 个领域版本
current 状态按领域正确继承
node 被移动到正确领域版本
TrainingCycle 生成 3 条领域版本绑定
Skill / Evidence / TrainingTask 等稳定业务 ID 未变化
```

---

# 14. 推荐实施顺序

Codex 按以下顺序执行，不要先大改模板再回头修模型。

### Phase 1：确认引用面

全仓搜索：

```text
SkillTreeVersion
skill_tree_version
SkillTreeNode.technical_domain
technical_domain_id
current_skill_tree_for
skill_tree_structure
unmounted_primary_skills_for_tree_domain
move_skill_tree_node
tree_domain_detail
```

确认所有跨 APP 引用。

### Phase 2：模型与 migration

先完成：

- SkillTreeVersion domain 化；
- SkillTreeNode 去 domain；
- TrainingCycle 多领域版本绑定；
- staged data migration；
- model tests。

### Phase 3：selectors / services

再调整：

- current selector；
- tree structure；
- unmounted skills；
- create/attach/edit/move/remove/reorder service；
- Skill related domain 校验；
- permission scope。

### Phase 4：现有树形工作台适配

让现有：

- current tree；
- historical tree；
- inline add；
- detailed create；
- edit；
- move；
- remove；
- reorder；
- unmounted skill

在新模型下恢复全部功能。

先保证原有能力不回退，再新增列表功能。

### Phase 4A：版本克隆能力

完成：

- `SkillTreeVersion.based_on`；
- 基于当前版本创建；
- 基于历史版本创建；
- 创建空白版本；
- `clone_skill_tree_version()`；
- 两阶段复制节点并恢复 parent；
- 默认非 current；
- 显式 current 切换；
- 版本克隆测试。

### Phase 5：树搜索 + 列表视图

新增：

- tree search；
- tree/list tabs；
- SkillTreeNodeTable；
- FilterableListMixin；
- filters；
- sorting；
- full_path；
- current WSOS mapping status。

### Phase 6：WSOS Section 工作台

新增：

- Section CRUD；
- detail UI；
- mapped skill count；
- add/remove Skill mapping；
- weight total；
- SkillDetail 映射展示改进。

### Phase 7：Training UI

完成：

- TrainingCycleForm 多领域版本；
- current default；
- historical binding；
- TrainingTask domain 限制。

### Phase 8：文档 / navigation

更新：

- CONTEXT.md；
- 必要时 AGENTS.md 中受影响的稳定领域描述；
- navigation label；
- 相关用户手册（仅已有对应内容时更新，不机械新增大篇文档）。

### Phase 9：验证

完成全部聚焦测试和必要的全量测试。

---

# 15. 明确不做

本轮不要实现：

- 独立技能目录/技能库日常维护页；
- WSOSItem；
- WSOS 子条目树；
- WSOS -> TechnicalDomain 直接映射；
- StandardRelease / 跨领域发布包；
- SkillVersion / Skill 字段快照；
- 自动根据 WSOS 生成 Skill；
- 自动根据 Skill 生成训练计划；
- 将 Evidence / TrainingTask / ScoringResult 改绑到 SkillTreeNode；
- 技能树任意排序；
- 跨 TechnicalDomain 的一次性 subtree move；
- 与本轮无关的 standards / training 全面重构。

---

# 16. 验证命令

本次属于模型 + migration + standards/training 跨 APP + 模板交互的重要修改，允许并建议比普通小改动更完整地验证。

至少执行：

```bash
uv run manage.py makemigrations --check --dry-run
uv run manage.py migrate
uv run manage.py check

uv run pytest standards training
uv run ruff check standards training
```

完成后建议执行：

```bash
uv run pytest
```

如修改了 Tailwind / DaisyUI / Iconify class、Alpine 前端代码或相关模板：

```bash
npm run build:css
```

不要为了通过与本次修改无关的历史失败而扩大修改范围。

---

# 17. Definition of Done

满足以下条件才算完成：

- [ ] 每个 TechnicalDomain 独立拥有 current SkillTreeVersion；
- [ ] SkillTreeVersion 不再持久化 skill_project；
- [ ] SkillTreeNode 不再持久化 technical_domain；
- [ ] TrainingCycle 能固定多个技术领域各自的树版本；
- [ ] TrainingTask 领域受周期版本绑定约束；
- [ ] 当前树和历史树都能正常浏览/编辑；
- [ ] 树形视图可搜索并定位；
- [ ] 列表视图支持搜索、筛选、排序；
- [ ] 不恢复独立技能列表日常入口；
- [ ] WSOSVersion 可维护 Section 内容；
- [ ] Section 可维护 Skill 多对多映射；
- [ ] 不存在 WSOSItem；
- [ ] WSOS 不直接绑定 TechnicalDomain；
- [ ] 旧技能树和训练周期版本数据通过 migration 正确迁移；
- [ ] CONTEXT.md 与新模型一致；
- [ ] 聚焦测试通过；
- [ ] migration check 通过；
- [ ] Django system check 通过；
- [ ] 重要跨 APP 回归验证完成。

---

# 18. 推荐 Codex 模型与推理强度

本任务不是普通 CRUD，而是：

- Django schema 重构；
- 跨 `standards` / `training` APP；
- 有数据迁移；
- 有领域不变量变化；
- 有 HTMX / django-tables2 UI；
- 有权限范围；
- 需要保持历史数据语义。

**推荐主执行模型：GPT-5.6 Sol**

**推荐推理强度：High**

理由：

- 需要先完整追踪引用关系，再安全修改；
- migration 拆分 project-level tree version 的逻辑容易产生隐蔽数据错误；
- TrainingCycle 的版本语义不能只做字段替换；
- UI 与 model/service/selector 必须同时保持一致。

如果 Codex 环境提供 Extra High，可用于：

- migration 方案复核；
- 最终全量 review；
- 出现复杂迁移/测试失败时。

不建议整个实施过程默认使用 Max / Pro；当前任务虽复杂，但边界已明确，`Sol + High` 更适合质量、速度和额度之间的平衡。

如果希望降低额度：

- 主模型仍建议 Sol + High 完成 Phase 1–4（模型、迁移、service）；
- 后续纯模板整理、小型测试修复可以切 Terra + Medium/High；
- 不建议用 Luna 承担本次主 schema 重构。
