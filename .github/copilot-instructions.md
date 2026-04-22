# TMS 工作区说明

## 技术栈

- Django 6、Python 3.13、django-tables2、HTMX、Alpine.js、Tailwind CSS 4、DaisyUI 5、Iconify。
- Python 命令统一使用 `uv`，前端命令使用 `npm`。
- 本地化默认是 `zh-hans` 和 `Asia/Shanghai`；`verbose_name`、表单错误和页面文案使用中文。

## 运行与验证

- 所有 Django 命令和脚本都从项目根目录运行；`.env` 中 `DATABASE_URL` 使用相对路径 `sqlite:///db.sqlite3`，如果从子目录启动脚本，可能连到错误的 SQLite 文件。
- 首次设置：`uv sync`、`npm install`、复制 `.env.example` 到 `.env`、`uv run manage.py migrate`、`uv run manage.py loaddata core/default accounts/default competitions/default conduct/default`。
- 常用开发命令：`uv run manage.py runserver`、`npm run watch:css`、`npm run build:css`。
- 运行测试时优先执行受影响 app 的测试，例如 `uv run manage.py test meeting`；不要默认跑全量测试。

## 架构

- 这是 Django 单体应用。认证用户使用 Django 默认 `auth.User`，扩展字段在 [accounts/models.py](../accounts/models.py)；不要引入自定义 User 模型。
- 角色常量、上传目录、扩展名和大小限制统一定义在 [core/constants.py](../core/constants.py)；不要硬编码组名或上传规则。
- 全站默认要求登录。公开页面必须显式使用 `@login_not_required`。中间件顺序在 [tmsproject/settings.py](../tmsproject/settings.py) 很敏感：`HtmxMiddleware` 在最前，`LoginRequiredMiddleware` 紧跟认证中间件之后，`FlatpageFallbackMiddleware` 在最后。
- 站点配置和菜单通过上下文处理器注入，入口见 [core/utils/context_processors.py](../core/utils/context_processors.py) 和 [core/config/menus.yml](../core/config/menus.yml)。
- `demo` 应用只在 `DEBUG=True` 时启用；不要让正式业务代码依赖它。说明见 [demo/README.md](../demo/README.md)。

## 代码约定

- 新建类视图时，优先组合 [core/utils/mixins.py](../core/utils/mixins.py) 中的 `TitleMixin` 与合适的权限 mixin；常用选择是 `PermissionRequiredMixin`、`OwnerRequiredMixin`、`CrossGroupAccessMixin`、`SuperuserRequiredMixin`。
- 列表页优先使用 `django-tables2` 的 `SingleTableView`，并复用 [core/utils/tables.py](../core/utils/tables.py) 中的 `BaseTable`、`BaseDateColumn`、`ActionsColumn`。
- 表单优先继承 [core/utils/forms.py](../core/utils/forms.py) 中的 `StyledFormMixin`，保持 DaisyUI 类名一致。
- 模板、表格和业务代码展示用户时，统一使用 `user.display_name` 或 `user.full_info`。
- 带文件字段的模型应复用 [core/utils/signals.py](../core/utils/signals.py) 的清理信号；PDF 内嵌预览优先使用 [core/utils/pdf_response.py](../core/utils/pdf_response.py) 中的 `create_pdf_preview_view`。
- 需要审核的记录遵循 `PENDING`、`APPROVED`、`REJECTED` 状态流，并按角色限制查询集。
- 新 app 需要补齐 app 内 `menus.yml`、[core/config/menus](../core/config/menus/) 下的菜单片段、`app_name` 命名空间和 `<app>:<model>_<action>` URL 命名。

## 模板与前端

- 复用 [templates/base.html](../templates/base.html) 的 block 结构；HTMX 的 CSRF headers 已全局配置。
- 图标统一使用 `icon-[tabler--...]` 语法；优先复用 [templates/components](../templates/components/) 下的组件模板。
- 保持现有 DaisyUI 和 Tailwind 风格，不要引入与现有模板体系冲突的新组件约定。

## 参考文档

- 项目启动、依赖和基础开发流程见 [README.md](../README.md)。
- `demo` 应用的用途和限制见 [demo/README.md](../demo/README.md)。

## AI 代理文档维护要求

- 只要修改了某个 APP 的用户可见功能，就必须同步检查并更新对应的用户手册文档。
- “用户可见功能”包括但不限于：页面入口、菜单结构、权限要求、字段含义、录入流程、页面文案、状态流、导入导出规则、附件处理方式。
- 如果当前 APP 已有用户手册，至少同步更新受影响章节；如果当前变更会影响角色边界或整体流程，还要同步更新总览页。
- 本仓库的用户手册当前放在 `docs/user-manual/` 下；新增或重构功能时，不要只改代码不改文档。