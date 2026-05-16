# TMS Copilot Instructions

本仓库以 repo-root `AGENTS.md` 为项目规则的权威来源。Copilot 生成或修改代码时，必须优先遵循 `AGENTS.md`；本文件只保留 Copilot 工作时最容易遗漏的摘要。

## 必读

- 先阅读 `AGENTS.md`。
- 需要命令、部署或环境细节时阅读 `README.md`。
- 用户可见行为变化时，检查并更新 `docs/user-manual/`。

## 快速规则

- Django 命令统一从仓库根目录运行，例如 `uv run manage.py check`、`uv run manage.py test <app>`。
- 使用 Django 默认 `auth.User`，不要引入自定义 User 模型。
- 菜单只维护在 `core/config/menus/*.yml`；分组维护在 `core/config/menus.yml`。
- 文件上传规则复用 `core.uploads`；多文件表单使用 `core.forms.fields.MultipleFileField` / `MultipleFileInput`。
- 私有上传使用 `settings.PRIVATE_MEDIA_ROOT` 和 `PrivateMediaStorage`，不要在迁移中写入本机绝对路径。
- 新增或修改页面时复用 `TitleMixin`、`StyledFormMixin`、`BaseTable`、`ActionsColumn` 和现有模板组件。
- 用户可见文案、模型名、表单标签、校验错误和文档使用中文。
- 不要读取、打印或提交 `.env` 密钥；AI API 密钥只能通过后端加密服务处理。

## 验证

- 优先运行受影响 app 的测试：`uv run manage.py test <app>`。
- 跨 app 或核心规则变更时运行更广的测试。
- 模板引入新的 Tailwind/Iconify 类后，运行 `npm run build:css` 并提交生成的 `static/css/output.css`。
