# `core/config` 配置边界

本目录只保存非敏感、受版本控制、随部署生效的静态 Catalog。

- `navigation.yml`：导航结构和每个叶子入口的访问模式。
- `permission_bundles.yml`：站点管理员可分配的业务权限包目录；修改文件需要代码评审和部署。

配置所有权分为六类：`.env` / `tmsproject/settings.py` 管部署与敏感设置；本目录管理静态 Catalog；`SiteConfig` 管 Django Admin 在线站点设置；各 APP 模型管可运营维护的业务目录和业务数据；`bootstrap_tms` 显式创建缺失的生产出厂目录；`core/constants.py` 只保存代码不变量。Fixture 仅用于测试、演示或显式数据交换。

Catalog 不支持 Admin 在线编辑或热加载。变更权限包后执行：

```powershell
uv run manage.py check
uv run manage.py reconcile_permission_assignments
uv run manage.py reconcile_permission_assignments --apply
```

确认同步结果后重启应用进程。Fixture 和 Bootstrap 都不是运行时配置来源；Bootstrap 不应在请求、应用启动或普通读取路径中隐式执行，也不应用于恢复旧角色或旧授权。
