# TMS 备份恢复演练手册

> 适用对象：TMS 生产环境  
> 当前基线：Django 6、Python 3.13、PostgreSQL 17，使用 `MEDIA_ROOT`、`PRIVATE_MEDIA_ROOT`、可独立配置的 `NOTES_ROOT`。  
> 配套脚本：`backup_tms.sh`与 `restore_tms.sh`。

---

## 1. 目的

备份文件存在，并不代表备份一定可恢复。

TMS 的一次完整恢复至少涉及：

1. PostgreSQL 业务数据库；
2. PostgreSQL roles / tablespaces 等全局对象；
3. 公共上传文件 `MEDIA_ROOT`；
4. 私有业务文件 `PRIVATE_MEDIA_ROOT`；
5. 教学笔记 `NOTES_ROOT`；
6. TMS 对应代码版本与依赖锁文件；
7. `.env` 等运行配置；
8. 如果启用了 Samba，还涉及操作系统用户、组、Samba passdb 与 `smb.conf`。

因此，恢复演练的目标不是“`pg_restore` 没报错”，而是证明：

> **某一份备份能够在隔离环境中恢复出一个可启动、可登录、可查询历史业务数据、可访问业务附件的 TMS。**

---

## 2. 演练原则

### 2.1 默认只做隔离恢复

日常恢复演练禁止直接覆盖：

- 正式 `tms` 数据库；
- 正式 `media/`；
- 正式 `media-private/`；
- 正式 `.env`；
- Samba / Nginx / systemd 配置。

`restore_tms.sh` 默认使用 `drill` 模式，恢复到：

```text
PostgreSQL:
    <原数据库>_drill_<时间戳>

文件:
    /var/tmp/tms-restore/<backup-name>-<时间戳>/
```

只有真正发生灾难恢复时，才使用：

```bash
--mode production --force
```

### 2.2 先校验，再恢复

每次演练都必须先验证：

```bash
sha256sum --check SHA256SUMS
```

`restore_tms.sh` 会自动执行该检查。

任何一个文件校验失败，都应将这一份备份判定为 **不可直接用于恢复**，先调查原因，不要继续正式恢复。

### 2.3 数据库恢复成功不等于 TMS 恢复成功

PostgreSQL `pg_dump` 可以生成数据库内部一致的逻辑备份，但 PostgreSQL 数据库与 `media` / `media-private` 文件系统并不是同一个事务。

因此完整演练还必须验证：

- 数据库中的附件记录存在；
- 对应物理文件存在；
- Django 能实际读取/下载文件；
- 私有文件仍经过权限控制。

---

## 3. 建议演练频率

至少在以下时间执行恢复演练：

- TMS 核心领域模型大规模重构前；
- 大规模 migration / 数据迁移前；
- PostgreSQL 主版本升级前；
- 服务器迁移前；
- 备份脚本发生重要修改后；
- 日常生产建议至少每季度抽取一份备份做完整恢复演练。

对于当前这次 TMS 核心重构，建议把重构前最后一份通过恢复演练的备份定义为：

```text
pre-core-refactor baseline
```

并长期保留。

---

# 4. 生成重构前基线备份

首先进入维护窗口，停止会修改数据的 TMS Web 请求和后台任务。

具体服务名以生产服务器实际 systemd 配置为准，例如：

```bash
sudo systemctl stop tms
```

然后执行完整备份，并启用备份脚本自身的 PostgreSQL 恢复验证：

```bash
sudo VERIFY_RESTORE=1 ./backup_tms.sh
```

如果服务器上仍使用旧文件名：

```bash
sudo VERIFY_RESTORE=1 ./tms-backup-v2.sh
```

确认终端至少出现：

```text
完整 PostgreSQL 恢复验证通过
私有媒体：.../media-private.tar.gz
TMS 备份完成
```

然后重新开放旧 TMS：

```bash
sudo systemctl start tms
```

---

# 5. 恢复演练

假设备份目录为：

```text
/var/backups/tms/20260907T120000+0800-tms-tms
```

## 5.1 先做 dry-run

```bash
sudo ./restore_tms.sh \
    --backup /var/backups/tms/20260907T120000+0800-tms-tms \
    --dry-run
```

检查计划中的：

```text
原数据库
目标数据库
MEDIA target
PRIVATE MEDIA target
NOTES target
```

确保所有目标都是演练环境，不是生产路径。

---

## 5.2 执行隔离恢复

```bash
sudo ./restore_tms.sh \
    --backup /var/backups/tms/20260907T120000+0800-tms-tms
```

脚本会要求输入：

```text
RESTORE
```

然后执行：

