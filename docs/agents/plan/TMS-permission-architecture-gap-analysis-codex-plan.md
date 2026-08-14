# TMS 权限架构 Gap Analysis 与 Codex 执行 Plan

> 仓库：`hdaojin/tms`
> 基线分支：`develop`
> 审阅基线提交：`33c67fdd5b42a35ba3744211edfc481e2c93ae36`
> 审阅日期：2026-08-13
> 架构复核日期：2026-08-14
> 决策状态：已通过 `grilling` 确认；Permission Bundle 采用部署期 YAML Catalog，旧授权配置采用硬切换，不保留数据兼容层
> 目标运行基线：Django 6 / Python 3.13 / django-htmx / django-tables2 / Tailwind CSS 4 / DaisyUI 5 / Alpine.js CSP build / Iconify

---

## 1. 任务目标

基于当前 `develop` 实现，将 TMS 权限体系重构为已经正式定稿的目标架构：

1. **Django Permission 是唯一运行时授权事实来源。**
2. **Business Permission Bundle 只是 Django Permission 的业务化配置层。**
3. **Django Group 是站点管理员完全自定义的角色，不内置“教练 / 选手 / 班务”等授权角色。**
4. **业务代码禁止依赖 Group 名称或固定 Group codename 决定权限。**
5. **默认拒绝（deny by default）：登录只完成身份认证，没有业务 Permission 就没有对应业务页面、数据、附件、下载、HTMX 端点和菜单访问权。**
6. **普通 `view/change/delete` Permission 表示该动作在默认对象范围内有效；`*_all_*` 自定义 Django Permission 用于扩大数据范围；真正的对象过滤由 QuerySet / Selector / Policy 实现。**
7. **`is_superuser=True` 保持 Django 原生全权限语义；`is_staff` 只表示 Django Admin 准入资格，不代表 TMS 业务权限。**
8. **菜单是后端权限的 UI 投影，不是授权边界。**
9. **业务附件和文件下载同样必须经过授权；不能因为页面受限而继续通过直接媒体 URL 绕过。**
10. **Permission Bundle Catalog 使用 `core/config/permission_bundles.yml`，属于受版本控制、随部署生效的静态安全策略；Django Admin 只分配 Bundle，不在线编辑 Bundle 定义。**
11. **Bundle 选择与显式额外权限是授权配置的两类来源；`Group.permissions` / `User.user_permissions` 只是二者合并后的原生权限投影。**
12. **本次不兼容旧授权配置：删除旧 Bundle 反推、回填、code rewrite 和固定角色授权逻辑，通过一次性硬切换重新分配权限。**
13. **配置治理统一的是所有权和生命周期，不把部署配置、静态 Catalog、数据库在线设置、业务模型和 fixtures 强行搬进同一目录。**

本次任务不是重写认证系统，也不引入 django-guardian 或第二套 RBAC/ACL 框架。

---

## 2. 已定稿的权限模型

### 2.1 授权链路

```text
core/config/permission_bundles.yml
        ↓ strict load / validate
core.permissions registry
        ↓ bundle code → Django Permission

User
 ├─ direct Permission Bundles
 ├─ direct explicit Permissions
 └─ Groups（管理员自定义角色）
      ├─ Permission Bundles
      └─ explicit Permissions
             ↓ accounts assignment service
       native Django Permissions（物化投影）
             ↓
   ┌─────────┴─────────┐
   │                   │
View / Action      Selector / Policy
能不能做             能操作哪些对象
   │                   │
   └─────────┬─────────┘
             ↓
          QuerySet
             ↓
   Menu / Template / HTTP / HTMX / File
```

运行时只允许：

```python
request.user.has_perm(...)
request.user.has_perms(...)
PermissionRequiredMixin
permission_required(...)
{% if perms.app.codename %}
```

运行时业务代码**不得**通过 Permission Bundle 判断权限。

Catalog 也不参与每次请求的动态授权计算。Catalog 变更必须通过显式 reconciliation，把新的 Bundle 展开结果与 `explicit_permissions` 合并并写回 Django 原生 M2M；运行时仍然只使用 Django 原生权限接口。

### 2.2 Role / Group 规则

Django `Group` 就是 TMS 的角色容器，但角色完全由站点管理员创建和组合。

允许：

```text
网络项目选手
主教练
助理教练
资料管理员
翻译老师
赛事专家
基地负责人
```

禁止：

```python
if user.groups.filter(name="教练").exists():
    ...

if GROUP_COMPETITOR in group_names:
    ...
```

同一用户可以同时属于多个 Group；有效权限由 Django 原生规则合并。

### 2.3 Own / All 规则

以 `TrainingLog` 为例：

```text
training.view_traininglog
    → 有“查看训练日志”的能力
    → 默认 Scope：本人

training.view_all_traininglog
    → 扩大查看 Scope：全部

training.change_traininglog
    → 有“修改训练日志”的能力
    → 默认 Scope：本人

training.change_all_traininglog
    → 扩大修改 Scope：全部
```

Selector 示例目标：

```python
def get_training_logs_visible_to(user):
    qs = TrainingLog.objects.all()

    if user.is_superuser:
        return qs

    if not user.has_perm("training.view_traininglog"):
        return qs.none()

    if user.has_perm("training.view_all_traininglog"):
        return qs

    return qs.filter(uploaded_by=user)
```

注意：

- `Permission` 解决“能不能做”。
- `Selector` 解决“能对哪些对象做”。
- 不建立通用对象 ACL 数据表。
- 不把 `own` / `all` 做成第二套权限系统。

---

# 3. 当前实现的总体判断

当前代码**不需要推翻重做**。

已有机制中最重要的方向是正确的：

- `core/permissions/bundles.py` 已经把 Permission Bundle 定义为 Django Permission 的组合，并实际承担 code → `auth.Permission` 的解析。
- `accounts/services/permission_bundles.py` 已经把 Bundle 选择保存到 Profile，并将展开结果同步到原生 `Group.permissions` / `User.user_permissions`。
- 业务运行时未发现直接按 Bundle code 授权，目标中的“Django Permission 是唯一运行时事实来源”已有基础。

但当前“额外原生 Permission”只是通过以下差集临时推断：

```text
当前 native M2M
−
按当前 Catalog 展开的 Permission
```

这不是稳定的来源记录。若 Bundle 原为 `{A, B}`，Catalog 后来移除 `B`，旧的 `B` 会被误判成 explicit extra 并永久保留；删除整个 Bundle code 时问题更严重。Catalog 变化也不会自动触发全量同步，JSON 与 M2M 写入当前没有 service 事务边界。

因此本次重构保留“原生 Django Permission 作为运行时投影”的核心机制，但必须重建配置来源和同步边界，重点解决以下差距：

1. 固定角色假设仍散落在业务代码。
2. 大量 GET 页面只有登录保护，没有业务 `view_*` 权限。
3. 菜单当前默认 fail-open。
4. Own / All Scope 没有统一执行。
5. 部分详情、修改和附件下载存在横向越权。
6. 敏感文件仍可能通过公共媒体 URL 绕过业务 View。
7. 默认 fixture 内置了业务 Group。
8. 权限包粒度偏“大而全”，尤其 `training.maintain_training`。
9. `AGENTS.md` / `tms-dev` 中仍存在“稳定角色 codename”旧原则，与新架构冲突。
10. Bundle Catalog、explicit extra 与 native M2M 没有可确定重建的来源模型。
11. 静态配置、部署配置、数据库在线配置和 fixture 的所有权边界未明确。

---

# 4. Gap Analysis：系统级

| 编号 | 当前实现 | 目标架构 | 风险 | 处理 |
|---|---|---|---|---|
| G-01 | `accounts/fixtures/accounts/default.yaml` 内置“教练 / 选手 / 班务” | 角色全部由站点管理员自定义 | P1 | 删除旧角色 fixture；硬切换只清授权配置，保留已有 Group、membership 与其他业务关系 |
| G-02 | `core/constants.py` 定义固定 Group 名称 | 权限逻辑不得依赖固定角色名 | P1 | 移除授权相关固定 Group 常量及引用 |
| G-03 | `CrossGroupAccessMixin` 按“教练/选手”互访 | Permission + Selector Scope | P1 | 删除/废弃该授权方式 |
| G-04 | 多数业务 List/Detail 只有 `LoginRequiredMixin` | 登录后仍必须有业务 Permission | P1 | 所有业务 GET 入口增加显式 `view_*` |
| G-05 | `navigation.yml` 叶子菜单缺 `permissions` 时登录用户可见 | 菜单 fail-closed | P1 | 反转默认策略；无明确授权条件的业务菜单隐藏 |
| G-06 | `users/roles` 菜单按 `is_staff`，View 按业务 Permission | 菜单与 View 使用同一授权条件 | P1 | 用户管理使用 `accounts.view_all_profiles`；角色页使用明确 Django Permission |
| G-07 | `is_staff` 在部分 UI 中被当作角色展示 | `is_staff` 只是 Django Admin 准入 | P2 | 与业务角色 Badge 分离 |
| G-08 | Permission Bundle 定义硬编码在 Python，并使用三元组引用 | 部署期静态 Catalog，Bundle → Django Permission 对应关系清晰 | P2 | 迁移到 `core/config/permission_bundles.yml`，使用 `app_label.codename` 并严格校验 |
| G-09 | 新注册用户没有可配置默认 Group | 可选默认注册角色 | P2 | `SiteConfig` 增加可选 default registration Group |
| G-10 | 零权限用户登录后仍能看到大量业务菜单/页面 | deny-by-default | P1 | 登录落地页只显示可授权内容；无权限时显示“尚未获得业务访问权限” |
| G-11 | 文件访问策略不统一，`settings.PRIVATE_MEDIA_ROOT` 与 `core.constants.PRIVATE_MEDIA_ROOT` 还是双重来源 | 文件与父业务对象同等授权，路径来源唯一 | P0/P1 | 敏感文件使用 private storage + permission checked download；Notes 改用 `settings.NOTES_ROOT` |
| G-12 | `AGENTS.md` / `tms-dev` 仍允许角色 codename 授权思路 | Group 名称/codename 不参与业务授权 | P2 | 同步更新项目规范和开发工作流 |
| G-13 | extra Permission 由 native M2M 与当前展开结果做差推断 | explicit extra 是独立、可审计的配置来源 | P0 | GroupProfile/UserProfile 增加 `explicit_permissions`；native M2M 仅作投影 |
| G-14 | Catalog 变化不会自动重算既有 Group/User | 配置变更可检查、可预览、可确定授权和撤权 | P0 | 增加 strict system checks 与 `reconcile_permission_assignments` dry-run/apply 流程 |
| G-15 | 未知 Bundle code、重复 code、缺失 Permission 会被静默忽略或覆盖 | 配置错误必须 fail loudly | P0 | 禁止静默归一化；校验失败阻止部署与同步 |
| G-16 | `.env/settings`、`core/config`、SiteConfig、fixtures、constants 的配置语义未明确 | 每类配置有唯一所有者和生命周期 | P2 | 新增配置分层约定与 `core/config/README.md`，不建立大一统配置中心 |

