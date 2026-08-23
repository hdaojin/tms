# TMS 标准体系权限与 TechnicalDomain Scope 优化实施 Plan

> 面向 Codex 的可执行实施计划  
> 基线分支：`develop`  
> 基线提交：`50b5f8c80eed736f5da4955d234fc7dd5036dd5c`（标准体系基本定型）  
> 日期：2026-08-22

## 1. 任务目标

在不推翻 TMS 现有 Django Permission 授权架构的前提下，完成标准体系权限模型收敛：

1. 将 **Group 明确作为管理员定义业务角色的主要载体**。
2. 将 **Permission Bundle 收敛为 APP 内、小粒度、相关 Django Permission 的集合**，不再承担“技术教练”“项目管理员”等角色语义。
3. 将技术领域权限范围从当前的 `User -> TechnicalDomainMembership -> TechnicalDomain` 改为：
   `User -> Group -> TechnicalDomainGroupScope -> TechnicalDomain`。
4. 普通用户的技术领域写权限必须同时满足：
   - 用户所属的某一个 Group 拥有所需 Django Permission；
   - **同一个 Group** 拥有目标 `TechnicalDomain` 的 Scope。
5. `superuser` 作为唯一全局管理员，直接拥有全部权限和全部技术领域范围。
6. 标准体系采用：
   - **全项目可查看**
   - **按 TechnicalDomain 维护**
7. 删除不再需要的：
   - `training.coach`
   - `training.project_admin`
   - `standards.manage_all_technical_domains`
   - `TechnicalDomainMembership`
8. 保持当前“Permission 决定能做什么，policy/selector 决定能对哪些对象做”的授权原则，不引入通用 Scope 引擎、对象权限第三方库或 User 级 Scope。

## 2. 必须遵守的正式决策

### 2.1 Django Permission 仍是运行时权限事实

继续遵守 ADR 0003：

- View / service / selector 不判断 Permission Bundle code；
- 不根据 Group 名称或 `GroupProfile.codename` 授权；
- Permission Bundle 仅用于配置和同步 `Group.permissions` / `User.user_permissions`；
- 业务代码最终仍基于 Django Permission + 业务范围 policy 做授权。

禁止写：

```python
if user.groups.filter(name="Linux 技术教练").exists():
    ...
```

也禁止写：

```python
if "standards.maintain_skills" in user.profile.selected_permission_bundles:
    ...
```

### 2.2 Group 是角色，Permission Bundle 不是角色

管理员可以创建：

- Linux 技术教练
- Windows 技术教练
- Network 技术教练
- Linux 主教练
- 综合技术教练

代码不识别这些名称。

角色最终由以下两部分组成：

```text
Group
├── Django Permissions（由 Permission Bundle / explicit permissions 投影）
└── TechnicalDomain Scopes
```

### 2.3 不设计 User Scope

本次明确不实现：

- User -> TechnicalDomain Scope；
- User 临时 Scope；
- allow / deny / override；
- 通用 Generic Scope；
- ContentType 驱动的泛型对象权限；
- 第三方 object permission 框架。

用户例外通过调整 Group 或新建适当 Group 解决。

### 2.4 superuser 是唯一全局管理员

普通用户全部受 Group Permission + Group Domain Scope 限制。

不要保留或重新创建：

- project admin 角色；
- `manage_all_technical_domains`；
- `*_all_domains` 类权限。

### 2.5 Scope 与 Permission 必须来自同一个 Group

这是本次实现的安全不变量。

禁止采用：

```text
用户所有 Permission 的并集
+
用户所有 Domain Scope 的并集
```

否则会产生跨 Group 的权限串联。

例如：

```text
Group A：change_skill + Linux
Group B：view_skill + Windows
```

正确结果：

```text
change Linux：允许
view Windows：允许
change Windows：拒绝
```

因此领域写权限必须按如下逻辑判断：

```text
ALLOW
=
superuser
OR
存在一个用户所属 Group：
    Group 拥有所需 Permission
    AND
    Group Scope 包含目标 TechnicalDomain
```

实现时优先封装为 standards 的统一 selector/policy helper，不在每个 View 重复查询。

## 3. 数据模型调整

### 3.1 新增 `TechnicalDomainGroupScope`

位置：`standards/models.py`

推荐模型：

