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

普通列表优先用 django-tables2；复杂矩阵表格可手写 HTML，但必须放入 `components/table_wrapper.html` 的结构中。