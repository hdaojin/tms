---
description: "Use when editing Django tests, TestCase classes, app-level tests.py files, permission tests, view tests, model tests, and regression tests in TMS."
name: "TMS Django Tests"
applyTo: "**/{tests.py,tests/**/*.py}"
---

# TMS Django Test Guidelines

- 测试命令统一从项目根目录运行，并优先执行受影响 app 的测试，例如 `uv run manage.py test meeting`；不要默认跑全量测试。
- 优先沿用 Django 内置 `TestCase` 与现有 app 的 `tests.py` 组织方式；如果 app 里只有一个 `tests.py`，先在原文件补测试，而不是无端拆出复杂测试目录。
- 小规模测试数据优先在 `setUp()` 中显式创建，沿用 `get_user_model()`、`User.objects.create_user()`、`Group.objects.create()` 这类 Django 原生写法；不要先引入 pytest 或工厂库。
- 角色、组名、状态值、上传限制等测试数据应复用 [core/constants.py](../../core/constants.py) 或模型常量，不要在测试里再硬编码一套规则。
- 修改模型或业务流程时，至少补一条覆盖核心行为的回归测试；这个仓库现有有效样板可参考 [accounts/tests.py](../../accounts/tests.py)。
- 涉及审核或汇总逻辑时，重点验证状态流转和副作用，例如 `PENDING` 到 `APPROVED` 后的汇总更新、权限变化或关联记录写入。
- 涉及视图时，优先覆盖登录要求、权限限制、成功路径和关键上下文/重定向；因为全站默认要求登录，公开页面需要显式验证其例外行为。
- 涉及用户与角色场景时，测试里保持教练、选手、超管的访问边界清晰，避免把跨组访问和所有者访问混在一个测试里。
- 测试名应描述行为而不是实现细节；可以沿用 `test_<behavior>` 风格，并在类或方法 docstring 中用中文说明业务意图。
- 只为当前改动补最小必要测试，不要顺手重写整个 app 的测试结构；如果当前 app 还没有有效测试，优先补最核心的模型或视图回归。