```text
SHA256 校验
    ↓
pg_restore archive 检查
    ↓
解压源码快照
    ↓
创建新的 drill 数据库
    ↓
pg_restore
    ↓
ANALYZE
    ↓
恢复 media
    ↓
恢复 media-private
    ↓
必要时恢复独立 NOTES_ROOT
    ↓
生成 restore-report.txt
```

正常情况下，不会修改生产数据库和生产媒体目录。

---

# 6. 数据库层验证

恢复完成后，终端会给出演练数据库名，例如：

```text
tms_drill_20260907143000
```

首先检查数据库：

```bash
sudo -u postgres psql -d tms_drill_20260907143000
```

建议至少检查：

```sql
SELECT COUNT(*) FROM django_migrations;
SELECT COUNT(*) FROM auth_user;
SELECT COUNT(*) FROM django_content_type;
```

然后根据 TMS 当前核心数据抽查业务表。

重点不是固定某个数量，而是确认：

- 表存在；
- 历史记录不是空的；
- 关键业务数据数量与生产环境在同一合理数量级；
- migration 历史完整。

退出：

```text
\q
```

---

# 7. 文件层验证

演练目录大致为：

```text
/var/tmp/tms-restore/<backup-name>-<timestamp>/
└── project/
    ├── manage.py
    ├── ...
    ├── media/
    └── media-private/
        └── notes/
```

如果生产环境的 `NOTES_ROOT` 被配置在 `PRIVATE_MEDIA_ROOT` 之外，则还会看到独立恢复目录：

```text
project/notes-restored/
```

检查：

```bash
du -sh project/media
du -sh project/media-private

find project/media -type f | wc -l
find project/media-private -type f | wc -l
```

并随机抽查 PDF、Word、XLSX、图片等文件可以正常打开。

---

# 8. Django 应用级 Smoke Test

这是恢复演练最重要的一步。

## 8.1 不要直接复制生产 `.env` 后启动

备份中的：

```text
config/.env
```

仍然指向原生产数据库和原生产文件路径。

如果直接复制后执行：

```bash
manage.py migrate
```

可能误操作正式数据库。

因此，演练必须创建一个 **专用 `.env`**。

---

## 8.2 创建演练 `.env`

进入恢复后的项目：

```bash
cd /var/tmp/tms-restore/<本次演练>/project
```

可以把备份 `.env` 作为参考：

```bash
sudo cp \
    /var/backups/tms/<backup>/config/.env \
    .env.drill-reference
```

然后新建：

```bash
sudo editor .env
```

以原 `.env` 为基础，但至少修改：

```dotenv
DEBUG=False

DATABASE_URL=postgres://<TMS数据库用户>:<密码>@127.0.0.1:5432/<drill数据库名>

PRIVATE_MEDIA_ROOT=/var/tmp/tms-restore/<本次演练>/project/media-private

NOTES_ROOT=/var/tmp/tms-restore/<本次演练>/project/media-private/notes
```

如果本次备份存在独立：

```text
project/notes-restored/
```

则：

```dotenv
NOTES_ROOT=/var/tmp/tms-restore/<本次演练>/project/notes-restored
```

`MEDIA_ROOT` 当前由 TMS settings 定义为：

```python
BASE_DIR / "media"
```

恢复脚本已经把公共媒体恢复到：

```text
<演练项目>/media/
```

因此通常不需要额外配置。

### 特别注意

演练 `.env` 中的 `DATABASE_URL` 必须指向：

```text
*_drill_*
```

数据库。

在继续之前建议人工执行：

```bash
grep '^DATABASE_URL=' .env
```

再次确认。

---

## 8.3 使用兼容的 Python 环境

如果是在原生产服务器上演练，可以复用当前生产虚拟环境，例如：

```bash
/srv/tms/.venv/bin/python manage.py check
```

如果是在独立恢复服务器，则根据备份中的：

```text
pyproject.toml
uv.lock
```

安装对应环境：

```bash
uv sync --frozen
```

然后：

```bash
uv run manage.py check
```

---

## 8.4 不要在演练开始时执行 migrate

恢复数据库已经包含当时完整的 migration 状态。

首先只执行：

```bash
python manage.py check
python manage.py showmigrations
```

不要直接：

```bash
python manage.py migrate
```

否则你验证的就不再是“这份备份能否还原当时的 TMS”，而变成了“恢复后再升级到当前代码能否工作”。

如果恢复代码就是备份对应的代码版本，`showmigrations` 应与数据库基本一致。

---

# 9. 浏览器业务验证

启动演练 TMS，例如：

```bash
python manage.py runserver 127.0.0.1:18000
```

建议只绑定：

```text
127.0.0.1
```

不要直接开放外网。

至少验证以下业务。

## 9.1 账户与权限

- 管理员可以登录；
- 普通用户存在；
- Group / Permission 正常；
- 权限受限页面仍然不能越权访问。

## 9.2 标准体系

抽查：