---

# 5. Gap Analysis：当前高风险问题

## P0-01 TrainingLog Detail 横向读取

当前：

- `TrainingLogListView` 会按本人 / `view_all_traininglog` 过滤。
- `TrainingLogDetailView` 只有登录要求。
- 知道 PK 的任意已登录用户可以直接访问其他人的日志。

目标：

```text
没有 training.view_traininglog
    → 403

有 training.view_traininglog
    → 只能取得本人对象

有 training.view_all_traininglog
    → 可取得全部

superuser
    → 全部
```

详情对象必须通过与列表相同的 selector queryset 获取。

---

## P0-02 TrainingLog Update 横向修改

当前：

- `TrainingLogUpdateView` 仅要求 `training.change_traininglog`。
- 获取对象时没有 owner scope。
- 持有该 Permission 的用户可以通过 PK 修改其他人的日志。

目标：

```text
training.change_traininglog
    → 只能修改本人

training.change_all_traininglog
    → 可以修改全部

superuser
    → 全部
```

新增自定义 Django Permission：

```text
training.change_all_traininglog
```

不要为了兼容当前漏洞而把历史角色自动授予 `change_all_traininglog`。

---

## P0-03 WorldSkills Forum 附件绕过父对象可见性

当前 `ForumAttachmentContentView`：

- 只要求登录。
- 直接按附件 PK 查找。
- 没有先验证附件所属 Post / Topic 是否对当前用户可见。

目标：

```text
基础 forum view Permission
+
Post / Topic visibility selector
+
attachment belongs to visible parent
```

未知或不可见父对象一律 404/403，不能通过猜 PK 下载。

---

## P0-04 ArchiveAsset 通用下载绕过业务对象

当前：

- `ArchiveAssetListView` / Detail / Download 对所有已登录用户开放。
- ArchiveAsset 可通过 GenericRelation 绑定 TrainingLog、ExamPaper、Scoring 等业务对象。

目标：

1. 至少要求 `archives.view_archiveasset`。
2. 如果资产绑定业务对象，则同时继承父对象访问策略。
3. 未注册的 GenericForeignKey target 对非 superuser **fail closed**。
4. 通用 Archive 页面不能成为绕过父业务权限的后门。

---

## P0/P1-05 公共 Media 可能绕过页面权限

当前：

- `Meeting.file` 使用普通 `FileField`。
- `NoticeAttachment.file` 使用普通 `FileField`。
- `ConductRecord.attachment` 使用普通 `FileField`。
- 开发环境通过 `static(settings.MEDIA_URL, ...)` 提供 `MEDIA_ROOT`。
- 若生产 Web Server 也直接公开 `/media/`，即使 View 有权限，知道 URL 后仍可能绕过。

目标：

下列敏感业务文件迁移到 `PRIVATE_MEDIA_ROOT`，由 Django 权限 View 读取：

- 会议记录；
- 通知附件；
- 奖惩附件；
- 其他经审计判定为非公开的业务文件。

不要直接在模板使用这些敏感文件的 `.url`。

---

# 6. Gap Analysis：按 APP

## 6.1 accounts

### 当前

- Bundle → Django Permission 同步机制基本正确。
- `GroupProfile.selected_permission_bundles` / `UserProfile.selected_permission_bundles` 已存在。
- 默认 fixture 硬编码三种业务 Group。
- `accounts:home` 是登录落地页，当前展示所有可见 section card。
- `profile` 只有登录要求。
- User / Role 列表与菜单授权条件不一致。
- 新注册用户不加入默认 Group。

### 目标

- 保留 Bundle 同步实现。
- Group 完全由管理员自定义。
- `accounts:home` 作为**认证后的技术落地页**可以不要求业务 Permission，但不得泄露业务内容：
  - 只渲染当前用户实际有权限的 section；
  - 零权限时展示空状态：“当前账号尚未获得业务访问权限，请联系站点管理员。”
- “个人资料”使用：
  - GET：`accounts.view_userprofile`
  - POST：`accounts.change_userprofile`
  - Scope：仅本人；superuser 例外。
- 用户管理：`accounts.view_all_profiles`。
- 角色列表建议使用 Django 原生 `auth.view_group`。
- Django Admin 仍要求 `is_staff`，Admin 内具体操作继续由 Django Permission 决定。
- SiteConfig 增加可选默认注册 Group。

---

## 6.2 training

### 当前差距

- Cycle list/detail：登录即看。
- Log list：无 base `view_traininglog`；默认本人可看。
- Log detail：无 scope。
- Log update：有 change Permission 但无 scope。
- Monthly stats：
  - 登录即看；
  - 依赖固定“选手/教练” Group；
  - 按固定角色分类。
- `TrainingLog.Meta.permissions` 仍有：
  - `view_coach_traininglog`
  - `view_competitor_traininglog`
- `training.maintain_training` 太大。

### 目标

新增 / 保留：

```text
training.view_all_traininglog
training.change_all_traininglog
training.view_traininglog_statistics
training.export_traininglog_archive
```

删除旧角色型权限：

```text
training.view_coach_traininglog
training.view_competitor_traininglog
```

建立 `training/selectors.py`：

```text
get_training_logs_visible_to(user)
get_training_logs_editable_by(user)
```

Monthly Stats：

- 要求 `training.view_traininglog_statistics`。
- “应提交人员”不再通过 Group 名称判断。
- 以**显式拥有 `training.add_traininglog` 的 active users**作为业务集合。
- 不把 superuser 的隐式全权限自动解释为“应该提交训练日志的人”。
- 页面不再硬分“选手/教练”；如需显示角色，仅显示用户实际自定义 Group 名称，且 Group 只用于显示，不参与访问判断。

---

## 6.3 behaviors

### 当前差距

- `ConductRecord.student.limit_choices_to={'groups__name': GROUP_COMPETITOR}`。
- `can_view_all_conduct_records()` 把普通 `view/change/delete` 以及 review 都解释成“查看全部”。
- list / summary 未显式要求 view Permission。
- HTMX choices endpoint 只有登录保护。

### 目标

新增自定义 Django Permission：

```text
behaviors.be_conduct_subject
```

业务语义：

> 该用户可被选为奖惩记录对象。

这样不再依赖“选手”Group 名称。

Scope：

```text
view_conductrecord
    → 默认查看本人的奖惩记录

view_all_conduct_records
    → 查看全部

record_conduct
    → 可新增；默认可查看自己录入的记录 + 自己作为 subject 的记录

review_conduct_record
    → 审核能力
```

`view_conductrecord` / `change_conductrecord` / `delete_conductrecord` **不得自动提升为 all scope**。

HTMX `item_choices` / `severity_choices` 至少要求录入奖惩所需 Permission。

---

## 6.4 notices

### 当前

- selector 已按：
  - 发布者；
  - published；
  - `target_groups`
  做受众过滤。
- list/detail 登录即进入。
- delete 仅按 owner 判断，不要求 delete Permission。
- 附件为普通 Media File。

### 目标

- list/detail 先要求 `notices.view_notice`，再执行 target-group selector。
- 发布者 Bundle 包含 `view_notice + add_notice`，如发布者需要删除本人通知，再加入 `delete_notice`。
- delete：
  - 先要求 `delete_notice`；
  - 默认 Scope 为 `published_by=request.user`；
  - superuser bypass。
- `target_groups` 保留：
  - 这是管理员配置的“内容受众范围”，不是硬编码业务角色。
- 通知附件改 private storage，并通过父 Notice selector 下载。

---

## 6.5 meetings

### 当前

`can_view_meeting()` 等价于“只要登录”。

### 目标

- `can_view_meeting()`：
  - superuser → true
  - 否则必须 `meetings.view_meeting`
- list/detail/PDF preview/download 使用同一 checker。
- 上传 Bundle 至少包含 `view_meeting + add_meeting`。
- 删除必须有 `delete_meeting`。
- 文件改 private storage。