```python
class TechnicalDomainGroupScope(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="technical_domain_scopes",
        verbose_name="用户组",
    )
    technical_domain = models.ForeignKey(
        TechnicalDomain,
        on_delete=models.CASCADE,
        related_name="group_scopes",
        verbose_name="技术领域",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "技术领域用户组范围"
        verbose_name_plural = "技术领域用户组范围"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "technical_domain"],
                name="uniq_technicaldomain_group_scope",
            ),
        ]
```

要求：

- 模型属于 `standards` APP，不向 `accounts.GroupProfile` 注入 standards 业务字段；
- 一个 Group 可以拥有多个 TechnicalDomain；
- 一个 TechnicalDomain 可以绑定多个 Group；
- 不增加 role / lead_coach / coach 字段；
- 不为未来可能出现的 Scope 提前泛型化。

### 3.2 删除 `TechnicalDomainMembership`

确认代码中无独立业务用途后删除：

```python
TechnicalDomainMembership
```

同时删除：

- `Role.LEAD_COACH`
- `Role.COACH`
- 对应 Admin 注册；
- 表单引用；
- selector 查询；
- 测试 fixture / factory；
- 文档说明；
- migrations 中仅通过新增 migration 删除，不修改历史 migration。

## 4. Scope 授权 Policy

### 4.1 新建/重构统一 helper

保留 `standards/selectors.py` 作为读取和范围判断的主要位置。

建议将当前：

```python
is_project_admin()
manageable_domains_for()
can_manage_domain()
```

重构为更直接的语义，例如：

```python
scoped_domains_for(user, permission, skill_project=None)
can_manage_domain(user, domain, permission)
```

具体命名可结合现有项目风格调整，但必须满足以下行为。

### 4.2 `scoped_domains_for()`

输入：

- `user`
- 所需 permission，例如 `standards.change_skill`
- 可选 `skill_project`

行为：

```text
未登录 -> none
superuser -> 全部目标领域
普通用户 ->
    查找 user.groups 中同时满足：
        group.permissions 包含所需 Permission
        group 对 TechnicalDomain 有 Scope
```

注意：

- 不通过 `user.has_perm(permission)` + “任意 scoped group” 两步拼接；
- 必须保持同一个 Group 的 Permission + Scope 关系；
- 查询应使用 Django ORM 一次完成，避免循环 Group / Permission / Scope 造成 N+1；
- Permission 应按 `app_label + codename` 严格解析，避免只按 codename 产生模型歧义。

### 4.3 `can_manage_domain()`

继续作为 service/view 的明确授权入口。

语义：

```text
superuser -> True
普通用户 ->
    domain ∈ scoped_domains_for(user, permission)
```

### 4.4 Skill

查看：

```text
有 standards.view_skill -> 全项目可见
```

不再因 Domain Scope 隐藏其他领域 Skill。

修改：

```text
required permission = standards.change_skill
scope domain = skill.primary_domain
```

新增：

```text
required permission = standards.add_skill
scope domain = 新 Skill.primary_domain
```

`related_domains` 不赋予 Skill 维护权。

### 4.5 当前技能树内容

对 `SkillTreeNode`：

```text
scope domain = tree_version.technical_domain
```

新增、挂载、移动、排序、移除分别检查相应 Django Permission + Domain Scope。

### 4.6 技能树版本

版本治理现阶段仅由 superuser 负责：

- 创建 SkillTreeVersion；
- 修改版本元数据；
- 设置当前版本；
- 基于历史版本创建版本。

普通 Domain Group 即使有当前技能树节点维护权，也不得治理版本。

如现有页面依赖普通 `add/change_skilltreeversion` Permission，收紧为 superuser gate 或不向任何普通 Bundle 提供这些权限。

### 4.7 SkillProject / TechnicalDomain / WSOS

现阶段仅 superuser 维护：

- SkillProject；
- TechnicalDomain；
- SkillTreeVersion；
- WSOSVersion；
- WSOSSection；
- SkillWSOSMap。

普通标准体系查看者可查看这些对象。

不要为这些低频治理操作额外创建“项目管理员”角色。

## 5. 标准体系 Permission Bundle 重构

修改：

`core/config/permission_bundles.yml`

### 5.1 保留并校正 `standards.view_standard`

定位：

> 查看整个标准体系，不受 Domain Scope 限制。

建议包含：

```text
standards.view_skillproject
standards.view_technicaldomain
standards.view_skill
standards.view_skilltreeversion
standards.view_skilltreenode
standards.view_wsosversion
standards.view_wsossection
standards.view_skillwsosmap
```

