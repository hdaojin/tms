# TMS 全站面包屑（Breadcrumbs）实施 Plan

> 目标仓库：`hdaojin/tms`  
> 目标分支：`develop`  
> 方案基线：`977e52f9dcdd5c54d8bbfec466e7a5d42e67d06b`  
> 技术栈：Django 6 / Python 3.13 / django-htmx / django-tables2 / Tailwind CSS 4 / DaisyUI 5 / Alpine.js / Iconify

---

## 1. 背景

TMS 当前已经具备面包屑的展示基础：

- `templates/layouts/app.html` 已预留 `{% block breadcrumbs %}`；
- 默认 include `templates/partials/breadcrumbs.html`；
- `partials/breadcrumbs.html` 已使用 DaisyUI `breadcrumbs` 结构；
- 当前大多数业务 View 已复用 `core.utils.mixins.TitleMixin`；
- `core/navigation.py` 已能通过 `request.resolver_match`、`active_app_names`、URL 等信息判断当前所属导航 Section；
- `core/config/navigation.yml` 是全站导航唯一配置入口。

当前缺失的是统一的 **Breadcrumb 数据生成机制**。除 `notes` 等少量页面自行手写 Breadcrumb 外，大部分页面没有提供 `breadcrumbs` 上下文。

本次改造的目标不是重新实现一个 UI 组件，而是补全现有页面基础设施，使面包屑成为与 `title`、`title_icon` 类似的统一页面元信息。

---

## 2. 总体目标

实现一套低侵入、可复用、可扩展的全站 Breadcrumb 机制，使使用 `layouts/app.html` 的标准业务页能够：

1. 默认自动生成基础 Breadcrumb；
2. 自动识别当前一级导航 Section；
3. 自动使用当前页面 `title` 作为最后一级；
4. 对复杂业务对象显式声明真实父级；
5. 不根据 URL 路径机械推断业务层级；
6. 不把 `navigation.yml` 当成完整业务对象树；
7. 不引入新的前端交互依赖；
8. 与现有 DaisyUI / Tailwind / Iconify 风格保持一致；
9. 收敛并删除页面内重复手写的 Breadcrumb；
10. 为后续新 APP 提供明确、简单的开发约定。

---

## 3. 设计原则

### 3.1 Breadcrumb 的信息来源

Breadcrumb 按以下顺序组织：

```text
首页
  ↓
当前导航 Section
  ↓
View 显式声明的业务父级（0~N 层）
  ↓
当前页面 title
```

示例：

```text
首页 > 标准 > 技能项目 > 网络系统管理
```

复杂业务：

```text
首页 > 竞赛与考核 > 第48届世界技能大赛 > Module A > 评分方案
```

---

### 3.2 navigation.yml 的职责边界

继续保持：

```text
core/config/navigation.yml
```

为全站导航唯一配置入口。

Breadcrumb 可以复用 `core.navigation.resolve_current_section(request)` 获取当前一级 Section，但：

- 不新增第二套 breadcrumb YAML；
- 不在 `navigation.yml` 中维护所有对象级 Breadcrumb；
- 菜单 group 一般不进入 Breadcrumb；
- 不把侧边栏菜单层级机械转换成 Breadcrumb。

例如：

```text
标准
  └─ 标准体系（menu group）
       ├─ 技能项目
       ├─ WSOS
       └─ 标准技能树
```

Breadcrumb 不应出现无实际业务意义的：

```text
首页 > 标准 > 标准体系 > ...
```

---

### 3.3 不根据 URL 自动拆分完整层级

禁止通过：

```text
request.path.split("/")
```

或 URL path segment 自动生成 Breadcrumb。

原因：

- URL 层级不等于领域对象层级；
- `AssessmentModule` 的真实父对象是 `Assessment`；
- `ScoringScheme` 的真实父对象是 `AssessmentModule`；
- 技能树涉及 SkillProject / TechnicalDomain / SkillTreeVersion / Skill 等领域关系；
- 部分页面使用查询参数 Tab，但 Tab 不是独立资源。

复杂关系必须由 View 根据领域对象明确提供。

---

### 3.4 Tab / Filter / QueryString 不进入 Breadcrumb

例如：

```text
/assessments/8/?tab=scoring
```

无论当前是：

- 概览
- 模块与资料
- 人员
- 评分
- 最终结果
- 考点与技能
- 分析

Breadcrumb 均保持：

