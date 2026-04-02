---
description: "Use when editing Django HTML templates, HTMX partials, DaisyUI pages, shared form components, and template includes in TMS."
name: "TMS Templates and HTMX"
applyTo:
  - "templates/**/*.html"
  - "**/templates/**/*.html"
---

# TMS Templates and HTMX Guidelines

- 页面布局优先继承 [templates/base.html](../../templates/base.html)，复用现有 block 结构，不要重新发明页面外壳。
- HTMX 的 CSRF headers 已在 [templates/base.html](../../templates/base.html) 全局配置；除非请求脱离基础布局，否则不要重复手写同样的 headers。
- 优先复用共享模板组件，而不是在页面里重复铺开标记。常见入口见 [templates/components/form_snippet.html](../../templates/components/form_snippet.html)、[templates/components/field.html](../../templates/components/field.html)、[templates/components/table_block.html](../../templates/components/table_block.html)、[templates/components/doc_detail_with_pdf.html](../../templates/components/doc_detail_with_pdf.html)。
- 表单渲染优先沿用 `form_snippet.html` 和 `field.html` 组件流；不要为常规 Django 表单逐字段手写 DaisyUI 标记。
- 图标统一使用 `icon-[tabler--...]` 类名风格，保持与现有 Iconify/Tailwind 写法一致。
- 保持现有 DaisyUI 和 Tailwind 视觉语言；类名应与现有模板一致，不要引入另一套组件命名习惯。
- 页面标题优先由视图侧的 `TitleMixin` 提供 `title` 和 `title_icon`，模板只负责渲染，不重复造标题逻辑。
- HTMX 交互优先返回聚焦的局部模板片段，不要为局部刷新重复返回完整页面框架。
- 模板文案、帮助提示和错误信息默认使用中文；新页面命名与 include 路径保持 app 命名空间一致。