### 5.2 新增 `standards.maintain_skills`

定位：

> 在 Group 的 TechnicalDomain Scope 内创建和修改长期 Skill。

建议：

```text
standards.view_skill
standards.add_skill
standards.change_skill
```

不要包含：

- SkillProject；
- TechnicalDomain；
- SkillTreeVersion；
- WSOS。

### 5.3 新增 `standards.maintain_current_tree`

定位：

> 在 Group 的 TechnicalDomain Scope 内维护当前技能树内容。

建议：

```text
standards.view_skilltreeversion
standards.view_skilltreenode
standards.add_skilltreenode
standards.change_skilltreenode
standards.delete_skilltreenode
```

如当前“在树中直接创建新 Skill”的工作流要求 `standards.add_skill`，不要把它隐式塞进本 Bundle；管理员应同时选择：

```text
standards.maintain_skills
standards.maintain_current_tree
```

这样 Bundle 边界更清晰。

### 5.4 删除 `standards.maintain_standard`

该 Bundle 粒度过大，混合：

- SkillProject；
- TechnicalDomain；
- Skill；
- SkillTreeVersion；
- SkillTreeNode；
- WSOS；
- SkillWSOSMap。

删除后不要创建等价“大包”。

## 6. 清理角色型跨 APP Permission Bundle

### 6.1 删除 `training.coach`

当前 `training.coach` 跨：

- standards
- assessments
- scoring
- evidence
- training

不再保留。

其能力由管理员在具体 Group 上组合各 APP 的 Bundle，例如：

```text
standards.view_standard
standards.maintain_skills
standards.maintain_current_tree
assessments.view_assessments
assessments.maintain_assessments
scoring.view_schemes
scoring.maintain_scoring
evidence.view_evidence
evidence.maintain_evidence
training.<对应 APP 内训练管理 bundle>
```

### 6.2 删除 `training.project_admin`

superuser 已承担全局管理，不保留等价替代物。

### 6.3 training APP 内部 Bundle

检查 `training.coach` 被删除后，是否缺少纯 training APP 的常规管理 Bundle。

如缺少，则按现有训练工作流拆分为 APP 内 Bundle，优先“小而够用”，不要机械按模型拆成几十个 Bundle。

建议至少评估：

```text
training.view_training
training.maintain_plans
training.maintain_tasks
```

具体 permissions 以当前 training views/services 实际依赖为准。

原则：

- 每个 Bundle 仅包含 `training.*`；
- 不在本次顺手重做训练业务权限语义；
- 保留已有 `training.view_all_logs`、`training.manage_all_logs` 等明确范围扩展 Bundle，除非实际代码审计发现冲突。

### 6.4 `training.competitor`

本次不要因为名称像角色就无条件扩大修改范围。

先检查其是否完全局限于 training APP 且实际表达“选手训练自助能力集合”。

如果它只是 APP 内常用能力集合，可以仅重命名为能力型名称；
如果改名会造成无关迁移和授权扰动，可记录后续清理项，不阻塞本次 standards Scope 重构。

## 7. 跨 APP selector 调整

TechnicalDomain 是训练组织和范围轴，因此本次必须检查当前直接依赖 Membership 的 APP。

### 7.1 `standards/selectors.py`

重点：

- 删除 `is_project_admin()` 的普通权限分支；
- `superuser` 单独 bypass；
- `manageable_domains_for()` 改为 Group Scope 逻辑，或替换为新的 permission-aware helper；
- `visible_skills_for()` 改为“有 view_skill 即全项目可见”；
- `manageable_skills_for()` 按 `primary_domain` + Group Permission/Scope；
- `skill_tree_structure()` 中所有 `can_*` 装饰必须按实际 permission 对应 scope 判断；
- 不再读取 `memberships__user`。

### 7.2 `assessments/selectors.py`

当前：

```text
technical_domain__memberships__user
manageable_domains_for(user)
```

必须改为 Group Domain Scope。

保持现有业务规则不变：

- participant 可见；
- explicit module coach assignment 可见/可管理；
- 单领域模块可由对应领域授权 Group 的教练管理；
- 跨领域模块仍优先通过显式教练分配管理，不因多个 Domain Scope 自动扩大。

不要借本次权限重构改变 Assessment 业务语义。

### 7.3 `training/selectors.py`

当前直接查询：

```text
domain_links__technical_domain__memberships__user
```