```text
首页 > 竞赛与考核 > 第48届世界技能大赛
```

Tab 是页面内部工作区状态，不是新的资源层级。

---

## 4. 核心实现设计

### 4.1 新增 Breadcrumb 数据对象

建议新增：

```text
core/utils/breadcrumbs.py
```

定义简单的数据结构，例如：

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Breadcrumb:
    label: str
    url: str | None = None
    icon_class: str = ""
```

保持对象职责简单，不实现复杂 DSL。

可按实际需要补充少量 helper，例如：

- 安全 reverse；
- 相邻重复 label 去重；
- 当前 crumb 统一去除 URL；
- 从 Section 构造 Breadcrumb。

不要把业务对象解析逻辑集中到 core 中。

---

### 4.2 新增 BreadcrumbMixin

建议在：

```text
core/utils/mixins.py
```

新增 `BreadcrumbMixin`。

建议接口：

```python
class BreadcrumbMixin:
    show_breadcrumbs = True

    def get_breadcrumb_parents(self):
        return []

    def get_breadcrumbs(self):
        ...

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumbs"] = self.get_breadcrumbs()
        return context
```

要求：

- `get_breadcrumb_parents()` 默认返回空列表；
- `get_breadcrumbs()` 负责合并 Home、Section、显式父级、当前 title；
- 自动去除相邻重复 label；
- 最后一级必须无 URL；
- `show_breadcrumbs = False` 时返回空列表；
- 不因 reverse 失败导致页面 500；
- 不查询与当前 View 无关的业务数据。

---

### 4.3 与 TitleMixin 集成

当前 TMS 大量类视图已经复用 `TitleMixin`。

建议：

```python
class TitleMixin(BreadcrumbMixin):
    ...
```

或其他不会破坏现有 MRO 的等价实现。

目标是：

> 现有标准业务类视图无需逐个增加 `BreadcrumbMixin`，只要使用 `TitleMixin` 即默认获得基础 Breadcrumb。

必须检查 MRO，确保：

```python
get_context_data()
```

链路仍正确调用 `super()`，不破坏已有类视图和 mixin。

---

## 5. 默认 Breadcrumb 生成规则

### 5.1 Home

Home 固定作为第一项。

建议 UI：

- 使用 Iconify `icon-[tabler--home]`；
- 视觉上只显示图标；
- 保留 `sr-only` 的“首页”文本用于可访问性；
- 链接指向系统首页。

---

### 5.2 Section

使用：

```python
resolve_current_section(request)
```

识别当前 Section。

从 `navigation.yml` 中取得：

- label；
- 对用户可访问的第一个有效 URL。

例如：

```text
training  -> 训练
standards -> 标准
assessments/scoring/evidence -> 竞赛与考核
account -> 账户
```

注意：

- 继续遵守已有权限过滤；
- 不显示用户没有权限访问的 Breadcrumb 链接；
- Section 无有效 URL 时可只显示 label 或按现有 navigation helper 的结果处理；
- 不复制一份 Section 映射常量。

---

### 5.3 当前页面

当前页面最后一级优先使用 `TitleMixin.get_title()` 的最终结果。

例如：

```python
title = "{name}"
```

应该得到真实对象名称，而不是模板字符串。

最后一级：

```text
url = None
```

且模板中设置：

```html
aria-current="page"
```

---

### 5.4 自动去重

必须避免：

```text
首页 > 竞赛与考核 > 竞赛与考核
```

建议对相邻相同 label 去重，最终显示：

```text
首页 > 竞赛与考核
```

同理：

```text
首页 > 标准 > 标准
```

应合并。

不要跨越不同父级进行过度去重。

---

## 6. 简单页面的父级声明

对于标准 CRUD 页面，可允许 View 静态声明父级。

可以选择一种简洁 API，例如：

```python
breadcrumb_parents = [
    Breadcrumb("训练计划", reverse_lazy("training:plan_list")),
]
```

或者使用更适合当前项目风格的声明形式。

实现时优先考虑：

- 可读性；
- 不在 import 阶段错误 reverse 动态 URL；
- 不增加复杂配置层；
- 容易测试。

示例目标：

```text
训练计划列表：
首页 > 训练 > 训练计划

训练计划详情：
首页 > 训练 > 训练计划 > 九月训练计划

新增训练计划：
首页 > 训练 > 训练计划 > 新增训练计划

