# ADR 0003：权限授权架构

- 状态：已接受
- 日期：2026-08-14

## 背景

试运行阶段的权限包由 Python 常量声明，Group/User 的原生权限既被当作输入又被当作展开结果。Catalog 调整后，旧派生权限可能被误认为显式授权而无法撤销；固定 Group 名称和 codename 也混入了业务授权判断。

## 决策

1. Django Permission 是运行时唯一授权事实来源；View、下载端点和模板不直接判断权限包或 Group 名称。
2. Permission Bundle 是 `core/config/permission_bundles.yml` 中受版本控制的部署期静态 Catalog。它不提供 Admin 在线编辑、嵌套或热加载。
3. `selected_permission_bundles` 与 Profile 上独立保存的 `explicit_permissions` 是授权配置来源；`Group.permissions` 和 `User.user_permissions` 只是两者并集的物化投影。
4. `core.permissions` 负责严格加载、校验和展开 Catalog；`accounts.services.permission_assignments` 负责事务化写入 Group/User 授权与投影。
5. 对象范围由 selector/policy 收窄。基础 Permission 表示默认/本人范围，`*_all` Permission 只扩大范围。
6. Group 名称和 `GroupProfile.codename` 仅用于显示或 Samba 等技术集成，不参与业务授权。
7. 本次采用授权配置硬切换：清空旧 Bundle、显式权限与原生投影，不迁移旧 code；保留 User、Group、membership、技术映射和业务数据。

## 配置边界

- `.env` / settings：部署、安全、路径和基础设施配置。
- `core/config/*.yml`：非敏感、版本化、随部署生效的静态 Catalog。
- `SiteConfig`：站点管理员在线维护的站点设置。
- 各 APP 模型：业务数据和业务配置。
- fixtures：可选初始化数据，不是运行时配置。
- constants：代码不变量，不保存站点可配置值。

## 后果

Catalog 缺失、重复、未知 code、无效或模糊 Permission 都会在 system check 或同步时失败。Catalog 更新后需先检查，再运行 reconciliation 的 dry-run 与 `--apply`，最后重启应用进程。管理员不能直接编辑原生权限投影。