必须切换 Group Scope。

保持：

- 选手自己的执行记录；
- 显式 coach assignment；
- 单领域 TrainingTask 的领域管理；
- 跨领域 TrainingTask 的显式教练分配；
- TrainingLog 的本人 / `*_all` 范围规则。

特别注意：

> TrainingLog 的 owner scope 与 TechnicalDomain Scope 是不同范围来源，不要为了“统一 Scope”重构成通用框架。

### 7.4 evidence / scoring

搜索确认是否直接或间接依赖：

- `TechnicalDomainMembership`
- `manageable_domains_for`
- `manage_all_technical_domains`
- `is_project_admin`

有依赖则按相同原则修改；无依赖不要顺手重构。

## 8. Service / View 授权

### 8.1 Service 层继续做最终写入保护

保留 standards 当前 service 层的双重防护思想。

所有关键写操作不得只依赖：

- 页面是否显示按钮；
- Form queryset；
- View mixin。

例如：

- create skill in tree；
- attach existing skill；
- move node；
- reorder；
- remove node。

service 必须再次检查 Domain Scope。

### 8.2 View

View 负责：

- 基础 Django Permission；
- 获取业务对象；
- 调用 policy/service。

不要在各 View 复制 ORM Scope 查询。

### 8.3 模板

模板中的按钮显示仅作为 UX。

服务端权限必须独立成立。

## 9. Django Admin

### 9.1 Group Admin

当前 Group Admin 已经支持：

- Permission Bundle；
- explicit Django permissions。

本次增加“技术领域范围”配置。

推荐在 Group Admin 中以 inline 或横向多选方式维护 `TechnicalDomainGroupScope`。

要求：

- 展示“技能项目 / 技术领域”；
- 可一次给 Group 配置多个领域；
- 不在 User Admin 增加 TechnicalDomain Scope；
- 管理员无需再进入旧 `TechnicalDomainMembership` 页面。

### 9.2 User Admin

保持：

- Group 作为主要授权入口；
- User 直接 Bundle / explicit permissions 作为既有兼容能力，不扩展 User Scope。

对于需要 Domain Scope 的写权限：

> User 直接权限本身不能绕过 Group Domain Scope。

可在后台 help text 中说明这一点，避免管理员误解。

## 10. 数据迁移策略

### 10.1 不猜测 Group 角色关系

禁止 migration 通过以下方式自动推断：

- Group 名称；
- Group codename；
- 用户第一个 Group；
- 将一个用户 Membership 随机挂到其任意 Group。

这会产生潜在越权。

### 10.2 采用明确的硬切换

本项目仍处于训练体系重构阶段，本次采用明确硬切换：

1. 新增 `TechnicalDomainGroupScope`；
2. 调整代码只读取 Group Scope；
3. 删除 `TechnicalDomainMembership`；
4. 删除旧角色型 Bundle；
5. 由 superuser 在部署后按实际组织结构创建/调整 Group，并配置：
   - Permission Bundles；
   - Domain Scopes；
   - Group members。

如果生产环境存在必须保留的现有 Membership，在执行 schema migration 前：

- 先导出 `TechnicalDomainMembership` 当前对应关系作为人工迁移参考；
- 不在代码中长期保留兼容双轨；
- 不做自动推断授权。

Codex 可提供一个一次性只读 management command 或 Django shell 查询用于迁移前核对，但不要引入长期兼容层。

## 11. Permission Catalog 同步

由于当前 Permission Bundle 是部署期静态 Catalog：

1. 修改 `core/config/permission_bundles.yml`；
2. 删除旧 code：
   - `training.coach`
   - `training.project_admin`
   - `standards.maintain_standard`
3. 新增新的 APP 内 Bundle；
4. 更新权限 Catalog 校验测试；
5. 执行项目现有 reconciliation / sync 流程；
6. 确认旧 Bundle 派生到 Group/User 的权限投影不会残留。

不要直接编辑 `Group.permissions` 作为配置来源。

## 12. 测试矩阵

### 12.1 标准体系基础矩阵

准备：

```text
Domain:
- Linux
- Windows
- Network

Group:
- linux_coach: maintain_skills + maintain_current_tree + Linux scope
- windows_viewer: view_standard + Windows scope
- network_coach: maintain_skills + Network scope
```

至少覆盖：

