---
name: tms-dev
description: TMS 功能开发与重构的执行工作流。用于从业务目标和现有代码链路出发，判断 model/form/service/selector/view/template 的职责，完成权限、导航、文件、HTMX 与测试闭环。项目长期规范以仓库根目录 AGENTS.md 为准，本 skill 不复制规范。
---

# TMS Feature Delivery Workflow

## 这个 Skill 解决什么问题

使用 `$tms-dev` 时，目标不是再次背诵一遍项目规范，而是把一次 TMS 开发任务从“需求”推进到“可验证的完整纵向切片”。

适用于：

- 新增或修改一个 TMS 业务功能。
- 重构现有 Django APP 的业务流程。
- 涉及多个 APP 的导入、统计、权限或数据联动。
- 新增列表/详情/表单/HTMX 局部交互，并需要接入现有 UI 与导航。

仅做仓库问答、解释某段代码或单纯代码 review 时，不必机械执行完整流程。

## 工作契约

开始前读取：

1. 仓库根目录 `AGENTS.md`：工程规则与架构边界的权威来源。
2. 涉及领域模型、统计口径或业务术语时读取 `CONTEXT.md`，并检查相关 ADR。
3. 需要快速定位当前 APP 与入口时读取 `references/project-overview.md`。
4. 实施过程中需要逐项收尾时读取 `references/feature-checklist.md`。

如果 reference 与实际代码不一致，以当前代码/迁移/测试确认现状，并在本次变更中修正 reference；不要用 skill 覆盖 `AGENTS.md`。

## Step 1：先定义功能边界

在改代码前明确以下内容：

- 谁在使用：角色/permission 是什么？
- 从哪里进入：URL、导航项、详情页动作还是后台入口？
- 读写哪些领域对象？它们属于哪个 APP？
- 哪些业务不变量必须始终成立？
- 是否涉及文件、导入、批量操作、外部系统或状态迁移？
- 成功后的可观察结果是什么？失败时必须回滚什么？

如果任务跨越 `standards -> events -> examcontent/scoring -> knowledge -> training` 主链路，先画出数据流再动模型。

## Step 2：沿现有纵向切片追代码

不要从一个孤立文件开始写。按实际请求路径检查：

`urls -> view -> form/table -> service/selector -> model -> template/fragment -> navigation -> tests`

同时检查：

- 目标 APP 已有的 `services.py` / `selectors.py`。
- `core` 中现成的 mixin、table、form field、upload、permission、navigation helper。
- 相似但**当前仍在使用**的页面实现。
- 相关 migration 和测试，确认历史兼容要求。

这样做的目的，是复用当前架构，而不是从旧 APP 或旧文档复制过时模式。

## Step 3：把逻辑放到正确层

用下面的判断顺序决定代码位置：

### Model

当规则只描述一个实体自身，或能用数据库 constraint 保证时，放 model/constraint。

例：日期范围合法、同一版本 code 唯一、父子节点必须属于同一技能树。

### Form

当规则主要是输入规范化、字段联动或需要向用户展示友好错误时，放 form；不要把最终授权只放在 form。

### Service

只要一次业务动作需要写多个模型、需要事务、需要导入确认、需要状态迁移或需要跨 APP 协作，就优先建立/复用 service。

典型参考：`scoring.services.parse_scheme_upload()` / `confirm_scheme_import()`。

### Selector

当查询会被复用、包含统计聚合、多层关系、树形分析或需要集中定义口径时，放 selector。

典型参考：`knowledge/selectors.py`。

### View

View 只负责 HTTP 边界：解析请求、权限、调用 form/service/selector、选择 full-page 或 HTMX fragment、返回 response。

### Template / Table

Template 只做展示和轻量状态判断；表格展示逻辑优先放 django-tables2 Table/Column。不要在模板重新计算业务状态。

## Step 4：选择最小但完整的实现切片

优先一次完成一个可用纵向切片，而不是先铺大量抽象。

一个典型 CRUD/业务功能至少考虑：

