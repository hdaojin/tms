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

## HTMX

- 局部响应只返回局部 HTML。
- 筛选、分页、排序更新结果容器。
- 表单校验失败只替换表单区域。
- CSRF 由 `static/js/htmx.js` 统一处理。
- 删除、归档、锁定等操作优先替换行、卡片或状态区域。

## CSP

- 不写 inline `<script>`、`onclick`、`javascript:` 链接。
- Alpine 逻辑放入 `static/js/alpine-components.js` 或改用 `data-*` + `static/js/app.js`。
- 主题切换由 `static/js/theme.js` 管理；偏好值支持 `system/light/dark/corporate/business/night`，`data-theme` 只写 DaisyUI 可识别的实际主题值。
- 需要新增脚本时，放入 static 文件并由布局集中加载。

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