| 场景 | 预期 |
|---|---|
| Linux coach 查看 Linux Skill | 允许 |
| Linux coach 查看 Windows Skill | 允许 |
| Linux coach 修改 Linux primary Skill | 允许 |
| Linux coach 修改 Windows primary Skill | 拒绝 |
| Linux coach 修改 primary=Windows, related=Linux Skill | 拒绝 |
| Linux coach 在 Linux 当前树新增/挂载/移动节点 | 允许 |
| Linux coach 操作 Windows 当前树 | 拒绝 |
| 普通 viewer 查看全部领域标准 | 允许 |
| 普通 viewer 修改任意 Skill/Tree | 拒绝 |
| superuser 操作任意领域 | 允许 |

### 12.2 防止跨 Group 权限串联

必须有安全回归测试：

```text
Group A:
  permission = change_skill
  scope = Linux

Group B:
  permission = view_skill
  scope = Windows
```

用户同时属于 A、B：

```text
change Linux -> True
view Windows -> True
change Windows -> False
```

这是本次最重要的权限测试之一。

### 12.3 Direct User Permission

用户直接拥有：

```text
standards.change_skill
```

但没有任何带对应 Scope 的 Group：

```text
修改 Linux Skill -> False
```

superuser 除外。

### 12.4 Cross-app

补充/调整：

- `assessments/tests.py`
- `training/tests.py`

确保：

- 原来由 TechnicalDomainMembership 控制的领域可见/可管理行为改由 Group Scope 控制；
- explicit coach assignment 继续生效；
- participant / owner scope 继续生效；
- `*_all` 既有规则不受破坏。

## 13. 文档与 ADR

### 13.1 更新 ADR

ADR 0003 的核心原则仍然成立，不推翻。

新增一份补充 ADR 更清晰，例如：

```text
docs/adr/0005-group-domain-scope-authorization.md
```

记录：

- Group 是角色载体；
- Permission Bundle 是能力集合，不是角色；
- TechnicalDomain Scope 绑定 Group；
- Scope + Permission 必须来自同一个 Group；
- User 不配置 Domain Scope；
- superuser 唯一全局 bypass；
- 不使用 Group name/codename 授权；
- 不引入通用 Scope 框架。

ADR 0003 中若存在与新方案直接冲突的表述，仅做最小交叉引用或说明，避免重写历史决策。

### 13.2 更新 `AGENTS.md`

仅更新稳定架构规则：

```text
TechnicalDomain 是 Group 级对象范围；
领域写权限必须由同一 Group 同时提供 Permission 和 Domain Scope；
superuser 是唯一全局 bypass。
```

### 13.3 更新 `CONTEXT.md`

删除 `TechnicalDomainMembership` 作为权限/教练职责模型的描述。

改为：

```text
技术领域权限范围由 Group -> TechnicalDomainGroupScope 表达。
```

### 13.4 用户文档

如果当前已有管理员权限配置文档，更新为：

```text
创建 Group（角色）
-> 选择 Permission Bundles
-> 选择 TechnicalDomain Scope
-> 将用户加入 Group
```

## 14. 推荐执行顺序

### Phase 1：现状确认

1. 阅读：
   - `AGENTS.md`
   - `CONTEXT.md`
   - ADR 0003
2. 搜索：
   - `TechnicalDomainMembership`
   - `memberships__user`
   - `manageable_domains_for`
   - `can_manage_domain`
   - `is_project_admin`
   - `manage_all_technical_domains`
   - `training.coach`
   - `training.project_admin`
3. 列出真实受影响文件，不做无关全仓重构。

### Phase 2：模型与 Scope policy

1. 新增 `TechnicalDomainGroupScope`；
2. 重构 standards scope helper；
3. 实现“同一个 Group 必须同时拥有 Permission + Scope”；
4. superuser bypass；
5. 补最小单元测试。

### Phase 3：standards 权限行为

1. 全项目查看；
2. Skill 按 primary_domain 维护；
3. 当前技能树按 tree domain 维护；
4. 版本/WSOS/项目/领域治理收紧为 superuser；
5. service 写保护同步。

### Phase 4：跨 APP 迁移

1. assessments；
2. training；
3. evidence/scoring 如实际存在依赖才修改；
4. 保留 explicit assignment / owner / participant 等既有 Scope 语义。

### Phase 5：Permission Bundle

1. 新增 standards 小粒度 bundles；
2. 拆除 `training.coach`；
3. 删除 `training.project_admin`；
4. 删除 `standards.maintain_standard`；
5. 补齐必要的纯 training bundle；
6. Catalog check / reconciliation tests。