---

## 6.6 worldskills_forum

### 当前

- feed/topic/read 主要只有登录保护。
- unpublished/owner selector 已有较好的雏形。
- Topic/Post 编辑存在“owner/translator 直接可编辑”的逻辑，未统一要求 base `change_*`。
- attachment content 存在父对象绕过。

### 目标

- 所有读取先要求对应 `view_*` Permission。
- owner/translator scope 只能在 base Permission 通过后生效。
- `translate_forum` Bundle 加入翻译业务所需 view/add/change Permission。
- 如果需要非 superuser 全局维护论坛内容，新增一个**Django 自定义 Permission**用于扩大 scope，例如：

```text
worldskills_forum.change_all_forum_content
```

- attachment download 继承父 Post/Topic access。
- Workbench 的菜单和后端使用同一权限条件。

---

## 6.7 glossary

### 当前

这是当前项目最接近目标模式的 APP：

- Proposal 已有 base Permission + own selector。
- StudySession 已有 owner scope。
- 全部统计已有 `view_all_study_statistics`。

主要差距：

- browse / study / my stats 仅登录即可。

### 目标

- 增加明确的“词汇浏览/学习”业务 Bundle。
- browse 至少要求对应 `view_*`。
- 创建 StudySession / StudyAttempt 使用相应 Django Permission 或明确的自定义 Django Permission。
- StudySession 继续 own scope。
- `view_all_study_statistics` 继续作为 all-scope Permission。
- 保留现有 Proposal selector 设计作为其他 APP 的参考模式。

---

## 6.8 events

### 当前

所有 List/Detail 基本登录即看；写操作使用 add/change。

### 目标

读取入口增加对应 Django `view_*`。

建议把查看能力拆为：

```text
events.view_event_catalog
events.view_event_participants
```

原因：

- 赛事系列 / 级别 / Event / Module 属于业务目录。
- 参与人员包含人员数据，可独立授权。

注意：

`EventParticipant.Role` 中的 competitor / coach / staff / observer 是**某个事件中的参与身份字段**，不是 Django Group 授权角色。

**不要因为本次“删除硬编码角色权限”而删除 EventParticipant 的领域角色枚举。**

---

## 6.9 standards

### 当前

List/Detail 登录即看。

### 目标

- `standards.view_standard`
- `standards.maintain_standard`

所有读页面使用具体 Django `view_*`；维护 Bundle 组合 view + 当前实际支持的 add/change。

---

## 6.10 examcontent

### 当前

Paper / Requirement list/detail 登录即看。

### 目标

- 增加明确 read Bundle。
- read View 要求标准 Django view Permission。
- `maintain_examcontent` 包含 read + write。

本次权限重构**不额外引入试题发布生命周期**。

原因：

- deny-by-default 已能解决“所有登录用户都可读”的基础暴露。
- Draft / Published / Restricted 属于下一层业务生命周期设计，避免和本次授权架构重构混在一起。

如后续业务明确要求“同一角色只能看已发布试题”，再单独做 ADR / feature。

---

## 6.11 scoring

### 当前

- Scheme list/detail 登录即看。
- Scheme detail 可显示评分点、命令、期望结果和全部 participant。
- Participant detail 登录即看。

### 目标

至少拆分：

```text
scoring.view_schemes
scoring.view_own_results
scoring.view_all_results
scoring.maintain_scoring
```

新增 all-scope Permission：

```text
scoring.view_all_scoringparticipant
scoring.view_all_scoringresult
```

own participant selector：

```python
Q(user=user) | Q(event_participant__user=user)
```

外部 participant 在 own scope 中不可见。

Scheme detail 中的 participant table 必须经过 selector，不能因为能看 Scheme 就自动看到所有参评人员结果。

本次不强制加入“评分方案发布状态”；先完成 Permission 白名单和 own/all scope。

---

## 6.12 knowledge

### 当前

Evidence list/detail/unmapped 登录即看。

### 目标

- `knowledge.view_knowledge`
- `knowledge.maintain_knowledge`
- list/detail/unmapped 显式要求 `view_knowledgeevidence`。
- mapping 页面按 mapping Permission。
- maintain 包含必要 view + write。

---

## 6.13 archives

### 当前

所有登录用户可 list/detail/download。

### 目标

- `archives.view_archive`
- `archives.maintain_archive`
- 通用入口至少要求 `archives.view_archiveasset`。
- 对绑定 target 的 ArchiveAsset 再调用父对象 access policy。
- unknown target type fail closed。
- 不允许 ArchiveAsset 通用下载绕开 Training / Exam / Scoring 等权限。

---

## 6.14 notes

### 当前

- NoteRepo 有 `allowed_groups`。
- `can_access_note_repo()`：
  - 有 allowed_groups → 需属于其中一个 Group；
  - 没有 allowed_groups → 任意登录用户。

### 目标

增加 base Permission：

```text
notes.view_noterepo
```

访问逻辑：

```text
先有 notes.view_noterepo
+
再检查 NoteRepo.allowed_groups
```

`allowed_groups` 保留，因为这是每个 NoteRepo 的管理员可配置受众范围，并不依赖固定 Group 名称。

空 `allowed_groups` 的语义改为：

> 对所有拥有 `notes.view_noterepo` 的用户开放。

而不是：

> 对所有已登录用户开放。

详情 / print / assets 必须共用同一个 checker。

---

## 6.15 samba

### 当前

Samba account 页面只有全局登录保护；GET/POST 都可被任何登录用户使用。

### 目标

使用 Django 原生：

```text
samba.view_sambaoperation
samba.add_sambaoperation
```

例如：

```text
samba.manage_own_account
    ├─ samba.view_sambaoperation
    └─ samba.add_sambaoperation
```

GET：

- view permission；
- 只看本人 operation。

POST：

- add permission；
- target_user 固定本人。

---

# 7. 配置治理与 Permission Bundle Catalog

## 7.1 配置来源分层

统一的是配置的**所有者、生命周期和生效方式**，不是把所有配置物理搬进同一个目录。

| 配置类型 | 权威来源 | 修改者 / 生效方式 | 例子 |
|---|---|---|---|
| 部署、安全与路径配置 | `.env` + `tmsproject/settings.py` | 部署运维修改，重启生效 | 数据库、缓存、`PRIVATE_MEDIA_ROOT`、`NOTES_ROOT` |
| 跨 APP 静态 Catalog | `core/config/*.yml` | 受信任维护者或部署运维修改，检查、同步、部署后生效 | navigation、Permission Bundle |
| 站点在线设置 | `SiteConfig` | 有权限的站点管理员通过 Django Admin 修改 | 站点资料、新注册用户默认 Group |
| APP 业务配置 / 主数据 | 所属 APP model | 对应业务管理员通过应用或 Admin 修改 | NoteRepo、论坛来源身份、倒计时事件 |
| 初始化数据 | `*/fixtures/` | 安装 / 演示时显式加载 | 默认站点资料；不得伪装成运行时配置 |
| 代码不变量 | Python constants / model choices | 随代码发布 | 上传扩展名上限、稳定枚举 |

新增：

```text
core/config/README.md
```

用于记录以上边界。不要建立把所有 APP 配置集中搬入 `core` 的“大一统配置中心”。

## 7.2 YAML Catalog

Permission Bundle 定义迁移到：

```text
core/config/permission_bundles.yml
```

它是受版本控制、随部署生效的**静态安全策略 Catalog**，不是 Django Admin 可在线编辑的 SiteConfig，也不是新的数据库 Bundle model。

Catalog 使用带版本的扁平结构：

```yaml
version: 1
bundles:
  - code: training.submit_logs
    name: 训练日志｜提交和管理本人记录
    description: 提交、查看和修改自己的训练日志。
    permissions:
      - training.view_traininglog
      - training.add_traininglog
      - training.change_traininglog
```

规则：

1. Bundle 只能直接引用 `app_label.codename`。
2. 不支持 Bundle 嵌套、继承、条件表达式或 policy DSL。
3. YAML 列表顺序就是 Django Admin 的展示顺序。
4. code 是稳定配置标识；name / description 使用中文业务语言。
5. Django Admin 只选择 Bundle，不新增、删除或修改 Bundle 定义。
6. 不支持运行中热编辑或热加载；Catalog 只在检查、命令执行和进程启动时加载并缓存。

## 7.3 严格校验与失败语义

新增：

```text
core/permissions/registry.py
core/permissions/checks.py
```

Registry / system check 必须验证 Catalog 本身：

1. YAML duplicate key、schema version、字段类型和未知字段。
2. Bundle code 与 name 全局唯一。
3. code 满足稳定命名格式；Bundle 内 Permission 不重复且非空。
4. 每个 Permission 使用 `app_label.codename`。
5. Permission 在已安装 model 的默认 / 自定义权限声明中存在且唯一；缺失或模糊时失败。
6. 不再使用“未知 code 静默丢弃”“重复 code 后项覆盖”或“Permission 缺失直接跳过”的行为。

静态检查应尽量基于 Django app registry / model metadata，不依赖未完成的数据库迁移；数据库中的 ContentType / Permission 解析以及 Profile 中未知 Bundle code 的检查，在 migrate/post_migrate 后由 reconciliation 完成。

低层 YAML 读取如需复用，只抽取 duplicate-key、安全解析和错误定位；navigation 与 permission registry 继续各自拥有领域 schema 校验，不建立通用配置 DSL。

## 7.4 模块职责与授权配置来源

推荐边界：