编辑训练计划：
首页 > 训练 > 训练计划 > 编辑训练计划
```

---

## 7. 复杂对象使用 get_breadcrumb_parents()

涉及真实领域父子关系时，在 View 中覆盖：

```python
def get_breadcrumb_parents(self):
    ...
```

不要把这些关系配置到 `navigation.yml` 或 core。

### 7.1 AssessmentModule

目标：

```text
首页
> 竞赛与考核
> 第48届世界技能大赛
> Module A
```

父级从：

```python
self.object.assessment
```

获得。

必要时在 `get_queryset()` 中补充 `select_related("assessment")`，避免 N+1 或额外查询。

---

### 7.2 Scoring

涉及评分方案时，目标业务路径：

```text
首页
> 竞赛与考核
> 第48届世界技能大赛
> Module A
> 评分方案
```

根据实际 View 的对象关系，从：

```text
ScoringScheme
  -> AssessmentModule
  -> Assessment
```

构造。

不要为所有 scoring 页面强制加入同一深度，按实际资源语义处理。

---

### 7.3 Standards

重点覆盖以下业务路径：

#### SkillProject

```text
首页 > 标准 > 技能项目 > 网络系统管理
```

#### TechnicalDomain

```text
首页 > 标准 > 技能项目 > 网络系统管理 > Linux
```

#### 当前技能树

```text
首页 > 标准 > 技能项目 > 网络系统管理 > Linux > 标准技能树
```

#### SkillTreeVersion

```text
首页 > 标准 > 技能项目 > 网络系统管理 > Linux > 技能树 v3
```

#### Skill

根据 Skill 当前入口和可确定的业务上下文合理组织，例如：

```text
首页 > 标准 > 技能项目 > 网络系统管理 > Linux > DNS 服务配置
```

若同一 Skill 可能属于多个树/上下文，不要在 core 中猜测；优先根据当前 View 已有参数和对象关系构造稳定路径。

---

### 7.4 Training

至少覆盖：

- TrainingCycle
- TrainingPlan
- TrainingTask
- TrainingLog

示例：

```text
首页 > 训练 > 训练周期 > 2026 世赛冲刺周期
首页 > 训练 > 训练计划 > 九月训练计划
```

若训练计划、任务存在明确父对象且页面语义需要，可增加业务父级；不要为了“层级更多”而制造冗余 Breadcrumb。

---

## 8. Notes 页面收敛

当前：

```text
notes/templates/notes/note_detail.html
```

存在页面内手写 DaisyUI Breadcrumb。

本次应：

1. 删除模板中的重复 Breadcrumb HTML；
2. 在对应 View/context 中生成统一 `breadcrumbs`；
3. 保留 Notes 自身有意义的业务层级。

目标示例：

```text
首页
> 资料
> 笔记仓库
> Debian 教学讲义
> DHCP 服务
```

避免最终同时出现：

```text
全局 Breadcrumb
+
Notes 页面自己的 Breadcrumb
```

---

## 9. Breadcrumb 模板调整

修改：

```text
templates/partials/breadcrumbs.html
```

继续复用 DaisyUI `breadcrumbs`，不要重做 CSS 组件。

建议结构：

```html
<nav
  class="breadcrumbs max-w-full overflow-x-auto text-sm text-base-content/70"
  aria-label="面包屑"
>
  <ul>
    ...
  </ul>
