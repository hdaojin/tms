# TMS UI 开发规范

## 布局入口

- 后台登录后页面：`{% extends "layouts/app.html" %}`。
- 首页、错误页、邀请页、flatpages、公开展示页：`layouts/minimal.html`，默认带公共顶部导航、当前区域侧边栏和页脚。
- 登录、注册、找回密码：`layouts/auth.html`，内容写入 `{% block auth_content %}`，不显示公共侧边栏和页脚。
- 打印页面：`layouts/print.html`。
- 纯 HTMX 局部响应：`layouts/htmx.html` 或 `template.html#partial_name`。

## 页面模板

页面级小片段优先写在同一个模板中：

```django
{% partialdef results %}
  ...
{% endpartialdef %}
```

视图中优先返回：

```python
return render(request, "demo/list.html#results", context)
```

跨页面复用的内容才放入 `templates/components/`。

## 组件

常用入口：

- `components/form.html`
- `components/field.html`
- `components/table_wrapper.html`
- `components/list_filter_toolbar.html`
- `components/list_bulk_actions.html`
- `components/pagination.html`
- `components/file_upload.html`
- `components/confirm_modal.html`
- `components/alert.html`
- `components/empty_state.html`

组件参数中的 variant/size/icon class 必须由 Python 或调用方白名单提供完整类名，禁止 `text-{{ color }}`、`size-{{ size }}`、`icon-[{{ name }}]`。

组件局部标题不得复用页面级 `title` 变量；例如表格包装组件使用 `table_title` 或 `wrapper_title`，页面标题只由 `partials/page_header.html` 渲染。

## 文件上传

- 业务 APP 统一复用 `components/file_upload.html`，不要在各 APP 内分别实现文件选择、拖放、粘贴、预览和前端校验。
- 通用文件上传前端以 FilePond v5 为底层实现，FilePond 属于基础设施实现细节；业务模板和业务 JS 不直接依赖其内部 API。
- Django `FileField` / `MultipleFileField`、`UploadSpec` 及服务端 validator 始终是文件类型、大小和内容校验的最终事实来源；FilePond 的前端校验只用于即时反馈，不能替代服务端校验。
- 第一阶段保持普通 `multipart/form-data` 表单提交和 HTMX multipart 提交，不因引入 FilePond 而强制改成异步上传 API。需要大文件、分块上传或临时附件时，再按具体业务引入异步 store。
- FilePond v5 当前允许跟随 beta 版本升级；`package-lock.json` 保持每次提交的可复现版本，升级后应做上传组件的聚焦回归验证。
- 上传区域使用 FilePond 内置“浏览文件”入口、拖放和粘贴提供统一体验；粘贴截图或普通文件前必须先点击或聚焦目标上传区域，纯文本粘贴不应被拦截。
- 详细约定见 `docs/developer/file-upload.md` 和相关 ADR。

## HTMX

- 局部响应只返回局部 HTML。
- 筛选、分页、排序更新结果容器。
- 表单校验失败只替换表单区域。
- CSRF 由 `static/js/htmx.js` 统一处理。
- 删除、归档、锁定等操作优先替换行、卡片或状态区域。
- 文件表单通过 HTMX 提交时必须使用 `multipart/form-data` / `hx-encoding="multipart/form-data"`，并继续由 Django 表单处理 `request.FILES`。

## 前端脚本与 CSP

- 前端脚本遵循“**默认外置、按需内联**”，不机械追求“零 inline JavaScript”。跨页面复用、逻辑较复杂、需要独立测试或会持续维护的代码优先放入 `static/js/`。
- 页面局部、一次性、很短且与当前模板强耦合的初始化、配置或事件逻辑，如果内联反而更清晰，可以使用 inline `<script>` / `<script type="module">`；简短 `onclick` / `x-on` 也可在确有理由时使用，但不应承载复杂业务逻辑。
- 不要为了形式上消除一小段内联代码而额外制造全局状态、通用组件或无意义的 `data-*` 转发层。
- `javascript:` URL 仍禁止使用；事件处理优先使用语义化元素和正常事件绑定。
- 项目继续使用 Alpine.js CSP build；Alpine 指令应符合该 build 的能力边界。若项目实际启用 HTTP Content-Security-Policy，则所有内联脚本、动态资源和第三方组件必须同时满足实际 CSP 的 nonce、hash 或 source 限制。
- 主题切换由 `static/js/theme.js` 管理；偏好值支持 `system/light/dark/corporate/business/night`，`data-theme` 只写 DaisyUI 可识别的实际主题值。