```text
core/config/permission_bundles.yml
    纯声明

core/permissions/registry.py
    加载、校验、查找、批量解析 Bundle → Django Permission

core/permissions/checks.py
    Django system checks

accounts/services/permission_assignments.py
    保存 Group/User 的 Bundle 与 explicit Permission 选择
    事务化物化原生 Permission M2M

accounts/services/groups.py
    GroupProfile / technical codename 生命周期
```

`GroupProfile.codename` 仍被 Samba 等技术集成使用，可以保留；必须明确它不是业务授权角色标识。

在 `GroupProfile` 与 `UserProfile` 分别增加：

```text
explicit_permissions -> auth.Permission
    ManyToManyField(blank=True, related_name="+")
```

授权配置的唯一计算式为：

```text
native Django Permission projection
=
expand(selected_permission_bundles)
∪
explicit_permissions
```

原生 `Group.permissions` / `User.user_permissions` 不再作为管理员输入来源。Admin 隐藏原始投影字段，只显示“业务权限包”和“额外原生权限”；shell 或其他入口直接修改原生 M2M 属于 drift。

Assignment service 必须使用 `transaction.atomic()`，必要时锁定对应 Profile，保证 Bundle JSON、explicit M2M 与 native M2M 同一事务提交。读 Admin 表单不应为了展示 Bundle 而隐式创建 Profile；Profile 生命周期应在明确的创建 / 保存边界处理。

## 7.5 Reconciliation 与 Catalog 演进

新增管理命令：

```text
uv run manage.py reconcile_permission_assignments
uv run manage.py reconcile_permission_assignments --apply
```

默认只 dry-run；`--apply` 才写库。命令必须：

1. 全量检查 Group / User 的 selected Bundle code。
2. 批量解析 Catalog 引用并报告缺失 / 模糊 Permission。
3. 计算 desired projection 与当前 native M2M 的差异。
4. 明确输出将新增、撤销和保持的授权统计，不输出敏感用户资料。
5. `--apply` 在事务中重建 native M2M。
6. 从 Bundle 删除的 Permission 必须撤销；只有同时存在于 `explicit_permissions` 时才保留。
7. 未知 Bundle code、无效 Catalog 或无法完成的对象使命令失败，不允许部分成功。

部署期 Catalog 变更流程：

```text
修改 YAML
→ Django system check
→ migrate / post_migrate
→ reconciliation dry-run
→ reconciliation --apply
→ 重启 / 开放流量
```

Bundle code 视为稳定标识：

- 可以在同一 code 下调整 Permission 组成，并通过 reconciliation 确定授权 / 撤权。
- 被 Group/User 引用的 code 不允许直接删除或重命名。
- 必须改名时采用两次部署：先新增新 code 并重新分配，再删除已无人引用的旧 code。
- 不提供 legacy alias，也不自动猜测 code 迁移目标。

## 7.6 推荐 Bundle Catalog

以下是重构后的第一版业务 Bundle 命名。Codex 实施时应按当前真实页面操作核对底层 Permission，不要因为模型有默认 delete Permission 就自动把未开放的删除能力塞进 Bundle。

### accounts

```text
accounts.manage_own_profile
accounts.view_all_profiles
```

### notices

```text
notices.view_notices
notices.publish_notice
```

### meetings

```text
meetings.view_meetings
meetings.upload_meeting
meetings.delete_meeting
```

### training

```text
training.view_cycles
training.manage_cycles
training.submit_logs
training.view_all_logs
training.manage_all_logs
training.view_statistics
training.export_logs
```

### behaviors

```text
behaviors.conduct_subject
behaviors.record_conduct
behaviors.review_conduct
behaviors.view_all_conduct_records
```

### standards

```text
standards.view_standard
standards.maintain_standard
```

### events

```text
events.view_event_catalog
events.view_event_participants
events.maintain_event
```

### examcontent

```text
examcontent.view_examcontent
examcontent.maintain_examcontent
```

### scoring

```text
scoring.view_schemes
scoring.view_own_results
scoring.view_all_results
scoring.maintain_scoring
```

### knowledge

```text
knowledge.view_knowledge
knowledge.maintain_knowledge
```

### archives

```text
archives.view_archive
archives.maintain_archive
```

### worldskills_forum

```text
worldskills_forum.view_forum
worldskills_forum.translate_forum
worldskills_forum.manage_forum
```

### glossary

```text
glossary.study_glossary
glossary.contribute_entries
glossary.manage_glossaries
```

### notes

```text
notes.view_notes
```

### samba

```text
samba.manage_own_account
```

---

# 8. 新增 / 删除的 Django 自定义 Permission

## 8.1 新增

最低需要：

```text
training.change_all_traininglog
training.view_traininglog_statistics

behaviors.be_conduct_subject

scoring.view_all_scoringparticipant
scoring.view_all_scoringresult
```

如果实现论坛非 superuser 的全局管理能力：

```text
worldskills_forum.change_all_forum_content
```

原则：

- 只有 standard Permission 无法表达 Scope 扩展时才新增。
- 不为每个模型机械生成 `view_own/change_own/delete_own`。
- base Permission 默认就是 normal / own scope。
- 当前没有业务入口的 `delete_all_*` 不要预先创建。

---

## 8.2 删除

从 `TrainingLog.Meta.permissions` 移除：

```text
view_coach_traininglog
view_competitor_traininglog
```

并安全清理数据库中遗留 Permission 记录及 Group/User M2M 关联。

---

# 9. 授权配置硬切换与默认数据策略

本次处于试运行阶段，明确**不兼容旧授权配置数据**。不保留旧 Bundle code alias、JSON rewrite、权限反推或 backfill；但“不兼容旧授权配置”不等于删除业务数据、Group 业务关系或 Django migration 历史。

## 9.1 不再创建内置业务 Group

`accounts/fixtures/accounts/default.yaml` 当前只包含“教练 / 选手 / 班务”及其旧授权配置，应删除该 fixture，并同步移除 README / 安装脚本中的 loaddata 引用。

新安装环境不再自动创建：

```text
教练
选手
班务
```

硬切换不根据 Group.name 或 codename 查找并删除已有 Group。原因：

- Group 可能仍被通知受众、NoteRepo、Samba 或其他业务关系引用。
- 在新架构下，即使名称碰巧是“教练”，也只是普通自定义 Group。
- 清空授权配置即可消除旧角色带来的能力，不需要破坏 Group、membership 和领域关系。

## 9.2 一次性授权配置硬切换

新增一次性、forward-only、明确标注不可恢复的 data migration。执行前必须确认至少有一个可登录 superuser；迁移后除 superuser 的 Django 隐式全权限外，普通用户和 Group 均从零授权重新配置。

迁移执行：

1. 清空 `GroupProfile.selected_permission_bundles`。
2. 清空 `UserProfile.selected_permission_bundles`。
3. 清空 Group/User 新增的 `explicit_permissions`。
4. 清空原生 `Group.permissions` / `User.user_permissions` 投影。
5. 删除已从 model Meta 移除的 role-specific `auth_permission` 行及关联：
   ```text
   training.view_coach_traininglog
   training.view_competitor_traininglog
   ```
6. 不按 Group 名称、显示名称或 codename 推断任何新授权。

明确保留：

- User；
- Group；
- Group membership；
- GroupProfile 的技术 codename 与 Samba 映射；
- 通知 / Notes 等对 Group 的业务关联；
- 全部业务记录和业务文件；
- 已提交的 Django migration 历史。

本次不重写：

```text
training.maintain_training
→
training.view_cycles / training.manage_cycles / ...
```

管理员必须在新 Catalog 上重新分配 Bundle；不要把历史越权行为或旧 Bundle 粒度带入新架构。

## 9.3 删除旧兼容代码

删除：

```text
accounts/management/commands/backfill_permission_bundles.py
get_permission_bundle_permission_map()
infer_permission_bundle_codes_from_permissions()
相关 services __init__ 导出
全部 backfill / legacy code rewrite tests
```

同时检查并删除旧测试用户脚本、README 或 fixture 中对固定角色和已废弃 Bundle code 的引用。不要为了旧试运行数据库保留双写、fallback、alias 或兼容分支。

## 9.4 未来 Catalog 变更不走旧数据兼容

硬切换后，Bundle code 按第 7.5 节的稳定标识规则演进。未来调整 Bundle 权限组成走 reconciliation；rename/delete 走显式两阶段重新分配，不新增自动映射或反推逻辑。

---

# 10. SiteConfig 与新用户默认角色

在 `core.models.SiteConfig` 增加：

```python
default_registration_group = models.ForeignKey(
    Group,
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    ...
)
```

建议管理员显示名称：

> 新注册用户默认角色

规则：

```text
配置了 Group
    → 注册成功后加入该 Group

未配置
    → 不加入任何 Group
    → 零业务权限
```

禁止：

```python
Group.objects.get(name="游客")
```

Group 重命名不应影响默认角色关联。

当前注册流程仍然可以保持“注册后 inactive，等待管理员启用”；默认 Group 赋予和 `is_active` 是两个独立概念。

同时修复 `SiteConfig` 的单例与缓存边界：

1. `get_solo()`、Admin changelist redirect 和编辑入口必须指向同一个固定对象，不再混用 `first()` 与 `id=1`。
2. 无需引入第三方 singleton package；使用项目内明确的固定主键 / 唯一对象约束。
3. `SiteConfig` 保存或删除后立即失效 `site_config_solo` cache。
4. fixture 默认值与 `get_solo()` fallback 不再维护两份互相漂移的站点资料；确定一个初始化来源。
5. 增加测试覆盖重复创建防护、Admin 编辑对象一致性、保存 / 删除缓存失效，以及默认 Group 被删除后的 `SET_NULL`。