</nav>
```

要求：

- 使用 `<nav aria-label="面包屑">`；
- 最后一级使用 `aria-current="page"`；
- 最后一级不可点击；
- Home 使用 Iconify 图标，并提供屏幕阅读文本；
- 其余层级默认纯文本，不给每一级增加图标；
- 长 Breadcrumb 在窄屏保持横向滚动；
- 不增加 JS 折叠逻辑；
- 不实现“... 中间层折叠”。

现有：

```text
max-w-full
overflow-x-auto
```

思路可继续保留。

---

## 10. Layout 范围

第一版仅将 Breadcrumb 作为：

```text
layouts/app.html
```

的标准能力。

建议：

| Layout | Breadcrumb |
|---|---|
| `layouts/app.html` | 默认启用 |
| `layouts/minimal.html` | 暂不默认 |
| `layouts/auth.html` | 不启用 |
| `layouts/print.html` | 不启用 |
| `layouts/htmx.html` | 不启用 |
| 首页大屏 | 不启用 |
| 倒计时大屏 | 不启用 |

不要为了“全站都有”修改不适合 Breadcrumb 的 layout。

---

## 11. HTMX / Alpine.js 约束

本功能本质是 Django Server-rendered navigation。

### 不需要 Alpine.js

不要新增：

```text
x-data
x-show
x-collapse
```

没有客户端 reactive state 时不使用 Alpine。

### 不需要专门 HTMX 化

Breadcrumb 链接使用标准：

```html
<a href="...">
```

不要默认添加：

```text
hx-get
hx-target
hx-swap
```

不要为 Breadcrumb 单独引入局部更新协议。

现有 HTMX partial 页面也不应负责渲染整个 Breadcrumb 页面壳。

---

## 12. 权限与安全

Breadcrumb 不得泄露用户不可见资源。

要求：

1. Section 必须沿用当前 navigation 权限过滤；
2. 复杂父对象来自当前 View 已授权、已过滤的对象关系；
3. 不为了构造 Breadcrumb 绕过已有 selector/queryset 权限边界；
4. 不通过全局不受限 queryset 查询父资源；
5. 用户无父资源查看权限时，不应提供可点击的越权链接；
6. Breadcrumb 仅是导航展示，不能替代实际 View 权限控制。

---

## 13. 性能要求

Breadcrumb 不应显著增加页面查询。

要求：

- 优先复用 `self.object`；
- 父对象尽量通过已有 `select_related()` / `prefetch_related()` 获取；
- 不在模板中做数据库查询；
- 不为 Section 重复解析完整导航多次；
- 复用 `core.navigation` 当前缓存机制；
- 对新增的复杂链路使用 `assertNumQueries` 仅在确有价值时测试，不为测试而过度固定查询数。

---

## 14. 测试计划

### 14.1 core 单元测试

重点测试统一基础能力：

- Home crumb 正确；
- Section crumb 正确；
- 当前 title 成为最后一级；
- 动态 `TitleMixin` title 正确；
- 当前 crumb 无 URL；
- `show_breadcrumbs = False` 返回空；
- 相邻重复 label 自动去重；
- 无 request / 无 resolver_match 的边界情况安全；
- reverse 失败时不导致 500；
- Section 权限过滤正确。

可在：

```text
core/tests/
```

或符合当前项目测试组织方式的位置新增专门测试文件。

不要把所有逻辑都塞回单一大型 `core/tests.py`，若当前测试目录结构允许，优先保持主题清晰。

---

### 14.2 代表性集成测试

至少覆盖以下链路：

#### Training

```text
训练 > 训练计划 > 某计划
```

#### Assessments

```text
竞赛与考核 > 某竞赛 > Module A
```

#### Standards

```text
标准 > 技能项目 > 项目 > 技术领域 > 技能树
```

#### Notes

验证原手写 Breadcrumb 已删除，统一机制正确输出。

---

### 14.3 模板可访问性断言

验证输出包含：

```html
<nav aria-label="面包屑">
```

以及当前项：

```html
aria-current="page"
```

并确认最后一级没有链接。

---

## 15. 推荐实施顺序

### Phase 1：core 基础能力

1. 阅读 `AGENTS.md`；
2. 阅读现有 `core/navigation.py`；
3. 阅读 `core/utils/mixins.py`；
4. 阅读 `layouts/app.html` 与 `partials/breadcrumbs.html`；
5. 新增 `core/utils/breadcrumbs.py`；
6. 新增 `BreadcrumbMixin`；
7. 与 `TitleMixin` 集成；
8. 为基础行为写 core 测试；
9. 运行相关 core 测试。

完成后，大部分使用 `TitleMixin` 的页面应至少自动拥有：

```text
Home > Section > Title
```

---

### Phase 2：模板和可访问性

1. 优化 `partials/breadcrumbs.html`；
2. 保持 DaisyUI Breadcrumb 结构；
3. 增加 Home Iconify；
4. 增加 `nav` / `aria-label` / `aria-current`；
5. 验证移动端长路径横向滚动；
6. 不新增 JS。

---

### Phase 3：业务层级补全

按价值优先级处理：

1. `assessments`
2. `scoring`
3. `standards`
4. `training`
5. `notes`

对每个复杂页面：

- 先确认真实领域父子关系；
- 再实现 `get_breadcrumb_parents()`；
- 必要时调整 queryset 的 `select_related()`；
- 不从 URL 猜父对象。

---

### Phase 4：收敛重复实现

全仓搜索：

```text
class="breadcrumbs
breadcrumbs
```

检查是否仍存在页面内手写 Breadcrumb。

除明确有特殊 UI 需求的情况外，统一迁移到全站机制。

重点删除 `notes` 当前重复实现。

---

### Phase 5：项目规范

在 `AGENTS.md` 合适位置补充简短规范，不写成长篇教程。

建议语义：

> 完整业务页面使用统一的 Title/Breadcrumb 页面元信息能力。Breadcrumb 的一级栏目复用 `core/config/navigation.yml` / `core.navigation`，复杂对象层级通过 View 显式声明，不根据 URL path 猜测；不要在业务模板中重复手写 Breadcrumb。

---

## 16. 不做事项

本次明确不做：

- 不新建独立 Breadcrumb APP；
- 不新增数据库模型；
- 不新增 migration；
- 不新增 breadcrumb.yml；
- 不恢复旧菜单配置；
- 不根据 URL segment 自动生成完整路径；
- 不引入第三方 Breadcrumb Python 包；
- 不新增 Alpine.js 交互；
- 不新增 HTMX Breadcrumb 请求；
- 不做移动端 `...` 自动折叠；
- 不改变首页、登录页、打印页、倒计时页；
- 不为了 Breadcrumb 重构无关业务；
- 不进行与本改动无关的大规模 UI 重构。

---

## 17. 验收示例

最终至少应得到类似以下结果。

### Training

```text
⌂ > 训练 > 训练周期
⌂ > 训练 > 训练周期 > 2026 世赛冲刺周期
⌂ > 训练 > 训练计划 > 九月训练计划
```

### Standards

```text
⌂ > 标准 > 技能项目 > 网络系统管理
⌂ > 标准 > 技能项目 > 网络系统管理 > Linux
⌂ > 标准 > 技能项目 > 网络系统管理 > Linux > 标准技能树
⌂ > 标准 > WSOS > WSOS 2026
```

### Assessments / Scoring

```text
⌂ > 竞赛与考核 > 第48届世界技能大赛
⌂ > 竞赛与考核 > 第48届世界技能大赛 > Module A
⌂ > 竞赛与考核 > 第48届世界技能大赛 > Module A > 评分方案
```

### Notes

```text
⌂ > 资料 > 笔记仓库 > Debian 教学讲义 > DHCP 服务
```

---

## 18. 验收标准

实现完成后必须满足：

- [ ] `layouts/app.html` 的 Breadcrumb 插槽继续作为唯一标准展示入口；
- [ ] `partials/breadcrumbs.html` 继续复用 DaisyUI；
- [ ] 大部分 `TitleMixin` 页面零额外配置即可显示基础 Breadcrumb；
- [ ] Section 来源于现有 navigation 配置/解析机制；
- [ ] 复杂业务对象路径由 View 显式生成；
- [ ] 当前页面为最后一级且不可点击；
- [ ] Home 使用 Iconify 图标并具备可访问文本；
- [ ] 重复 label 自动去重；
- [ ] Assessment Tab 不进入 Breadcrumb；
- [ ] Notes 重复手写 Breadcrumb 被收敛；
- [ ] 不新增 Alpine / HTMX 行为；
- [ ] 不泄露无权限资源；
- [ ] 不产生明显额外查询；
- [ ] 相关 core 测试通过；
- [ ] 代表性 Training / Assessments / Standards / Notes 集成测试通过；
- [ ] Ruff / 项目已有相关静态检查通过；
- [ ] `AGENTS.md` 更新了简短 Breadcrumb 开发规范。

---

## 19. Codex 执行要求

Codex 实施时：

1. 以当前 `develop` 最新代码为准，不假设本 Plan 中的代码片段与仓库完全一致；
2. 先读 `AGENTS.md` 和相关现有代码，再做最小必要修改；
3. 优先复用已有 `core.navigation`、`TitleMixin`、DaisyUI partial；
4. 如果实际代码结构与 Plan 有小差异，保持设计原则不变并按现状调整；
5. 不引入不必要抽象；
6. 不进行无关重构；
7. 每完成一个阶段运行对应的针对性测试；
8. 优先运行受影响测试，不要无目的地反复执行全量测试；
9. 最后汇报：
   - 修改文件；
   - 核心设计；
   - 关键业务链路；
   - 测试结果；
   - 尚未覆盖或需要人工确认的边界。
