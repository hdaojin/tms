---
description: "Use when editing Django Python files, including models, views, forms, tables, urls, tests, permissions, file uploads, PDF preview, and app scaffolding in TMS."
name: "TMS Django Backend"
applyTo: "**/*.py"
---

# TMS Django Backend Guidelines

- 从项目根目录运行 Python 和 Django 命令，统一使用 `uv`；测试优先跑受影响 app，而不是默认全量测试。
- 认证用户保持 Django 默认 `auth.User`，扩展字段沿用 [accounts/models.py](../../accounts/models.py)；不要引入自定义 User 模型。
- 角色名、上传目录、允许扩展名、大小限制统一复用 [core/constants.py](../../core/constants.py)；不要在业务代码里硬编码。
- 新建类视图时，优先组合 [core/utils/mixins.py](../../core/utils/mixins.py) 中的 `TitleMixin` 与最小必要权限 mixin。常用选择是 `PermissionRequiredMixin`、`OwnerRequiredMixin`、`CrossGroupAccessMixin`、`SuperuserRequiredMixin`。
- 列表页优先使用 `django-tables2` 的 `SingleTableView`，并复用 [core/utils/tables.py](../../core/utils/tables.py) 中的 `BaseTable`、`BaseDateColumn`、`BaseDateTimeColumn`、`ActionsColumn`。
- 表单优先继承 [core/utils/forms.py](../../core/utils/forms.py) 中的 `StyledFormMixin`，保持 DaisyUI 字段类名一致。
- 展示用户时统一使用 `user.display_name` 或 `user.full_info`，不要回退到分散的姓名拼接逻辑。
- 带文件字段的模型优先复用 [core/utils/signals.py](../../core/utils/signals.py) 的清理信号；PDF 内联预览优先复用 [core/utils/pdf_response.py](../../core/utils/pdf_response.py) 的 `create_pdf_preview_view`。
- 需要审核的记录遵循 `PENDING`、`APPROVED`、`REJECTED` 状态流，并按角色限制 queryset。
- 新增可导航功能时，补齐 app 内 `menus.yml`、[core/config/menus](../../core/config/menus/) 菜单片段、`app_name` 命名空间和 `<app>:<model>_<action>` URL 命名。
- 文案、`verbose_name`、校验错误和帮助文本默认使用中文，并遵循 `zh-hans` 本地化环境。