---

# 11. Navigation Fail-Closed 设计

保留当前 navigation YAML 体系，但改变规则。

## 11.1 叶子项必须显式声明一种访问模式

一个带 URL 的 leaf item 必须满足以下之一：

### Public

```yaml
login_required: false
```

例如：

- 首页
- About
- Countdown
- robots.txt 不需要菜单

### Django Permission

```yaml
permissions:
  - training.view_traininglog
```

### Staff-only technical entry

```yaml
staff_required: true
```

只用于 Django Admin 等技术入口。

### Superuser-only

```yaml
superuser_required: true
```

---

## 11.2 禁止当前模式

禁止：

```yaml
- key: training_logs
  url_name: training:log_list
```

并默认解释成：

> 登录用户都可见。

新的解释应该是：

> 业务 leaf 没有明确授权条件 = 配置错误 / 不可见。

Parent/container 可以不写 Permission，它只在至少一个 child 可见时出现。

---

## 11.3 导航校验

增加测试或启动时配置校验：

- URL leaf 必须有明确访问条件。
- Public item 必须显式 `login_required: false`。
- `permissions` 中的每个 Permission 必须合法。
- `staff_required` 不可替代业务 Permission。
- 不允许出现基于固定 Group name/codename 的导航规则。

---

# 12. 文件授权重构

这是本次 Plan 的必要范围，不作为后续优化。

## 12.1 使用 `PrivateMediaStorage`

项目已有：

```text
settings.PRIVATE_MEDIA_ROOT
core.uploads.PrivateMediaStorage
```

优先复用。

路径配置必须只有一个权威来源：

```python
PRIVATE_MEDIA_ROOT = env.path(...)
NOTES_ROOT = env.path("NOTES_ROOT", default=PRIVATE_MEDIA_ROOT / "notes")
```

删除 `core.constants.PRIVATE_MEDIA_ROOT` 及由它推导的绝对 `NOTES_ROOT` / archive 根路径。上传路径常量只保存 storage 内的相对子目录；代码通过 `settings.PRIVATE_MEDIA_ROOT`、`settings.NOTES_ROOT` 或相应 Storage 访问实际根目录。

Notes 改用 `settings.NOTES_ROOT`，但必须保留现有安全不变量：后台只存 relative path，正文、附件和相对链接解析都严格限制在配置根目录 / 选定 NoteRepo 根目录内，不得因配置来源调整而放宽路径边界。

迁移：

- Meeting.file
- NoticeAttachment.file
- ConductRecord.attachment

以及审计后确认需要权限保护的其他上传文件。

---

## 12.2 不直接输出 `.url`

敏感文件模板必须链接到：

```text
permission checked download / preview view
```

例如：

```text
meetings:meeting_pdf_inline
notices:attachment_download
behaviors:attachment_download
```

下载 View：

1. 检查 base Permission。
2. 获取父业务对象的 scoped queryset。
3. 再取得附件。
4. `FileResponse` 返回。
5. 不允许根据文件路径直接访问。

---

## 12.3 现有文件迁移

不要在 schema migration 中移动大量实际文件。

第 9 节“不兼容旧授权配置”只适用于权限和角色授权元数据，**不适用于业务文件**。会议记录、通知附件、奖惩附件及其他业务文件仍必须保留并安全迁移。

实现一个**幂等 management command**，例如：

```text
manage.py migrate_private_media
manage.py migrate_private_media --apply
```

要求：

1. 识别需迁移的 Meeting / NoticeAttachment / ConductRecord 文件。
2. 从旧 storage 读取。
3. 写入新 private storage。
4. 校验文件存在，最好校验 size / hash。
5. 成功后才删除旧文件。
6. 已迁移文件可安全重复运行。
7. 默认 dry-run，仅 `--apply` 执行迁移。
8. 输出迁移 / 跳过 / 缺失 / 失败统计。

部署文档明确迁移顺序。

---

# 13. 详细 Codex 执行阶段

---

## Phase 0 — 建立安全基线

### 任务

1. 确认当前工作基于最新 `develop`。
2. 记录执行开始时 HEAD；若已不同于本 Plan 的基线 SHA，先 review 与权限相关的 diff。
3. 运行现有测试，记录 baseline failures：
   ```bash
   uv run pytest
   uv run ruff check .
   uv run manage.py check
   uv run manage.py makemigrations --check --dry-run
   ```
4. 不把历史已有失败误认为本次引入。
5. 搜索所有以下模式：
   ```text
   GROUP_COACH
   GROUP_COMPETITOR
   GROUP_ASSISTANT
   SPECIAL_GROUPS
   CrossGroupAccessMixin
   groups__name=
   groups.filter(name=
   Group.objects.get(name=
   GroupProfile.codename
   selected_permission_bundles
   backfill_permission_bundles
   Group.permissions
   user_permissions
   is_staff
   LoginRequiredMixin
   @login_required
   .file.url
   .attachment.url
   core.constants.PRIVATE_MEDIA_ROOT
   NOTES_ROOT
   ```
6. 对 `GroupProfile.codename` 的命中逐个判断：
   - 如果只是显示/技术标识，可保留；
   - 如果决定业务权限，必须移除。

### 产出

- 权限重构影响文件清单。
- 无遗漏的 role-name 授权引用清单。
- native Permission M2M 的全部写入口与 drift 风险清单。
- 配置来源分类及重复路径 / 重复默认值清单。

---

## Phase 1 — 写入架构决策和项目规范

### 新建

```text
docs/adr/0003-permission-authorization-architecture.md
```

ADR 必须记录本 Plan 第 2 节的定稿原则。

同时记录：

- Permission Bundle Catalog 是部署期静态 YAML，不是 Admin 在线模型；
- 配置来源分为部署设置、静态 Catalog、数据库在线设置、APP 业务配置、fixtures 与代码不变量；
- selected Bundle + explicit Permission 是配置来源，native M2M 是物化投影；
- 本次采用授权配置硬切换，不迁移旧 Bundle code；
- Group/codename 可用于显示或技术集成，但不用于业务授权。

### 修改

```text
AGENTS.md
.codex/skills/tms-dev/SKILL.md
core/config/README.md
```

重点删除/改写：

- “稳定角色身份优先 GroupProfile.codename”的授权建议。
- “跨角色访问”的旧语义。

改成：

```text
Group 名称/codename 不用于业务授权。
业务访问只检查 Django Permission。
对象范围统一由 selector/policy 收窄。
```

`core/config/README.md` 按第 7.1 节记录配置所有权和生效方式，并明确 fixture 不是运行时配置。

如果此前另一个重构计划正在删除 `tms-dev` skill：

- 不要与该计划冲突；
- 若执行时 skill 已被删除，只更新 `AGENTS.md`；
- ADR 仍然保留。

---

## Phase 2 — 重构 Permission Bundle Registry

### 新增 / 修改

```text
core/config/permission_bundles.yml
core/permissions/bundles.py（迁移后删除）
core/permissions/registry.py
core/permissions/checks.py
core/permissions/__init__.py
accounts/models.py
accounts/services/permission_bundles.py（拆分后删除）
accounts/services/permission_assignments.py
accounts/services/groups.py
accounts/admin_forms.py
accounts/admin.py
accounts/tables.py
accounts/management/commands/reconcile_permission_assignments.py
相关 migrations / tests
```

### 要求

1. 把 Python catalog 迁移为第 7.2 节的 versioned、flat YAML。
2. Registry 严格校验 schema、duplicate key、code/name、Permission 格式 / 存在性 / 唯一性；批量解析，禁止 N+1 `.first()` 与静默跳过。
3. Bundle code → Permission 展开只在 `core.permissions`；Group/User 配置写操作只在 `accounts.services.permission_assignments`。
4. `GroupProfile` / `UserProfile` 增加独立 `explicit_permissions` M2M。
5. native M2M 只按 `expand(selected bundles) ∪ explicit_permissions` 生成。
6. Admin 隐藏原始 native M2M 输入，分区展示“业务权限包”和“高级：额外原生权限”。
7. assignment service 使用事务，不能出现 JSON 成功而 M2M 失败的部分状态。
8. 表格 / Admin 不能在模块 import 时形成无法随进程重启刷新的不受控快照；统一从 registry 读取稳定视图。
9. 新增默认 dry-run、显式 `--apply` 的 reconciliation 命令，并测试授权、撤权、explicit overlap、drift 修复和失败回滚。
10. 删除读路径隐式 `get_or_create` Profile；GroupProfile technical codename 生命周期移至明确 service。
11. 不新增 Bundle model / permission backend，不支持在线编辑、嵌套 Bundle 或热加载。

---

## Phase 3 — 权限定义与授权配置硬切换

### 修改

涉及：

```text
training/models.py
behaviors/models.py
scoring/models.py
worldskills_forum/models.py（如果加入 change_all）
core/config/permission_bundles.yml
accounts/models.py
accounts/fixtures/accounts/default.yaml（删除）
accounts/management/commands/backfill_permission_bundles.py（删除）
README.md
scripts/create_test_users.py（按实际引用删除或重写）
```

### 新 migration

按各 APP migration 序列创建真实迁移文件，不手写虚假编号。

### 要求

