# AI APP 更名与数据库恢复

旧版 TMS 使用 Django 标签 `ai_models`，新版使用 `ai`。现有数据库需要先原地转换身份，再运行新版正常迁移。浏览器入口继续使用 `/ai-models/`。

## 准备

1. 记录旧版发布标识、数据库版本及 schema、Web 和训练日志生成 worker 的服务配置。
2. 使用旧版应用确认数据库已完成当前迁移。基线应用提交为 `15a0777`，AI 历史到 `0005_model_share_audience`，训练日志相关迁移至少包含 `0026_training_log_ai_workflow`。
3. 准备 PostgreSQL 全库备份以及对应的公开上传、私有上传和原 `AI_MODEL_ENCRYPTION_KEY` 安全备份。将数据库备份恢复到隔离库，完成以下预检、转换、验证和旧版恢复演练。
4. 盘点保存的 API 地址。公开目标默认走 HTTPS 443。经管理员批准的内网或非默认端口配置到 `AI_TRUSTED_ENDPOINTS`，以逗号分隔，例如 `http://ollama.intra.example:11434`。按实际 scheme、主机、端口精确匹配，部署防火墙仍应限制出站权限。
5. 在维护窗口停止 Web、训练日志生成 worker 及其他写入进程，保留最终备份。将新版管理命令指向计划切换的数据库，核对连接环境和原加密密钥。

## 预检和转换

更新稳定部署入口后，使用 `tms-update plan --revision develop` 和 `tms-update apply <plan-id> --confirm-sha <完整 SHA>`。部署预检识别旧版数据库后，会在停机期间先执行原地转换，再运行 Django 迁移。原加密密钥取自运行环境，数据库转换使用迁移账号。转换后的发布失败会保留维护状态，需按下文恢复流程处理。

命令核对历史、四张实体表和两张共享中间表、ContentType、外键及权限身份，逐条检查旧密文可由原密钥解密。在一个事务中重命名表及 app 标签，迁移用户与角色的两项 AI 权限包编码。表数据、训练生成记录、权限及授权关系逐表比对，保留原主键。PostgreSQL 原有索引、约束和附属序列名称随表保留，依赖由数据库维持。预检报告包含表及统计、ContentType 和权限 ID，密文及明文仅用于进程内校验。

新建空数据库直接运行正常 migrate。SQLite 支持本地演练。

### 本地已出现迁移历史不一致

若 `migrate` 或 `migrate --plan` 报告已应用的 `training.0026_training_log_ai_workflow` 缺少 `ai.0004_provider_model_defaults`，先确认当前连接的是原有开发库。关闭本地 Web 和 worker，并备份该 SQLite 数据库。然后从仓库根目录依次运行：

```powershell
uv run manage.py migrate_ai_app_label --dry-run
uv run manage.py migrate_ai_app_label --apply
uv run manage.py migrate --noinput
uv run manage.py migrate --plan
```

只读预检通过后再执行 `--apply`。转换会把原先已应用的 `ai_models` 迁移历史改为 `ai`，使训练日志迁移的依赖重新对应。生产环境按上面的停机切换流程执行。

## 验证和恢复

- 复查用户与组的模型权限、原默认模型、定向共享、历史训练日志与生成任务关联。
- 启动新版 Web 和训练日志生成 worker，检查服务状态。真实模型连接测试由有权限的用户主动发起。
- 如需恢复，停掉新版进程，在隔离或维护窗口环境使用原备份恢复旧库，恢复配套密钥、媒体目录和原发布代码，再启动旧版 Web 和 worker。验证权限、模型关联及文档访问，保留数据库和应用日志供排查。

## 本地演练记录

2026-11-14 使用 PostgreSQL 17.11 和旧版提交 `15a0777` 创建隔离旧库。写入合成凭据、默认模型、定向共享、直接授权、角色授权、权限包及历史训练生成任务。依次通过预检、原地转换、新版迁移和重复预检。使用 `pg_dump -Fc` 及 `pg_restore` 恢复独立旧库，再用旧版代码检查历史生成关联和原密钥解密。自动化迁移测试分别在 SQLite 和 PostgreSQL 运行。上线前仍需在脱敏实际副本上重复演练。
