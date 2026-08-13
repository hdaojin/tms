# TMS Copilot Instructions

本文件只作为 Copilot 的入口提示，不维护第二套 TMS 开发规范。

## 必读顺序

1. **先读仓库根目录 `AGENTS.md`**：工程规则、分层边界、前端约束、验证和安全要求均以它为准。
2. 涉及业务模型、统计口径或术语时读 `CONTEXT.md`，并检查相关 `docs/adr/`。
3. 环境、安装、部署和命令细节读 `README.md`。
4. 用户可见功能变化检查 `docs/user-manual/`。

## 最容易遗漏的当前入口

- 当前领域主链路 APP 是 `standards`、`events`、`archives`、`training`、`examcontent`、`scoring`、`knowledge`；不要按旧 `assessments/competitions/skills/traininglogs` 结构生成代码。
- 导航唯一配置入口是 `core/config/navigation.yml`；不要恢复旧 `core/config/menus/*.yml`。
- 新业务页优先使用 `templates/layouts/*`、`templates/common/` 和 `templates/components/`，不要默认从旧 `templates/base.html` 模式复制页面。
- 复杂跨模型写流程优先放 service，复杂复用查询/统计优先放 selector；view 保持 HTTP 编排职责。
- 新授权优先 Django permission / `core.permissions` 权限包；新角色判断不要依赖可变 `Group.name`。
- Tailwind/Iconify class 保持完整静态字符串；项目使用 Tailwind 4、DaisyUI 5、`@alpinejs/csp` 和 `@iconify/tailwind4`。

## 最低验证

优先运行受影响测试，并与 CI 对齐：Ruff、Django check、migration drift check、pytest；模板/CSS/Iconify class 有变化时运行 `npm run build:css`。

具体命令和何时运行全量测试，以 `AGENTS.md` 为准。