1. 新增本 Plan 第 8 节 Permission。
2. 删除 training role-specific Permission。
3. 创建第 9.2 节的一次性 forward-only data migration，清空旧 selected Bundle、explicit source 与 native M2M。
4. 删除 obsolete role-specific `auth_permission` 记录及关联。
5. 不删除 User、Group、membership、GroupProfile technical codename、业务关系或业务数据。
6. 不根据“教练/选手/班务”名称迁移或删除数据。
7. 不做 selected bundle code JSON rewrite，不保留 alias / fallback / backfill。
8. 删除反向推断 service、backfill command、旧 fixture、旧脚本引用与对应测试。
9. 新安装与已有试运行库迁移后的授权配置均为空，由 superuser 按新 Catalog 重新分配。
10. 测试硬切换范围、不可误删业务关系、obsolete Permission 清理和 fresh-install 一致性。

---

## Phase 4 — 移除固定授权角色

### 修改 / 删除授权引用

```text
core/constants.py
core/utils/mixins.py
accounts/services/users.py
training/views.py
behaviors/models.py
behaviors/forms.py（按实际代码）
behaviors/admin.py（按实际代码）
其他 Phase 0 grep 命中文件
```

### 要求

- 删除授权用途的：
  - GROUP_COACH
  - GROUP_COMPETITOR
  - GROUP_ASSISTANT
  - SPECIAL_GROUPS
- 删除 / 停用 `CrossGroupAccessMixin`。
- 业务代码不得根据 Group.name/codename 判断权限。
- 任意 Group 的名称都能正常显示。
- role badge 使用统一样式；不要内置“教练/选手/班务”的特殊色彩作为身份逻辑。
- `is_staff` / `is_superuser` 如显示，作为系统标记单独展示。

### 不要误删

```text
EventParticipant.Role
```

它是事件内部参与身份，不是认证角色。

---

## Phase 5 — 建立 Scope Selector 约定

### 新增 / 整理

至少：

```text
training/selectors.py
scoring/selectors.py
archives/permissions.py 或 archives/access.py
```

继续复用：

```text
behaviors/selectors.py
worldskills_forum/selectors.py
```

### 建议增加通用 helper

在 `core/permissions/` 中增加一个小型查询 helper：

```python
get_users_with_explicit_permission(permission_name, queryset=None)
```

用途：

- Training “应提交日志的人员”；
- Behaviors “可作为奖惩对象的人员”。

它必须查询：

```text
user.user_permissions
OR
user.groups.permissions
```

并 `.distinct()`。

**不要**调用 `user.has_perm()` 去建立“人员业务集合”，因为 superuser 的隐式全权限不应该让他自动成为“训练日志应提交人员”或“奖惩对象”。

---

## Phase 6 — 修复 P0 授权漏洞

按顺序实施并先写测试：

### 6.1 TrainingLog

- list/detail/update 共用 selector。
- base view/change Permission 必须存在。
- own/all scope 正确。
- PK tampering 测试。

### 6.2 Forum Attachment

- attachment 先经过 parent visibility。
- 未授权 PK 返回 404/403。
- 测试 unpublished topic 附件。

### 6.3 ArchiveAsset

- base view permission。
- bound target inheritance。
- unknown target fail closed。
- 下载和详情一致。

### 6.4 Sensitive Media

- 先增加受保护 View + template link。
- 再切换 private storage。
- 把路径权威统一到 `settings.PRIVATE_MEDIA_ROOT` / `settings.NOTES_ROOT`，删除 `core.constants` 中重复的绝对根路径。
- 提供 migration command。
- 测试匿名 / 无权限 / 有权限 / 非目标受众。

---

## Phase 7 — 全站业务 GET 白名单化

逐 APP 修改 Login-only read views。

执行顺序建议：

1. accounts self-service / samba
2. notices
3. meetings
4. behaviors
5. training
6. worldskills_forum
7. glossary
8. events
9. standards
10. examcontent
11. scoring
12. knowledge
13. archives
14. notes

每个 View 都回答：

```text
这个 GET 要求哪个 Django Permission？
这个对象的默认 Scope 是什么？
是否存在 all-scope Permission？
是否有父对象/受众范围？
```

原则：

```text
LoginRequiredMixin
≠
业务授权
```

全局 LoginRequiredMiddleware 继续保留。

少数公开页面继续通过 `login_not_required()` 明确 opt-out。

---

## Phase 8 — Navigation Fail-Closed

### 修改

```text
core/navigation.py
core/config/navigation.yml
core/permissions/checks.py 或相邻 config checks
core/tests.py
相关 menu tag tests
```

### 要求

1. 所有业务 leaf menu 明确 `permissions`。
2. 用户管理：
   ```text
   accounts.view_all_profiles
   ```
3. 角色列表：
   ```text
   auth.view_group
   ```
4. Django Admin：
   ```text
   staff_required: true
   ```
5. superuser-only technical action 保留 `superuser_required`。
6. public home/about/countdown 保留明确 public 配置。
7. parent 无 visible child 自动隐藏。
8. 零业务权限用户：
   - 不看到任何业务 section/menu；
   - 仍可 logout；
   - 登录 landing 显示明确空状态。
9. YAML 使用与 Permission Catalog 一致的 strict duplicate-key / error-location 基础读取能力，但 navigation schema 仍由 navigation 模块自己校验。
10. 配置缺失、重复 key、非法 access mode 或无效 Permission 必须 fail loudly；不得再以空配置或 fail-open 行为掩盖错误。

增加测试：

```text
menu permission == backend permission
```

特别验证：

- staff 但没有业务 Permission：
  - Django Admin 技术入口可见；
  - TMS 业务菜单不可凭 staff 自动出现。
- nonstaff 但有 TMS Permission：
  - 对应 TMS 菜单和页面可访问；
  - Django Admin 不可进入。

---

## Phase 9 — 用户注册默认 Group

### 修改

```text
core/models.py
core/admin.py
accounts/views.py 或新增 accounts/services/registration.py
core/fixtures/core/default.yaml
相关 tests
```

### 推荐结构

把注册后的初始化动作放到 service，而不是继续堆在 View：

```python
apply_default_registration_group(user)
```

### 测试

- SiteConfig 无默认 Group → 用户无 Group。
- 配置默认 Group → 新用户加入该 Group。
- Group 重命名 → 关联不受影响。
- Group 删除 → SiteConfig SET_NULL。
- 默认 Group 的 Permission 正常通过 Django 原生 group permission 获得。
- inactive 注册行为保持原样。
- `SiteConfig.get_solo()` 与 Admin 始终操作同一固定对象。
- 阻止第二条 SiteConfig 记录造成读取漂移。
- 保存 / 删除 SiteConfig 后缓存立即失效。
- fixture 与 `get_solo()` 不再维护冲突的默认站点资料。

---

## Phase 10 — Template / Table / HTMX 权限一致性

检查：

```text
templates/
*/tables.py
HTMX endpoints
```

规则：

1. 按钮只根据 Django `perms` / server context 显示。
2. 不根据 Group 名称显示按钮。
3. 隐藏按钮不替代后端 Permission。
4. django-tables2 操作列可根据 request user 隐藏，但对应 URL 仍必须后端授权。
5. HTMX 请求与普通请求使用相同 permission / selector。
6. Alpine.js 只做交互状态，不做安全授权。
7. Tailwind / DaisyUI / Iconify class 保持静态完整字符串，不动态拼接 class name。

如果本次模板修改增加 Tailwind/Iconify class：

```bash
npm run build:css
```

---

## Phase 11 — 管理员权限配置 UX

目标：

站点管理员首先看到的是业务能力，而不是几十个 Django raw permissions。

### Group Admin

建议 fieldset：

```text
基本信息
业务权限包
高级：额外原生 Django 权限
```

### User Admin

同样：

```text
角色（Groups）
用户直接业务权限包
高级：额外原生 Django 权限
```

要求：

- Bundle 名称和 description 使用中文业务语言。
- 每个 Bundle 可展开/帮助文本显示底层 Permission 清单。
- Bundle code/name 唯一性由 registry 检查，Admin 不提供 Catalog 编辑入口。
- Bundle 改动保存后原生 Permission 立即同步。
- “额外原生权限”实际编辑 Profile 的 `explicit_permissions`，不再通过 native M2M 差集反推。
- 原始 `Group.permissions` / `User.user_permissions` 投影字段隐藏或只读，不允许绕过 assignment service 写入。
- 显式 extra Permission 不因 Bundle 重新同步而丢失；从 Bundle 移除且未显式选择的 Permission 必须撤销。
- Admin 保存失败时 Bundle、explicit 与 native projection 全部回滚。

---

# 14. 测试矩阵

为每个有权限边界的核心入口，至少覆盖：

| 用户类型 | 预期 |
|---|---|
| anonymous | 业务页面重定向登录；public 页面正常 |
| authenticated + zero Permission | 403 / empty scoped result；业务菜单不可见 |
| direct Permission | 正常获得能力 |
| Permission via arbitrary Group | 正常获得能力 |
| multiple Groups | Django 原生合并权限 |
| staff without business Permission | 不获得 TMS 业务访问 |
| nonstaff with business Permission | 可访问对应 TMS 业务页面 |
| superuser | 全部放行 |
| owner + base Permission | 访问自己的对象 |
| non-owner + base Permission | 不能通过 PK 访问他人对象 |
| user + `*_all` Permission | 可访问全部范围 |
| parent inaccessible + attachment URL | 不可下载 |
| target group mismatch | 通知/笔记等不可访问 |
| HTMX direct request without Permission | 与普通 HTTP 一样拒绝 |
| Bundle Permission removed | reconciliation 撤销 native grant，除非 explicit source 仍保留 |
| invalid / duplicate YAML | system check 与 reconciliation 失败，不发生部分写入 |
| unknown selected Bundle code | 列出受影响对象并失败，不静默丢弃 |
| native M2M drift | dry-run 报告；`--apply` 恢复为 bundles ∪ explicit |
| hard-cutover existing DB | 授权配置清空，User/Group/membership/业务关系保持 |

