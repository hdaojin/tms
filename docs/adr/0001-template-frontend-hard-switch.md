# ADR 0001: 新模板与前端基础设施硬切换

## 状态

Accepted

## 背景

新 TMS 将重建训练、考核、竞赛、技能树、评分归档、训练计划、用户角色权限等功能。旧标准链路 app 已从当前工作树删除，剩余启用 app 需要迁到面向未来的模板体系，而不是继续兼容旧 `base.html`、旧组件别名和旧菜单 YAML 分片。

## 决策

- `templates/base.html` 仅作为 `layouts/base.html` 的薄入口，底层骨架不再承载后台布局。
- 后台页面统一继承 `layouts/app.html`；独立页、认证页、打印页和 HTMX 响应分别使用 `minimal/auth/print/htmx`。
- 导航配置收敛为 `core/config/navigation.yml`，模板只渲染后端解析后的完整 `icon_class` 和 URL。
- django-tables2 基类迁到 `core/tables.py`，操作列通过模板组件渲染按钮和确认弹窗，不再拼接 inline `onclick`。
- Alpine 使用 `@alpinejs/csp` 构建；主题、HTMX、文件上传、确认弹窗、复制、打印等行为放在 `static/js/*.js`。
- CSP 以严格策略为目标，不依赖长期 `unsafe-inline` 或 `unsafe-eval`。

## 后果

- 旧 `form_snippet.html`、`table_block.html`、`file_uploader.html`、旧 `partials/*sidebar*`、旧 `core/config/menus*.yml` 不再可用。
- 新 app 必须优先使用页面级 `{% partialdef %}` 做 HTMX 局部响应，跨页面复用才进入 `components/`。
- Tailwind/Iconify/DaisyUI 类不得动态拼接，新增样式类后必须运行 CSS 构建。
