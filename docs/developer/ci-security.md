# CI 安全检查

- SQLite 保留全量回归。PostgreSQL 17 作业使用独立临时库，应用测试账号可创建 pytest 测试库，不具备超级用户权限。该作业覆盖账户权限和密码重置、AI 原地更名、训练发布和事务回滚。
- CI 用模拟的 HTTPS 配置运行 `manage.py check --deploy --fail-level WARNING`。生产发布仍由 `tms-deploy` 用真实部署配置运行 `check --deploy`。代理结束 TLS 时，应核对 HTTPS 转发头由代理覆盖、HTTP 跳转及安全 Cookie；CI 不能证明这些现场配置正确。CI 模拟 HSTS 子域及 preload；生产只在确认所有相关子域永久支持 HTTPS 后，才启用 `includeSubDomains` 或申请预加载。生产仅出现对应警告时应记录适用范围及决策。
- Python 审计运行 `uv --preview-features audit-command audit --frozen --no-dev --python-version 3.13 --python-platform linux`，仅扫描锁定的 Linux 生产依赖，使用公开 OSV 服务。依赖 PR、每周计划和人工触发均可执行。发现漏洞或网络错误时保留失败；若确认误报，记录公告编号、不受影响的理由、负责人及到期日，再讨论范围最小的临时例外。
- Django 版本限定在 6 系列；AI 调用使用 LiteLLM Core 1.109 系列，服务端依赖其 HTTP 适配层。放宽边界前核对兼容性，运行 Django 检查、迁移检查与 AI transport 回归，再更新 lockfile。
- 启用 Samba 时用 `visudo -c` 检查 sudoers，并用 `sudo -l -U <服务账号>` 核对授权。仅允许业务实际使用的固定路径和参数，不授予通用 shell 或 `ALL`。保持默认 `SAMBA_INTEGRATION_ENABLED=False`；CI 用 mock 核对外部命令参数。