## 导航

- 顶部导航入口由 `core/config/navigation.yml` 的 `layouts.header` 控制，只渲染纯文字。
- `core/config/navigation.yml` 的解析结果会进入 Django 缓存，并遵守 `CACHE_TIMEOUT`；开发时如需同时验证缓存命中与快速刷新，可在 `.env` 中调低 `CACHE_TIMEOUT`，等待 TTL 到期后观察变更，无需重启 `runserver`。
- “关于”入口使用 flatpage 路径 `/about/site/`，不要新增并行 AboutView。
- 有子菜单的侧边菜单默认折叠；当前路径只允许一个最具体的菜单项 `active=True`，父级只负责 `expanded=True`。
- 父级菜单只用于展开/收起；如果父级也需要访问入口，请显式提供“概览”子项。

## 表格

新列表页从 `core.tables` 导入：

```python
from core.tables import ActionsColumn, BaseDateColumn, BaseDateTimeColumn, BaseTable
```

普通列表优先用 django-tables2；复杂矩阵表格可手写 HTML，复用表格包装组件的横向滚动、边框和背景等视觉结构。`components/table_wrapper.html` 目前只接受 django-tables2 的 `table`，没有自定义 HTML 内容插槽，不要求矩阵直接 include 它。

## 列表页的三块布局

所有列表按以下顺序组织；用户列表是包含完整批量能力的接入示例，不是所有业务必须具备的功能清单。

1. **搜索筛选区**：独立 GET 表单，放在结果容器之外。优先复用 `FilterableListMixin`、`ListFilterSpec` 和 `components/list_filter_toolbar.html`；年月等专用筛选可以保留业务表单。先由业务 queryset 收窄可见范围，再应用筛选。
2. **批量操作区**：在结果列表之前，使用紧凑的“操作下拉框＋执行按钮＋已选计数”；额外角色、日期等参数不得全部铺在列表上，而应在执行后进入固定目标名单的中间页。
3. **结果列表区**：表格、空状态及分页；普通管理表格复用 `BaseTable` 和 `components/table_wrapper.html`。只有存在已授权批量动作时才显示行选择框和表头当前页全选框。

无筛选或无批量动作时省略对应区块，不渲染空占位，不为统一外观发明业务动作。普通查看者不显示批量栏和选择列。空结果保留筛选与空状态，禁用执行，不提供可执行的全匹配选择。

卡片流、树、统计矩阵、评分录入、详情内关联小列表和候选选择器只遵循适用部分，不强制转为 django-tables2，也不强制增加勾选或批量动作。新增、导入等整页操作仍使用既有工具区，不能伪装成依赖勾选记录的批量操作。

### 公共模板与组件边界

`common/table_page.html` 继续继承 `layouts/app.html`，默认仍渲染原表格。既有子模板在 `content` 中通过 `block.super` 加按钮或专用筛选的方式继续有效；新增页面优先使用以下扩展点：

| block | 责任 |
| --- | --- |
| `list_filters` | 默认按 `list_filter_controls` 呈现公共筛选栏，可覆盖为业务专用筛选 |
| `list_results` | 结果容器内部；批量页面在这里显式创建覆盖操作栏与行控件的 POST 表单 |
| `list_bulk_actions` | 默认结果结构中预留的批量栏位置；公共模板不自动创建表单或动作 |
| `list_table` | 默认包含表格包装组件；可替换为卡片、树或矩阵 |

结果容器 ID 使用 `list_filter_target_id`，未传时为 `list-results`。公共模板不自动推断授权、不生成批量端点、不创建 POST 表单，避免与已有业务表单嵌套。

HTMX 页面须在实际返回的业务模板中显式定义 `results` partial，并置于 `list_results` 内；不要假设 `业务模板.html#results` 会自动继承父模板的 partial。partial 包含批量栏与结果列表，不包含外层结果容器，避免默认 `innerHTML` 替换后出现重复 ID。

`components/list_bulk_actions.html` 只呈现操作栏，接口如下：

| 参数 | 约定 |
| --- | --- |
| `operation_field` | 必传 Django BoundField；空选项为“请选择操作”，widget 带 `data-bulk-operation` |
| `matching_count` | 必传；经过权限范围和当前筛选后的全部匹配数量，不是当前页行数 |
| `allow_select_all` | 默认关闭；仅业务后端已实现全匹配目标解析及确认流程时显式设为 `True` |
| `selection_label` | 默认“条记录”；如用户列表使用“位用户”，并在表单上设置同值的 `data-selection-label` |
| `selection_name` | 默认 `selection`；隐藏字段只表达 `selected` 或 `all`，不携带业务主键 |