---

# 15. 重点回归测试

必须至少明确覆盖：

## Permission Catalog / Assignment

```text
versioned flat YAML loads in declared order
duplicate YAML key rejected
duplicate bundle code/name rejected
invalid or ambiguous app_label.codename rejected
unknown selected bundle code rejected
bundle expansion is batched and deterministic
bundle permission addition is granted after reconciliation
bundle permission removal is revoked after reconciliation
explicit permission survives bundle removal
native M2M direct drift is reported and repaired
assignment JSON + explicit M2M + native projection commit atomically
reconciliation dry-run performs no writes
reconciliation failure rolls back every object
catalog is not editable through Django Admin
```

## Hard Cutover / Configuration

```text
legacy bundle selections are cleared, not rewritten
legacy backfill/alias entry points no longer exist
obsolete role-specific Permission rows are removed
users, groups, memberships and group-targeted business relations survive
fresh install creates no coach/competitor/assistant groups
SiteConfig is a true single logical object
SiteConfig save/delete invalidates cache
settings.NOTES_ROOT honors environment override
Notes path escape protections remain unchanged
```

## Training

```text
view own
cannot view other's PK
view_all can view other
change own
cannot change other's PK
change_all can change other
monthly stats requires permission
```

## Forum

```text
no view permission → feed/topic denied
published visibility preserved
own unpublished topic requires base permission
attachment cannot bypass parent
```

## Archives

```text
no view archive → denied
unbound asset with view permission → allowed
bound TrainingLog asset follows TrainingLog scope
unknown bound target → denied
```

## Behaviors

```text
subject user selected by be_conduct_subject Permission
no Group name dependency
view own only
view_all expands
normal change/delete does not imply view_all
```

## Notes

```text
no notes.view_noterepo → no repos
base permission + empty allowed_groups → allowed
base permission + matching arbitrary group → allowed
base permission + group mismatch → denied
asset endpoint same behavior
```

## Navigation

```text
zero permission user sees no business sections
permission grant causes exact entry to appear
permission revoke hides it
staff alone does not expose business entries
superuser sees all applicable entries
```

## Files

```text
direct protected download without login → denied
logged-in no permission → denied
permission but outside object scope → denied
authorized → FileResponse
```

---

# 16. Migration / Deployment Safety

本次包含**明确不可恢复的旧授权配置硬切换**和**必须可恢复的业务文件迁移**。两者不能混用同一安全语义。

## 数据库

首次硬切换：

1. 进入维护窗口，记录执行 HEAD，并确认至少一个可登录 superuser。
2. 备份数据库用于操作失误恢复；Plan 不提供旧授权语义兼容。
3. 部署 `permission_bundles.yml`、registry、assignment source 与新 Permission 定义。
4. 运行静态 Django system checks。
5. 运行 migrate / post_migrate：
   - 创建 `explicit_permissions` schema；
   - 创建新的自定义 Permission；
   - 执行一次性 forward-only 授权配置清空；
   - 清理 obsolete role-specific Permission。
6. 验证 User、Group、membership 和业务关系数量未被改变。
7. 由 superuser 在新 Catalog 上重新分配业务 Bundle / explicit Permission。
8. 运行 reconciliation dry-run，再运行 `--apply`。
9. 验证零权限用户、代表性业务角色、staff 与 superuser 场景后开放流量。

禁止：

- Bundle JSON rewrite；
- 按 Group 名称猜测新授权；
- legacy alias / fallback / backfill；
- 删除 migration 历史；
- 把未纳入硬切换范围的 Group 或业务关系顺带删除。

后续 Catalog 变更：

```text
修改 YAML
→ system check
→ migrate / post_migrate（若 Permission schema 有变化）
→ reconciliation dry-run
→ reconciliation --apply
→ 重启 / 开放流量
```

任何检查或 reconciliation 失败都必须阻止部署，不允许部分 Group/User 已更新而其他对象保留旧投影。

## 文件

敏感媒体迁移必须：

1. dry-run；
2. copy；
3. verify；
4. switch / confirm；
5. 最后才删除旧文件。

不要在 migration 文件里直接移动大批真实文件。

业务文件不属于“可直接丢弃的旧授权配置数据”；即使数据库授权采用硬切换，文件迁移仍必须 dry-run、copy、verify、switch 后才清理旧副本。

---

# 17. Documentation 更新

实施结束后同步：

```text
AGENTS.md
docs/adr/0003-permission-authorization-architecture.md
docs/user-manual/
core/config/README.md
README.md
```

建议新增用户手册：

```text
docs/user-manual/permission-management.md
```

至少解释：

- 什么是角色（Group）；
- 什么是业务权限包；
- 用户可以同时属于多个角色；
- 如何创建一个“游客/基础用户”角色；
- 如何设置新注册用户默认角色；
- 如何把 Bundle 分配给 Group；
- 用户直接 Bundle 的适用场景；
- raw Django Permission 属于高级配置；
- `is_staff` 与 TMS 业务管理员的区别；
- `is_superuser` 的含义。

同时在 ADR / 配置 README / 部署文档说明：

- 谁可以修改 `permission_bundles.yml`；
- Catalog 不支持 Admin 在线编辑或热加载；
- Bundle code 的稳定标识和两阶段 rename/delete 规则；
- `reconcile_permission_assignments` 的 dry-run/apply 部署顺序；
- `.env/settings`、`core/config`、SiteConfig、APP model、fixture、constant 的边界；
- 首次硬切换会清空旧授权配置，部署前必须确认 superuser；
- `NOTES_ROOT` / `PRIVATE_MEDIA_ROOT` 的唯一配置来源。

---

# 18. Definition of Done

满足以下条件才算本次权限重构完成：

- [ ] Django Permission 是唯一运行时授权事实来源。
- [ ] Bundle Catalog 位于 `core/config/permission_bundles.yml`，只负责部署期配置与同步，不参与 runtime auth 判断。
- [ ] Catalog 是 versioned、flat、strictly validated YAML，不支持嵌套、Admin 在线编辑或热加载。
- [ ] 未知 Bundle code、重复 code/name、缺失或模糊 Permission 均 fail loudly。
- [ ] `core.permissions` 只负责 Catalog/解析，`accounts.services` 只负责 Group/User assignment 写操作。
- [ ] Group/User 的 explicit Permission 有独立持久化来源，native M2M 只是 bundles ∪ explicit 的投影。
- [ ] 原始 native M2M 不再作为 Admin 输入；reconciliation 能检测并修复 drift。
- [ ] assignment 与 reconciliation 事务化，授权和撤权均有测试。
- [ ] 没有业务授权代码依赖固定 Group 名称 / codename。
- [ ] 默认 fixture 不创建教练/选手/班务业务角色。
- [ ] 旧 Bundle rewrite/backfill/inference/alias 代码和测试已删除。
- [ ] 硬切换清空旧授权配置，但保留 User、Group、membership、Group 技术映射及业务关系。
- [ ] 新用户默认 Group 可由 SiteConfig 配置，未配置时零业务权限。
- [ ] SiteConfig 单例读取/Admin 一致，保存和删除会失效缓存。
- [ ] 部署/静态/在线/业务/fixture/constant 配置边界已写入 `core/config/README.md`。
- [ ] 私有路径只来自 settings；Notes 使用 `settings.NOTES_ROOT` 且根目录逃逸保护保持有效。
- [ ] 所有非公开业务 GET View 均有显式 Django Permission。
- [ ] 所有 POST/修改/删除/下载端点均有对应 Django Permission。
- [ ] owner-based 数据均通过 selector/policy 限制。
- [ ] `*_all` 只负责扩大 scope。
- [ ] TrainingLog 详情/修改横向越权已修复。
- [ ] Forum attachment 父对象绕过已修复。
- [ ] ArchiveAsset 不能绕过父业务对象。
- [ ] 敏感媒体不能通过公共 media URL 绕过权限。
- [ ] 菜单 fail-closed。
- [ ] staff 不自动拥有 TMS 业务权限。
- [ ] superuser 保持 Django 原生全权限。
- [ ] 零 Permission 用户看不到业务菜单和业务内容。
- [ ] HTMX 端点与普通 HTTP 使用相同授权规则。
- [ ] 全部迁移有测试。
- [ ] 全部权限关键路径有 direct URL / PK tampering 测试。
- [ ] 用户手册和 ADR 已更新。
- [ ] `uv run manage.py check` 通过。
- [ ] `uv run ruff check .` 通过。
- [ ] `uv run manage.py makemigrations --check --dry-run` 通过。
- [ ] `uv run pytest` 通过。
- [ ] 如有 Tailwind/Iconify class 变化，`npm run build:css` 通过。

---

# 19. Codex 执行约束

Codex 执行本 Plan 时必须遵守：