- model/constraint（若需要）
- migration（若需要）
- form
- service/selector（复杂逻辑才需要）
- view + URL
- table/detail/template
- permission
- navigation
- tests
- user manual

跨 APP 写流程必须先确定事务边界和失败策略，再写 UI。

## Step 5：导入与外部数据工作流

评分表、结果包、CMP 回传、Excel/JSON 等导入功能优先采用：

1. 接收原始文件/数据。
2. 保存或登记原始来源（领域主链路文件优先 `ArchiveAsset`）。
3. parser 生成规范化 payload。
4. 保存解析快照、字段映射与 validation report。
5. 给用户预览/确认，或由明确策略自动确认。
6. 在 `transaction.atomic()` 中写正式数据。
7. 对重复导入定义幂等键、覆盖规则和已有下游数据时的保护策略。

不要让 parser 一边解析一边零散修改正式业务表。

## Step 6：权限与对象访问

对每个新入口同时检查：

- 页面是否需要登录。
- GET 是否有查看权限。
- POST/PUT/DELETE 是否有对应修改权限。
- 直接访问 URL 是否仍然受保护。
- 对象级所有者/跨角色访问是否符合业务规则。
- 是否应新增/复用业务 permission bundle。

不要仅通过隐藏按钮实现权限。

需要角色身份判断时遵循 `AGENTS.md`：优先稳定 codename/permission，不扩散基于 `Group.name` 的新逻辑。

## Step 7：HTMX 与前端实现

如果使用 HTMX：

- 先保证服务器端完整流程正确，再做 fragment 优化。
- full-page 和 HTMX 请求共享同一份 query/service/form 逻辑。
- 用 `request.htmx` 选择响应模板/fragment。
- 缓存的响应若依赖 `HX-Request`，检查 `Vary`。
- 保持 CSRF、权限和验证与普通请求一致。

前端继续使用现有 layouts/components、DaisyUI + Tailwind 4、Alpine CSP build、Iconify。新增 class 必须是 Tailwind/Iconify 可静态检测的完整字符串。

## Step 8：性能与一致性复核

功能跑通后，专门做一次读取路径检查：

- 列表是否缺 `select_related` / `prefetch_related`。
- Table accessor 是否暗中触发逐行查询。
- 树形递归是否每个节点重新查询 children。
- 同一统计是否对每个节点/参与者重复扫描全量数据。
- 文件模型普通更新是否重复读取大文件。

再做一次写路径检查：

- 并发下唯一性是否只有 `.exists()` 检查而无 DB constraint。
- 跨模型写失败能否回滚。
- 重复提交/重复导入是否产生重复数据。
- GenericForeignKey 的目标类型与业务归属是否校验。

## Step 9：验证闭环

按改动范围选择验证，但不要省略最相关的测试：

```bash
uv run pytest <affected-app-or-test-path>
uv run ruff check <affected-paths>
uv run manage.py check
```

模型变化再运行：

```bash
uv run manage.py makemigrations --check --dry-run
```

跨 APP、权限、核心组件或统计口径变化，最终运行：

```bash
uv run pytest
```

模板/CSS/Iconify class 有变化时：

```bash
npm run build:css
```

如果任务要求 push，遵循 `AGENTS.md` 的 pre-push CSS build 要求。

## Step 10：文档与交付检查

结束前回答四个问题：

1. 用户现在从哪里进入并完成这个功能？
2. 哪些角色/权限可以读、写、删除或审核？
3. 数据最终落在哪些模型，失败/重复执行会怎样？
4. 哪些测试证明核心行为没有退化？

然后同步：

- 用户行为 -> `docs/user-manual/`
- 领域术语/业务不变量 -> `CONTEXT.md`
- 长期架构决策 -> `docs/adr/`
- 项目开发入口发生变化 -> `AGENTS.md` / 本 skill references

## References

- `references/project-overview.md`：当前 APP、领域主链路和关键入口地图。
- `references/feature-checklist.md`：功能实施与 review 的逐项检查表。
