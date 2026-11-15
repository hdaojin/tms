# TMS 代码审阅整改记录

本地 `develop` 基准为 `44220c45e015f03ea4e56cefc15c8678ba6b217c`；远端的 [失败 CI](https://github.com/hdaojin/tms/actions/runs/43575203618) 对应 `81c4a67`。开工时只有用户提供的整改计划尚未跟踪。未提交、推送、部署或改动 GitHub 设置。

| 原 CI 失败 | 数量 | 处理 |
| --- | ---: | --- |
| accounts | 6 | 真实姓名及未填写占位，列表按展示姓名定位行，同时检查账号不外露 |
| assessments | 1 | 从日期和时间的独立元素核对上海时区格式 |
| core | 2 | 使用现有导航与授权，确认训练日志列表入口可见、已移除的新增入口不出现 |
| feedback | 2 | 验证筛选控件、HTMX 行为和处理人真实姓名 |
| training 周期详情、成员 | 3 | 正反向姓名可见性；有效姓名夹具使现有参数、预览、确认及事务回滚路径实际执行 |
| training 排班、日志 | 2 | 教练姓名不含账号；验证 PDF 真实预览地址、下载、签名失配与对象授权 |
| training 计划人员 | 2 | 使用有效真实姓名，核对拼音分页、账号不作为搜索字段、同名备注不足和正常提交 |
| worldskills_forum | 1 | 验证共享搜索控件、HTMX 触发与带参数的响应 |

以上 19 项均为测试断言或夹具与现行行为不一致；未因此改动业务代码。Windows 沙箱中的评测写入另受 NTFS 硬链接限制。评测测试在内存 SQLite 和隔离媒体目录中解除沙箱限制后通过。

代码变更集中在 `notes/html.py`、`notes/utils.py`、`notes/views.py`、`core/file_preview.py`、`core/utils/markdown.py`、`samba/samba_sync.py`，分别落实笔记 HTML 清洗、附件响应保护、渲染失败提示和 Samba 参数校验。测试另覆盖 AI 并发名额和超时释放、AI 更名后的事务回滚、训练发布提交时的权限与状态复查。未新增数据库迁移。

CI 配置修改位于 `.github/workflows/ci.yml`、`.github/workflows/python-dependency-audit.yml` 和 `.github/dependabot.yml`。部署及兼容范围见 [CI 安全检查](../../developer/ci-security.md)，笔记安全边界见 [笔记渲染与附件安全](../../developer/notes-rendering.md)，训练业务见 [状态决策表](../../design/training-publication-decisions.md)，旧分析移至 [历史归档](../../archive/AI_Optimization_suggestions.md)。

其余变更文件：

- P0 测试：`accounts/tests.py`、`assessments/tests.py`、`core/tests.py`、`feedback/tests/test_views.py`、`training/test_cycle_details.py`、`training/test_cycle_members.py`、`training/test_entry_refinement.py`、`training/test_log_workflow.py`、`training/test_plan_people.py`、`worldskills_forum/tests/test_search_and_unread.py`。
- 新增覆盖：`notes/tests.py`、`ai/test_app_rename.py`、`ai/test_llm.py`、`training/test_plan_publish.py`、`samba/test_command_boundary.py`。
- 配置与文档：`.env.example`、`README.md`、`pyproject.toml`、`uv.lock`、`docs/developer/deploy-tms-production.md`。生成的 CSS 与当前 HEAD 一致。

Python 审计发现 Soup Sieve 3.0.4 的 [CVE-2026-126190](https://nvd.nist.gov/vuln/detail/CVE-2026-126190)；锁文件定向更新为 4.1.1 后，86 个 Linux 生产依赖的复扫未报告已知漏洞。前端生产依赖审计无发现。Prettier 报告 4 个未修改文件有原有差异：`scripts/test-pdf-preview.mjs`、`scripts/test-plan-staff.mjs`、`scripts/test-training-entries.mjs`、`static/css/main.css`。

验证结果：

- `uv sync --frozen`、`uv lock --check`、`uv run ruff check .`、Django system check、模拟生产环境的 `check --deploy --fail-level WARNING`、迁移漂移检查及空 SQLite 迁移通过。
- 本地 SQLite 全量回归（`pytest -m "not document_pdf_native"`）：1,193 项通过，45 项跳过，7 项按原生 PDF 标记排除，240 项子测试通过。该轮在允许 NTFS 硬链接的环境运行，使用独立临时目录与测试用快速密码哈希。其后笔记白名单补充保留提示块和复选框，`uv run pytest notes` 复测 31 项通过，2 项因 Windows 不能创建符号链接而跳过。
- `npm ci` 在隔离目录安装锁定依赖，`npm run build:frontend` 及 `npm run test:frontend` 通过。53 项前端测试通过；重复构建 CSS 的哈希一致，且与当前 HEAD 相同。工作流和 Dependabot 的 YAML 已在本地解析校验。

发布前仍需在 PR 的 GitHub Actions 运行 PostgreSQL 17 和 Debian 13 原生 PDF 作业，核对全套状态检查，再按 [GitHub 人工核查清单](tms-review-github-checklist.md) 处理分支保护、历史分支和 Issue。