### Phase 6：Admin

1. Group 页面配置 Domain Scope；
2. 删除 Membership Admin；
3. User 页面不增加 Domain Scope。

### Phase 7：删除旧模型和权限

1. 删除 `TechnicalDomainMembership`；
2. 删除 `manage_all_technical_domains`；
3. 生成 migration；
4. 清理 imports/forms/tests/docs。

### Phase 8：验证

执行项目现有最小必要检查，至少包括：

```bash
python manage.py check
python manage.py makemigrations --check
```

以及与本次直接相关的 tests：

```text
standards
accounts permission assignment / catalog
assessments
training
```

如仓库使用 pytest，则遵循当前项目实际命令，不自行更换测试框架。

最后再执行权限 Catalog reconciliation 的 dry-run，确认无旧 Bundle / 派生权限残留。

## 15. 非目标

本次明确不做：

- 通用 RBAC 框架；
- ABAC 框架；
- django-guardian 等第三方对象权限；
- Generic Scope；
- User Domain Scope；
- deny / override；
- 按 Linux / Windows / Network 生成不同 Django Permission；
- 按技术领域拆 Skill model；
- 重构 owner / participant / assignment 等现有业务范围；
- 大规模重做所有 APP 的权限体系；
- 为未来假设需求预留复杂抽象。

## 16. 完成标准

1. 代码中不存在 `TechnicalDomainMembership` 运行时依赖。
2. 代码中不存在 `standards.manage_all_technical_domains`。
3. `training.coach`、`training.project_admin` 不再存在于 Permission Bundle Catalog。
4. 标准体系 Permission Bundle 均为 APP 内能力集合。
5. Group 可以配置一个或多个 TechnicalDomain Scope。
6. User 页面没有 Domain Scope。
7. 普通用户领域写权限必须由同一个 Group 同时提供 Permission + Scope。
8. 标准体系全项目可查看。
9. Skill 只由其 `primary_domain` 对应范围维护。
10. 当前技能树只由树所属 TechnicalDomain 范围维护。
11. SkillTreeVersion / SkillProject / TechnicalDomain / WSOS 现阶段仅 superuser 治理。
12. superuser 可以访问和维护全部领域。
13. assessments / training 原有领域约束与显式分配逻辑没有回归。
14. owner / participant / `*_all` 等非 Domain Scope 规则没有被误改。
15. 权限 Catalog、system check、相关 tests 全部通过。
16. ADR / AGENTS / CONTEXT 与最终实现一致。

## 17. Codex 执行要求

- 不重新讨论已经确定的业务方案，按本 Plan 实施。
- 遇到代码细节与 Plan 不一致时，以“正式决策 + 当前真实代码”判断最小兼容实现。
- 不因为权限重构顺手清理无关旧代码。
- 不新增通用权限框架。
- 不通过 Group 名称/codename 判断权限。
- 不降低 service 层写保护。
- 迁移涉及授权数据时优先安全，宁可明确要求管理员重新配置，也不要自动猜测并造成越权。
- 实施完成后输出：
  1. 修改摘要；
  2. 数据模型/迁移说明；
  3. Permission Bundle 变化；
  4. 管理员重新授权步骤；
  5. 测试结果；
  6. 仍需人工处理的生产配置。

## 18. 推荐 Codex 模型与推理能力

### 首选

```text
模型：GPT-5.6 Sol
推理强度：High
```

原因：

- 本任务跨 `standards / accounts / assessments / training / core config`；
- 涉及 Django auth、Group permission 来源、对象范围、数据迁移和安全回归；
- 需要在多个 selector/service 之间保持授权语义一致；
- 最大风险是隐蔽越权或授权缺口，而不是普通 CRUD 实现难度。

`High` 比 `Medium` 更适合本次权限架构修改；当前方案已经充分收敛，没有必要默认使用最高档推理。

### 可选升级

如果环境提供更高推理档位，可仅在以下阶段使用更高能力：

```text
xhigh / max
```

用于：

- 最终权限安全 review；
- 复杂 migration review；
- 出现跨 Group 权限串联或难以解释的测试失败时。

不建议整次任务默认使用最高档位。

### 不建议作为主执行模型

```text
Luna / 低推理档
```

可用于机械性文档整理或重复性修复，但不建议承担本次权限核心设计和授权判断修改。