调用方须用已授权动作构建 `operation_field`，同时控制批量表单及选择列的可见性；组件不读取用户角色、不推测动作权限。

### 选择交互与请求协议

仅在使用批量交互的页面加载 `static/js/list-bulk-actions.js` 一次。脚本采用事件委托，适用于 HTMX 更新；行为限定在对应批量表单中，不将选择状态保存在全局或跨页累积。

- POST 表单加 `data-bulk-list`、`data-matching-count`，并提供 CSRF；选择控件、操作栏必须归属于同一个表单。筛选 GET 表单不得嵌入该表单。
- 表头复选框标记 `data-select-page`，只选择当前页；行复选框标记 `data-row-selection`，`name` 与稳定主键值由业务约定，例如用户列表继续提交 `users`，不使用行号作为身份。
- 本页全部选中且匹配数大于当前页行数时，才显示已明确开放的“选择全部匹配结果”入口；进入全匹配模式后显示总数和清空入口，行复选框禁用。需要逐人调整时先清空选择。
- 操作默认为空，未选操作或目标时给中文提示；脚本校验不能替代服务器校验。全匹配开关和数量均不是可信授权数据。
- 筛选、翻页、排序后清空旧选择；HTMX 替换结果区时同时更新批量栏与列表。无关区域的 HTMX 更新不得清空其他列表的选择。
- 进入额外参数页时就固定目标名单，展示姓名／业务名称、稳定标识与人数，参数校验失败保留名单和输入；新增匹配记录不得悄悄加入。
- 保存或取消恢复进入前的筛选、排序和页码，清空选择；结果缩减导致原页码无效时回到最后有效页。返回链接只允许本站目标和白名单查询参数。

最小模板结构参考：

```django
{% extends "common/table_page.html" %}
{% load static %}
{% block list_results %}
  {% partialdef results inline %}
    {% if can_bulk_manage %}
      <form method="post" action="{{ bulk_action_url }}" data-bulk-list data-matching-count="{{ matching_count }}" novalidate>
        {% csrf_token %}
        {# 当前筛选快照、返回条件由业务端提供 hidden 字段，不信任客户端声称的数量 #}
        {% include "components/list_bulk_actions.html" with operation_field=bulk_form.operation matching_count=matching_count allow_select_all=can_select_all %}
    {% endif %}
    {% include "components/table_wrapper.html" with table=table %}
    {% if can_bulk_manage %}</form>{% endif %}
  {% endpartialdef %}
{% endblock %}
{% block extra_js %}
  {{ block.super }}
  <script src="{% static 'js/list-bulk-actions.js' %}" defer></script>
{% endblock %}
```

表格选择列同样以 `can_bulk_manage` 为条件显式启用；公共模板不会自动增加选择列。实际接入可参考 `accounts/templates/accounts/user_list.html`、其表格选择列和参数页；只复用布局与交互，不复制用户域的超级管理员规则、角色模型或保存服务。

### 批量写入的业务边界与验证

所有批量写操作须先预览明确目标、变更内容和人数，再确认保存；导出等不改变数据的操作可直接执行。参数中间页不是最终确认页。由业务服务严格验证操作、主键、筛选值和对象范围；非法筛选不得静默退化成全部记录。

预览固定名单并绑定相关现状；确认时重新检查操作者权限、对象存在性与业务状态，预览过期或相关状态变化后要求重新预览，不能只凭客户端签名中存在一组 ID 就跳过校验。多对象写入放在单一事务中，任一无效目标导致整批拒绝，不能循环调用各自提交的单对象服务而产生部分成功。无需变更的对象可跳过，但须明确统计。

新增接入至少验证：只读用户没有入口且伪造 POST 被拒；当前页／全匹配选择不会扩大到未授权对象；非法或空选择被拒；参数页固定名单；预览过期及状态变化；失败整批回滚；筛选、排序和分页条件恢复；普通／HTMX 响应都保持正确区域结构。公共模板变更还须覆盖既有 `content`／`block.super` 继承与没有筛选、没有批量动作的默认页面。

现有列表触及时逐步迁移；不因这份规范批量修改所有 APP 或为只读列表增加批量业务能力。
