# TMS 整改后的 GitHub 人工核查清单

2026-11-15 核对：远端默认分支是 `develop`，其提交仍为 `81c4a67`。以下内容只作为仓库所有者的操作建议。

1. 待本轮变更通过 PR 的完整 CI 后，在仓库设置中复核 `develop` 的分支保护与 Rulesets，再设置必需检查。当前读取接口受限，历史「未保护」结论不能作为设置现状。以首个成功的 PR 实际上报名称为准，预期包括 `Django checks and tests`、`PostgreSQL migrations and transaction tests`、`Document PDF rendering on Debian 13`、`Frontend build`。Python 审计工作流只在依赖相关 PR、每周或手动触发，不设为所有 PR 的必需检查。
2. 优先以功能分支和 PR 合并。单人维护时可要求状态检查而不强制其他人审批。生产发布前仍核对实际版本和部署预检。
3. 先看分支比较结果和关联 PR；有唯一提交的分支先确认是否需归档或摘取，再决定是否删除。勿批量删除。

| 远端分支 | 末次提交日期 | 未包含在本地基准 `44220c4` 的提交 / 非等价补丁 | 建议 |
| --- | --- | ---: | --- |
| `Manage-menus-in-Admin` | 2025-09-05 | 60 / 0 | 现行导航由 YAML 管理，确认无需保留独立历史后可归档 |
| `menus-two-method` | 2025-09-01 | 54 / 0 | 同上，确认关联 PR 后可归档 |
| `copilot/vscode1756800415521` | 2025-09-02 | 60 / 3 | 先审阅三个非等价补丁 |
| `notes` | 2025-03-30 | 20 / 2 | 保留至确认两个遗留变更是否仍有价值 |
| `chore/hardening-ci` | 2026-06-16 | 24 / 24 | 先与本轮 CI 加固对照 |
| `chore/hardening-ci-clean` | 2026-06-16 | 18 / 18 | 与同类分支合并评估 |
| `feature/list-filtering` | 2026-08-17 | 26 / 26 | 与现用统一列表筛选逐项比较 |
| `refactor/review-optimizations` | 2026-08-13 | 1 / 1 | 复核唯一补丁，不直接删除 |
| `codex/fix-training-task-publish-lock` | 2026-11-09 | 0 / 0 | 已包含，可按需要清理 |
| `feature/list-filter-toolbar-standardization` | 2026-11-11 | 0 / 0 | 已包含，可按需要清理 |
| `docs/list-ui-standardization-plan` | 2026-11-11 | 1 / 1 | 检查独立文档提交后再决定 |

提交数取 `git rev-list --right-only --count HEAD...origin/<branch>`；补丁数去除 merge 和等价补丁。远端 SHA 与用于统计的本地跟踪引用一致，日期指末次提交日期。

| 仍打开的 Issue | 建议 | 依据 |
| --- | --- | --- |
| [#29 选手就业](https://github.com/hdaojin/tms/issues/29) | 保留待定 | 当前周期成员和资料维护未替代就业登记 |
| [#28 Nginx 上传权限](https://github.com/hdaojin/tms/issues/28) | 复核后关闭 | 当前部署由 Caddy 提供静态内容，私有上传由权限端点提供；若另有 Nginx 部署，另记现场事项 |
| [#27 课件与习题集](https://github.com/hdaojin/tms/issues/27) | 设里程碑 | 教学笔记和考核附件已覆盖部分资料展示，习题编排与复用仍需定义 |
| [#26 收藏网址](https://github.com/hdaojin/tms/issues/26) | 合并至 #23 | 都涉及用户保存或访问常用链接，先统一使用场景 |
| [#23 首页常用网址](https://github.com/hdaojin/tms/issues/23) | 保留待定 | 首页现有导航不是用户收藏 |
| [#22 在线写日志](https://github.com/hdaojin/tms/issues/22) | 验收后关闭 | 已有 AI 辅助草稿、用户确认与正式日志归档 |
| [#21 上传优化](https://github.com/hdaojin/tms/issues/21) | 验收后关闭 | 已有共用上传组件、服务端校验及私有下载；有剩余场景时另立具体任务 |
| [#20 资产管理](https://github.com/hdaojin/tms/issues/20) | 保留待定 | 现有业务附件不提供设备生命周期管理 |
| [#18 重要事件提醒](https://github.com/hdaojin/tms/issues/18) | 明确剩余需求 | 已有站内公告及倒计时；主动提醒的渠道与触发还需确认 |
| [#16 成绩管理](https://github.com/hdaojin/tms/issues/16) | 验收后关闭或拆分 | 已有考核评分及最终成绩；跨赛事汇总若仍需要，单独界定 |
| [#12 竞赛人员角色](https://github.com/hdaojin/tms/issues/12) | 验收后关闭或拆分 | 已有赛项经理等赛事角色目录；合作交流管理若仍需要，单独立项 |
| [#4 技能点汇总](https://github.com/hdaojin/tms/issues/4) | 复核未完搜索项 | 已有技能树、考点和技能分析；确认旧需求指哪个列表的动态筛选 |
| [#2 周报](https://github.com/hdaojin/tms/issues/2) | 拆为待定里程碑 | 日计划、任务执行与 Excel 已覆盖一部分；周总结仍需明确，自动调整计划与当前领域约束冲突 |
| [#1 违纪扣分与匿名举报](https://github.com/hdaojin/tms/issues/1) | 拆分验收 | 已有奖惩记录和匿名反馈，需明确是否还要求专门的举报处理流程 |