- 技能项目；
- 技术领域；
- Skill；
- 技能树；
- WSOS 映射。

## 9.3 竞赛与考核

抽查：

- Assessment；
- 模块；
- 参与人员；
- 历史考核数据；
- 考核资料。

特别打开至少一个：

```text
media-private/assessments/
```

中的实际文件。

## 9.4 训练与评分

抽查：

- 训练计划；
- TrainingTask；
- TrainingLog；
- 评分标准；
- 评分结果；
- Evidence / Skill 映射。

## 9.5 其他私有附件

随机验证：

- `meetings/`
- `notices/`
- `feedback/`
- `worldskills_forum/`
- `glossary/`
- `behaviors/`

确保：

1. 数据库记录存在；
2. 文件存在；
3. 页面可以正常打开或下载；
4. 未授权用户不能直接访问私有文件。

## 9.6 Notes

如果使用教学笔记：

- Notes 仓库可以列出；
- Markdown 正文正常；
- 图片正常；
- 相对附件正常；
- Mermaid / 代码高亮等页面渲染没有因为路径变化失效。

---

# 10. Git / 代码恢复验证

备份目录中通常包含：

```text
code/tms-source.tar.gz
code/tms.git.bundle
code/git-info.txt
```

`git-info.txt` 用于确认当时生产版本：

```bash
cat code/git-info.txt
```

`git bundle` 可以验证：

```bash
git bundle verify code/tms.git.bundle
```

在真正灾难恢复到新服务器时，可以：

```bash
git clone code/tms.git.bundle tms
```

然后按 `git-info.txt` 中记录的 commit 检出对应版本。

`source.tar.gz` 的意义不同：

- Git bundle 保存已提交历史；
- source tar 保存生产机当时的工作区；
- 如果生产机存在未提交修改，只有 source tar 能完整保留。

因此两者都应该保留。

---

# 11. PostgreSQL globals 验证

正常恢复演练**不要**执行：

```bash
--restore-globals
```

因为 `postgres-globals.sql` 包含 roles / tablespaces，在同一台生产 PostgreSQL 上演练时可能修改真实全局角色。

只有以下场景才考虑恢复 globals：

- 新建的独立 PostgreSQL 恢复服务器；
- 真正灾难恢复；
- PostgreSQL 集群整体重建。

在独立服务器上，可以先 dry-run 阅读：

```bash
less database/postgres-globals.sql
```

确认后：

```bash
sudo ./restore_tms.sh \
    --backup <backup-dir> \
    --mode production \
    --restore-globals \
    --force
```

生产模式下，`pg_restore` 会尽量保留 archive 中的 owner 与 ACL；因此对应 roles 应当先存在。

---

# 12. Samba 恢复边界

TMS 的 Samba 集成会影响：

- Linux user；
- Linux group；
- Samba passdb；
- `/etc/samba/smb.conf`。

这些状态不属于 Django/PostgreSQL 数据库。

备份脚本在 Samba 集成启用时会保存类似：

```text
config/samba-passdb-export.txt
config/smb.conf
metadata/system-passwd.txt
metadata/system-group.txt
metadata/samba-users.txt
```

但 `restore_tms.sh` **不会自动导入**。

原因是 Samba passdb backend、Linux UID/GID、已有系统用户以及目标服务器配置可能不同。错误的自动恢复可能覆盖系统账户。

真正灾难恢复时应：

1. 先恢复 Django/PostgreSQL；
2. 对照 `system-passwd.txt` / `system-group.txt` 重建必要账户和组；
3. 确认 UID/GID 与文件权限；
4. 检查目标机器 Samba passdb backend；
5. 再人工导入 Samba 用户；
6. 人工合并 `smb.conf`；
7. 最后运行 Samba 功能测试。

不要把备份中的 `/etc/passwd` 快照直接覆盖目标服务器。

---

# 13. systemd / Nginx 恢复边界

备份中的：

```text
config/*.service.txt
config/nginx-config.txt
```

是**恢复参考快照**，不是应直接覆盖系统的配置包。

在新服务器上应该根据新路径、域名、TLS 证书和服务账户重新部署，然后与备份内容对照。

尤其不要直接从备份恢复 TLS 私钥；备份脚本本身也不保存证书私钥。

---

# 14. 正式灾难恢复流程

真正需要恢复生产 TMS 时，先保证 TMS 不接受写入：

```bash
sudo systemctl stop tms
```

先预览：

```bash
sudo ./restore_tms.sh \
    --backup /var/backups/tms/<backup> \
    --mode production \
    --force \
    --dry-run
```

确认以下目标完全正确：

```text
目标数据库
MEDIA target
PRIVATE MEDIA target
NOTES target
```

然后执行：

```bash
sudo ./restore_tms.sh \
    --backup /var/backups/tms/<backup> \
    --mode production \
    --force
```