1. 先读取当前仓库 `AGENTS.md`、`CONTEXT.md` 和相关 ADR。
2. 以执行时最新 `develop` 为准；如 HEAD 已变化，先比较权限相关变化再实施。
3. 不引入 django-guardian、Casbin 或新的 RBAC/ACL 框架。
4. 不新增自定义 Role/UserRole 表。
5. 不把 Permission Bundle 做成 runtime 权限 backend。
6. 不把 Bundle Catalog 做成数据库在线模型，不支持 nested Bundle、热加载或通用配置 DSL。
7. 不允许未知 Bundle code / Permission 被静默丢弃，也不允许 native M2M 绕过 assignment service 成为第二个配置来源。
8. 不用 Group 名称/codename做业务授权；GroupProfile.codename 的技术集成用途必须与授权分离。
9. 不把 EventParticipant.Role 等领域角色误认为 Django auth role。
10. 不用 `is_staff` 代替业务 Permission。
11. 不为旧授权数据保留 rewrite、backfill、alias、fallback 或双写。
12. 不通过仅隐藏按钮“修复”权限。
13. 不允许通用 Archive / Media / Attachment URL 绕过父对象权限。
14. 不把所有 own/all 逻辑抽成复杂通用 ACL 引擎；保持 app-specific selector/policy。
15. 不在模板中做复杂权限业务计算。
16. 所有关键授权修复先写 regression test，再改实现。
17. 授权硬切换不得删除 User、Group、membership、业务关系或 migration 历史。
18. 文件迁移不得因“不兼容旧授权数据”而直接删除原文件。
19. 每完成一个阶段运行最相关测试，最后运行全量验证。

---

# 20. 推荐实施提交顺序

为降低一次性变更风险，建议按以下 commit 粒度执行：

```text
1. docs: record finalized permission architecture
2. docs: define configuration ownership and static catalog boundary
3. refactor: move permission bundle catalog to strict YAML registry
4. feat: persist explicit permission intent and reconcile native projections
5. feat: add scope permissions and hard-cutover authorization data
6. refactor: remove hard-coded authorization roles and legacy backfill
7. feat: harden SiteConfig and add configurable default registration group
8. refactor: make navigation fail closed
9. fix: enforce training log ownership scopes
10. fix: protect forum and archive attachments
11. fix: unify private path settings and protect business downloads
12. refactor: enforce read permissions across business apps
13. refactor: align templates tables and htmx permission checks
14. docs: add permission management and deployment guidance
15. test: complete authorization matrix regression coverage
```

不要为了凑提交数机械拆分；如果 migration 和依赖代码必须同 commit 才可运行，应保持原子性。

---

# 21. 最终验收场景

Codex 完成后至少手工/自动验证以下场景：

### 场景 A：零权限用户

```text
注册 / 登录
→ 登录成功
→ landing 显示“尚未获得业务访问权限”
→ 无业务 section/menu
→ 手工输入 /training/、/events/、/scoring/ 等 URL 均不可访问
→ 可以安全退出登录
```

### 场景 B：管理员自定义“基础用户”角色

管理员创建 Group：

```text
基础用户
```

分配 Bundle：

```text
standards.view_standard
events.view_event_catalog
glossary.study_glossary
notes.view_notes
```

用户加入该 Group 后：

- 只出现相应菜单；
- 对应 GET 可访问；
- 没有任何维护按钮；
- 直接访问 add/change URL 返回 403。

### 场景 C：自定义训练参与角色

管理员创建任意名称：

```text
2026集训队
```

分配：

```text
training.view_cycles
training.submit_logs
```

用户：

- 能看训练周期；
- 能上传训练日志；
- 只能查看/修改本人 TrainingLog；
- 猜测别人的 PK 不可访问；
- 看不到全体统计和导出。

### 场景 D：自定义训练管理角色

管理员创建：

```text
训练管理人员
```

分配：

```text
training.manage_cycles
training.view_all_logs
training.view_statistics
training.export_logs
```

用户无需被命名为“教练”，即可获得对应能力。

### 场景 E：superuser

- 无需 Group / Bundle。
- 所有 Permission 检查通过。
- 所有 scoped selector 返回全部。
- 管理员页面和业务页面均可进入。

### 场景 F：staff without business Permission

- 可在拥有 Django Admin 模型权限时进入相应 Admin 页面。
- 不能因为 `is_staff=True` 自动进入 Training / Scoring / Standards 等 TMS 业务页面。

### 场景 G：Catalog 调整与撤权

部署运维从一个已被分配的 Bundle 中移除某项 Permission：

```text
system check 通过
→ reconciliation dry-run 明确报告将撤销的 Group/User 投影
→ --apply 后原生 M2M 撤销该 Permission
→ 显式在 explicit_permissions 中选择该 Permission 的对象仍然保留
→ 其他对象的 Bundle、explicit 与业务关系不变
```

若直接删除仍被引用的 Bundle code，system check / reconciliation 必须失败并列出受影响 assignment，不得静默降权或保留旧投影。

### 场景 H：首次授权硬切换

```text
确认可登录 superuser
→ migrate 清空旧授权配置
→ User / Group / membership / 业务关系保持
→ 普通用户暂时为零业务权限
→ superuser 按新 Catalog 重新分配
→ reconciliation dry-run / apply
→ 权限、菜单、对象 Scope 和下载验证一致
```

---

# 22. 本次重构明确不做的内容

为了控制范围，本 Plan 不同时解决以下业务演进：

- ExamPaper 的 Draft / Restricted / Published 完整发布工作流；
- ScoringScheme 的发布/保密生命周期；
- 教练审核 TrainingLog 的独立 Review 模型；
- 跨技能项目 / 训练周期的 assignment scope；
- 通用 ABAC / policy DSL；
- 外部 SSO / OIDC；
- object permission 第三方库。
- Django Admin 在线创建 / 编辑 Permission Bundle 定义；
- Permission Bundle 嵌套、继承、条件表达式或热加载；
- 通用站点配置中心或把所有 APP 配置迁入 `core`；
- 删除 / squash 全仓历史 migrations；
- 重命名 `GroupProfile.codename` 或重构 Samba Unix group 映射。

这些可在权限底座稳定后分别设计。

---

# 23. 实施时参考的当前代码入口

重点文件：

```text
AGENTS.md
CONTEXT.md

core/config/README.md
core/config/permission_bundles.yml
core/permissions/bundles.py（当前实现，迁移后删除）
core/permissions/registry.py
core/permissions/checks.py
core/navigation.py
core/config/navigation.yml
core/constants.py
core/utils/mixins.py
core/models.py
core/admin.py

accounts/models.py
accounts/views.py
accounts/admin.py
accounts/admin_forms.py
accounts/services/permission_bundles.py（当前实现，迁移后拆分 / 删除）
accounts/services/permission_assignments.py
accounts/services/groups.py
accounts/services/users.py
accounts/management/commands/reconcile_permission_assignments.py
accounts/management/commands/backfill_permission_bundles.py（删除）
accounts/fixtures/accounts/default.yaml（删除）
scripts/create_test_users.py（按实际引用删除或重写）

training/models.py
training/views.py

behaviors/models.py
behaviors/permissions.py
behaviors/selectors.py
behaviors/views.py

worldskills_forum/views.py
worldskills_forum/permissions.py
worldskills_forum/selectors.py

archives/models.py
archives/views.py

scoring/models.py
scoring/views.py

examcontent/models.py
examcontent/views.py

events/models.py
events/views.py

standards/views.py
knowledge/views.py

glossary/models.py
glossary/views.py

notes/models.py
notes/paths.py
notes/views.py
notes/permissions.py

meetings/models.py
meetings/views.py
meetings/permissions.py

notices/models.py
notices/views.py

samba/models.py
samba/views.py

tmsproject/settings.py
tmsproject/urls.py

core/tests.py
各 APP tests
```

---

# 24. 技术参考基线

实施时以项目锁定/声明版本与当前官方文档为准：

- Django 6 authentication / permissions / `PermissionRequiredMixin`
- Django 6 `LoginRequiredMiddleware` / `login_not_required`
- Django default `ModelBackend`（不自带项目所需的对象级权限实现）
- django-htmx 当前 middleware / `request.htmx` 行为
- django-tables2 当前 request-aware table rendering / `before_render`
- Tailwind CSS 4 source scanning：class 名保持静态完整字符串
- DaisyUI 5 + Tailwind CSS 4
- Alpine.js CSP build
- Iconify 当前项目既有静态 class 使用方式

权限安全的最终判断始终在 Django 服务端完成。

---

## 给 Codex 的最终执行指令

> 请严格执行本文件，而不是重新设计另一套权限体系。
> 本文件第 2 节“已定稿的权限模型”属于不可改变的架构约束。
> 先完成 Phase 0 的现状确认和 grep；如果执行时 `develop` 与基线提交已有变化，以最新代码为准调整文件路径，但不要改变权限架构原则。
> Permission Bundle 必须使用部署期 `core/config/permission_bundles.yml`；不得退回 Python hard-code，也不得扩展成 Admin 在线 Bundle model。
> explicit Permission 必须独立持久化，native Django Permission M2M 只作为可由 reconciliation 确定重建的运行时投影。
> 本次不迁移旧授权配置：删除 rewrite/backfill/alias 并执行一次性硬切换，但保留 User、Group、membership、业务关系、业务文件和 migration 历史。
> 对每个修改的业务入口同时检查 View、Selector/Policy、Menu、Template/Table、HTMX、Attachment/Download 和 Tests。
> 高风险授权问题先写回归测试后修复。
> 最终必须完成 Definition of Done 中全部适用项，并输出：修改摘要、迁移说明、权限 Bundle 变更表、测试结果、仍然存在但明确不属于本次范围的问题。