如果是全新的 PostgreSQL 集群，并且需要恢复 roles / tablespaces：

```bash
sudo ./restore_tms.sh \
    --backup /var/backups/tms/<backup> \
    --mode production \
    --restore-globals \
    --force
```

如果需要自动恢复备份中的 `.env`，只能用于**原拓扑恢复**：

```bash
sudo ./restore_tms.sh \
    --backup /var/backups/tms/<backup> \
    --mode production \
    --restore-env \
    --force
```

这里的“原拓扑”是指目标数据库名、`PRIVATE_MEDIA_ROOT` 和 `NOTES_ROOT` 都与备份时完全一致。

如果是新服务器、数据库名变化或目录路径变化，**不要使用 `--restore-env`**。应以备份中的 `config/.env` 为参考手工建立新的 `.env`，明确写入新数据库和新路径。

### production 模式的文件保护

如果目标：

```text
media/
media-private/
NOTES_ROOT
```

已经非空，脚本不会直接删除。

它会先改名为：

```text
<原目录>.before-restore-<timestamp>
```

再创建新的目标目录。

因此即使选择了 `--force`，恢复前已有文件仍保留一份现场副本。

---

# 15. 正式恢复后的验证

正式恢复结束后，**不要立即开放用户流量**。

依次执行：

```bash
python manage.py check
python manage.py showmigrations
```

然后进行数据库和文件抽查。

至少验证：

- 管理员登录；
- 用户和权限；
- 标准体系；
- Assessment；
- 评分；
- Training；
- Evidence；
- `media-private` 附件；
- Notes；
- 会议、通知、反馈、WorldSkills Forum 等附件。

最后才启动正式服务：

```bash
sudo systemctl start tms
```

再观察：

```bash
journalctl -u tms -f
```

以及 Nginx / Gunicorn 日志。

---

# 16. 演练完成后的清理

确认演练结果已经记录后，可以删除临时 drill 数据库：

```bash
sudo -u postgres dropdb <drill数据库名>
```

删除隔离文件：

```bash
sudo rm -rf /var/tmp/tms-restore/<本次演练目录>
```

**不要使用模糊通配符直接删除 `/var/tmp/tms-restore/*`。**

每次只删除本次已经确认的具体目录。

---

# 17. 演练记录模板

每次恢复演练建议留下记录：

```text
备份时间：
备份目录：
备份大小：
备份 SHA256：通过 / 失败

恢复时间：
恢复主机：
PostgreSQL 版本：
目标 drill 数据库：

数据库恢复：通过 / 失败
MEDIA_ROOT：通过 / 失败
PRIVATE_MEDIA_ROOT：通过 / 失败
NOTES_ROOT：通过 / 失败
Django check：通过 / 失败
登录验证：通过 / 失败
权限验证：通过 / 失败
Assessment 附件：通过 / 失败
训练数据：通过 / 失败
评分数据：通过 / 失败
Notes：通过 / 失败

发现的问题：
修复措施：

演练结论：
[ ] 该备份可以作为有效恢复点
[ ] 该备份不可作为正式恢复点
```

---

# 18. 成功判定

一份 TMS 备份只有同时满足以下条件，才应标记为“已验证”：

- [ ] `SHA256SUMS` 全部通过；
- [ ] `pg_restore` 完整成功；
- [ ] Django migration 历史存在；
- [ ] 核心业务数据存在；
- [ ] `media` 恢复成功；
- [ ] `media-private` 恢复成功；
- [ ] Notes 恢复成功；
- [ ] Django `check` 通过；
- [ ] TMS 能用恢复数据库启动；
- [ ] 管理员可以登录；
- [ ] 权限行为正常；
- [ ] 至少一个 Assessment 私有资料可以打开；
- [ ] 至少一个其他业务附件可以打开；
- [ ] Notes 正文/图片/附件正常；
- [ ] 已记录本次恢复演练结果。

对于 TMS 核心重构前的基线，建议要求以上项目**全部通过**。

---

## 参考

- PostgreSQL 17 Backup and Restore：  
  https://www.postgresql.org/docs/17/backup.html
- PostgreSQL 17 `pg_dump`：  
  https://www.postgresql.org/docs/17/app-pgdump.html
- PostgreSQL 17 `pg_restore`：  
  https://www.postgresql.org/docs/17/app-pgrestore.html
- PostgreSQL 17 `pg_dump` 兼容性说明：逻辑 dump 通常用于恢复到相同或更新的 PostgreSQL 版本，不保证可恢复到更旧的主版本。  
  https://www.postgresql.org/docs/17/app-pgdump.html
- Django 6 `django-admin` / `dumpdata`：  
  https://docs.djangoproject.com/zh-hans/6.0/ref/django-admin/
