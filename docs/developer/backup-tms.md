# TMS 生产备份脚本使用手册

> 适用脚本：`backup_tms.sh`  
> 适用环境：TMS 生产服务器，Django 6 / Python 3.13 / PostgreSQL  
> 默认项目目录：`/srv/tms`  
> 默认备份目录：`/var/backups/tms`

---

## 1. 文档目的

`backup_tms.sh` 用于为 TMS 生产环境生成一份可用于灾难恢复、服务器迁移和核心重构回滚的完整备份。

它不仅备份 PostgreSQL 数据库，还会同时保存 TMS 运行所依赖的上传文件、代码状态、配置和恢复所需的辅助信息。

对于 TMS 来说，一份完整备份至少应覆盖：

- PostgreSQL 业务数据库；
- PostgreSQL roles / tablespaces 等全局对象；
- `MEDIA_ROOT` 公共上传文件；
- `PRIVATE_MEDIA_ROOT` 私有业务文件；
- `NOTES_ROOT` 教学笔记文件；
- `.env`；
- 当前生产代码工作区；
- Git 提交、分支和历史；
- Python / Django / PostgreSQL 等环境信息；
- SHA256 完整性校验；
- 如果启用了 Samba，保存相关系统状态参考信息。

> `pg_dump` 可以保证 PostgreSQL 数据库内部的一致性，但数据库与 `media` / `media-private` 文件系统不是同一个事务。  
> 因此，在核心重构、重大 migration 或服务器迁移前制作“基线备份”时，应先停止 TMS 写入，再执行完整备份。

---

# 2. 最常用的标准备份流程

下面是推荐在 **TMS 核心重构前**执行的标准流程。

## 2.1 设置脚本权限

首次部署脚本后执行：

```bash
chmod 700 backup_tms.sh
```

建议只有管理员可以读取和执行该脚本。

---

## 2.2 停止 TMS 数据写入

进入维护窗口后停止 TMS 服务：

```bash
sudo systemctl stop tms.service
```

如果生产服务器实际使用的 systemd unit 不是 `tms.service`，应使用服务器真实的服务名。

确认服务已经停止：

```bash
systemctl status tms.service
```

停止写入的目的，是让：

```text
PostgreSQL 数据
+
media
+
media-private
+
notes
```

尽可能处于同一个业务时间点。

---

## 2.3 执行完整备份并验证 PostgreSQL 可恢复

核心重构前推荐：

```bash
sudo VERIFY_RESTORE=1 ./backup_tms.sh
```

`VERIFY_RESTORE=1` 不只是检查 `.dump` 文件是否能读取，还会：

```text
创建临时 PostgreSQL 数据库
        ↓
执行完整 pg_restore
        ↓
确认数据库可以正常连接
        ↓
删除临时验证数据库
```

因此它比普通备份更适合作为：

- 核心领域模型重构前基线；
- 大规模 migration 前备份；
- PostgreSQL 升级前备份；
- 服务器迁移前备份；
- 正式发布重大版本前备份。

---

## 2.4 确认终端输出

成功后，重点确认终端出现类似：

```text
完整 PostgreSQL 恢复验证通过。
公共媒体：.../files/media.tar.gz
私有媒体：.../files/media-private.tar.gz
TMS 备份完成
```

如果 `NOTES_ROOT` 位于 `PRIVATE_MEDIA_ROOT` 之外，还应看到：

```text
独立 Notes：.../files/notes.tar.gz
```

如果：

```text
NOTES_ROOT = PRIVATE_MEDIA_ROOT/notes
```

则 Notes 已包含在：

```text
media-private.tar.gz
```

中，不会重复打包。

---

## 2.5 再次检查 SHA256

进入本次备份目录：

```bash
cd /var/backups/tms/<本次备份目录>
```

执行：

```bash
sha256sum --check SHA256SUMS
```

正常情况下所有文件都应显示：

```text
OK
```

例如：

```text
./database/tms.dump: OK
./files/media.tar.gz: OK
./files/media-private.tar.gz: OK
./config/.env: OK
./code/tms-source.tar.gz: OK
...
```

任何一项出现：

```text
FAILED
```

都不能把这份备份标记为有效恢复点，应先调查原因。

---

## 2.6 重新启动 TMS

确认备份和 SHA256 校验都正常后：

```bash
sudo systemctl start tms.service
```

检查：

```bash
systemctl status tms.service
```

必要时观察日志：

```bash
journalctl -u tms.service -f
```

确认生产 TMS 已恢复正常服务。

---

# 3. 脚本会自动识别哪些配置

`backup_tms.sh` 会加载当前 TMS 的 Django settings，并以实际运行配置作为备份依据。

它会读取：

```text
DATABASES["default"]
MEDIA_ROOT
PRIVATE_MEDIA_ROOT
NOTES_ROOT
SAMBA_INTEGRATION_ENABLED
```

因此生产环境正常配置完成后，通常不需要再手工指定：

```bash
DB_NAME=tms
PRIVATE_MEDIA_ROOT=/srv/tms/media-private
NOTES_ROOT=...
```

数据库实际来源仍然是 TMS `.env` 中的：

```dotenv
DATABASE_URL=postgres://...
```

私有文件实际来源通常是：

```dotenv
PRIVATE_MEDIA_ROOT=/srv/tms/media-private
```

`NOTES_ROOT` 如果没有单独配置，则默认位于：

```text
PRIVATE_MEDIA_ROOT/notes
```

---

# 4. 默认配置

脚本默认值如下：

| 项目 | 默认值 |
| --- | --- |
| TMS 项目目录 | `/srv/tms` |
| 备份根目录 | `/var/backups/tms` |
| PostgreSQL 系统用户 | `postgres` |
| PostgreSQL 管理角色 | `postgres` |
| `.env` | `${PROJECT_DIR}/.env` |
| 是否备份 `.env` | 是 |
| 是否生成 Django dumpdata | 是 |
| 是否备份源码工作区 | 是 |
| 是否生成 Git bundle | 是 |
| Samba 状态 | 自动判断 |
| 完整 `pg_restore` 验证 | 默认关闭 |

如果生产服务器就是标准部署：

```text
/srv/tms
/var/backups/tms
本机 PostgreSQL
```

则通常直接运行即可：

```bash
sudo ./backup_tms.sh
```

---

# 5. 日常备份与基线备份

## 5.1 普通日常备份

普通备份：

```bash
sudo ./backup_tms.sh
```

此时：

```text
VERIFY_RESTORE=0
```

脚本仍然会执行：

```bash
pg_restore --list
```

确认 PostgreSQL custom archive 可以被解析，但不会额外创建一个数据库并完整恢复。

适合：

- 日常人工备份；
- 修改少量配置前；
- 一般版本发布前；
- 不需要完整恢复演练的临时备份。

---

## 5.2 核心重构前基线备份

推荐：

```bash
sudo systemctl stop tms.service

sudo VERIFY_RESTORE=1 ./backup_tms.sh

cd /var/backups/tms/<本次备份目录>
sha256sum --check SHA256SUMS

sudo systemctl start tms.service
```

这应作为当前 TMS 核心重构前的正式基线流程。

建议在确认恢复演练通过后，将该备份长期保留，并明确标记为：

```text
pre-core-refactor baseline
```

---

# 6. 备份内容

## 6.1 PostgreSQL 数据库

主备份：

```text
database/<数据库名>.dump
```

格式为 PostgreSQL custom archive。

该文件是业务数据库恢复的主要依据。

恢复时使用：

```bash
pg_restore
```

而不是直接：

```bash
psql < tms.dump
```

---

## 6.2 PostgreSQL 全局对象

```text
database/postgres-globals.sql
```

包括 PostgreSQL 集群级对象，例如：

- roles；
- role 属性；
- tablespaces 等。

它用于完整服务器重建或新 PostgreSQL 集群恢复。

> 不应在普通恢复演练中随意执行该文件，因为它可能修改当前 PostgreSQL 集群的全局角色。

---

## 6.3 数据库 schema 快照

```text
database/<数据库名>-schema.sql
```

只包含数据库结构。

它主要用于：

- 核心重构前后结构对照；
- migration 排查；
- 数据模型分析；
- 人工审阅。

它不是主恢复文件。

---

## 6.4 Django dumpdata

```text
database/<数据库名>-django-data.json.gz
```

这是 Django 层的辅助数据快照。

用途包括：

- 查看旧模型数据；
- 辅助数据迁移；
- 对比重构前后数据；
- 调试单个业务对象。

真正的完整数据库恢复仍应以：

```text
<数据库名>.dump
```

为准。

如果某个自定义模型导致 `dumpdata` 失败，脚本会记录警告，但不会否定已经成功生成的 PostgreSQL 主备份。

---

# 7. 文件备份

## 7.1 公共媒体

```text
files/media.tar.gz
```

对应 Django：

```python
MEDIA_ROOT
```

通常为：

```text
/srv/tms/media
```

---

## 7.2 私有媒体

```text
files/media-private.tar.gz
```

对应：

```python
settings.PRIVATE_MEDIA_ROOT
```

这里包含 TMS 大量核心业务文件，例如可能包括：

```text
assessments/
training/
scoring/
meetings/
notices/
feedback/
worldskills_forum/
glossary/
behaviors/
notes/
...
```

因此：

> `media-private.tar.gz` 与 PostgreSQL 数据库一样，是 TMS 完整恢复的核心备份文件。

不能只备份 `media/`。

---

## 7.3 Notes

如果：

```text
NOTES_ROOT
```

位于：

```text
PRIVATE_MEDIA_ROOT
```

内部，例如：

```text
/srv/tms/media-private/notes
```

则已经包含在：

```text
media-private.tar.gz
```

中。

脚本不会重复生成 Notes 归档。

如果生产环境将 Notes 独立配置到：

```text
/data/teaching-notes
```

则另外生成：

```text
files/notes.tar.gz
```

---

# 8. 配置备份

## 8.1 `.env`

默认会备份：

```text
config/.env
```

`.env` 对完整恢复很重要，因为其中可能包含：

```text
SECRET_KEY
DATABASE_URL
ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS
PRIVATE_MEDIA_ROOT
SAMBA_TASK_ENCRYPTION_KEY
...
```

但它也是高度敏感文件。

因此备份目录默认使用严格权限：

```text
仅 root 可读
```

不要把完整备份目录直接上传到公开云盘、GitHub 或不受信任的共享存储。

---

## 8.2 systemd / Nginx

如果服务器存在相关配置，脚本会保存参考快照，例如：

```text
config/tms.service.txt
config/gunicorn.service.txt
config/nginx-config.txt
```

这些文件用于灾难恢复时对照。

它们不是自动恢复目标。

在新服务器上，应根据：

- 新服务器路径；
- 域名；
- TLS；
- 服务账号；
- Gunicorn 部署方式；

重新确认后再配置。

---

# 9. Git 与生产源码

备份通常包含：

```text
code/tms-source.tar.gz
code/tms.git.bundle
code/git-info.txt
```

三者用途不同。

## 9.1 `tms-source.tar.gz`

保存生产服务器当时的实际工作区。

即使服务器存在尚未提交到 Git 的修改，这部分仍可以保存下来。

源码快照不会重复打包：

```text
.git/
.env
.venv/
.uv-cache/
node_modules/
media/
media-private/
staticfiles/
backups/
```

以及 Django settings 中识别出的实际持久化文件目录。

---

## 9.2 `tms.git.bundle`

保存 Git 仓库历史和 refs。

在灾难恢复时，可以用于：

```bash
git clone tms.git.bundle tms
```

---

## 9.3 `git-info.txt`

记录当时生产环境的：

```text
commit
branch
describe
remote
git status
最近提交
```

它可以帮助确定：

> 这份数据库和文件备份究竟对应哪一个 TMS 代码版本。

---

# 10. Samba 备份

TMS 的 Samba 集成不仅有 Django 数据库状态，还可能创建：

- Linux user；
- Linux group；
- Samba user；
- Samba password；
- Samba 配置。

脚本默认：

```bash
INCLUDE_SAMBA_STATE=auto
```

当：

```text
SAMBA_INTEGRATION_ENABLED=True
```

时，会尝试额外保存 Samba 状态，例如：

```text
config/samba-passdb-export.txt
config/smb.conf
metadata/samba-users.txt
metadata/system-passwd.txt
metadata/system-group.txt
```

其中可能包含密码哈希或系统账户信息，因此同样属于敏感数据。

恢复 Samba 时不能简单覆盖：

```text
/etc/passwd
/etc/group
```

应按《TMS 备份恢复演练手册》中的 Samba 恢复流程人工处理。

---

# 11. 备份目录结构

一次正常完整备份大致为：

```text
/var/backups/tms/
└── <时间戳>-<主机名>-tms/
    ├── database/
    │   ├── tms.dump
    │   ├── postgres-globals.sql
    │   ├── tms-schema.sql
    │   ├── tms-archive.list
    │   └── tms-django-data.json.gz
    │
    ├── files/
    │   ├── media.tar.gz
    │   ├── media-private.tar.gz
    │   └── notes.tar.gz
    │
    ├── code/
    │   ├── tms-source.tar.gz
    │   ├── tms.git.bundle
    │   └── git-info.txt
    │
    ├── config/
    │   ├── .env
    │   ├── nginx-config.txt
    │   ├── *.service.txt
    │   └── Samba 相关文件
    │
    ├── metadata/
    │   ├── backup-info.txt
    │   ├── system.txt
    │   ├── django.txt
    │   ├── postgres-settings.tsv
    │   ├── pyproject.toml
    │   ├── uv.lock
    │   └── ...
    │
    ├── RESTORE.txt
    ├── MANIFEST.txt
    └── SHA256SUMS
```

其中：

```text
notes.tar.gz
```

只有在 `NOTES_ROOT` 位于 `PRIVATE_MEDIA_ROOT` 之外时才会存在。

Samba 文件也只有在启用或显式要求备份 Samba 状态时才会存在。

---

# 12. 备份结果中的重要文件

## `metadata/backup-info.txt`

记录本次备份实际使用的运行信息，例如：

```text
数据库名称
数据库 host/port
MEDIA_ROOT
PRIVATE_MEDIA_ROOT
NOTES_ROOT
项目目录
是否启用 Samba
VERIFY_RESTORE
```

在恢复前应优先查看该文件。

---

## `MANIFEST.txt`

记录备份中有哪些文件及其大小。

用于快速检查：

> 这份备份到底包含了什么。

---

## `SHA256SUMS`

记录所有备份文件的 SHA256。

用于确认备份文件复制、传输、长期存储后有没有损坏。

检查：

```bash
sha256sum --check SHA256SUMS
```

---

## `RESTORE.txt`

脚本根据本次实际备份配置自动生成的简要恢复提示。

它主要用于灾难恢复时快速定位：

```text
原数据库
原 MEDIA_ROOT
原 PRIVATE_MEDIA_ROOT
原 NOTES_ROOT
基本 pg_restore 命令
```

完整恢复仍应配合：

```text
restore_tms.sh
```

和《TMS 备份恢复演练手册》。

---

# 13. 常用参数

脚本主要通过环境变量覆盖默认配置。

## 修改项目目录

例如 TMS 不在 `/srv/tms`：

```bash
sudo PROJECT_DIR=/opt/tms ./backup_tms.sh
```

---

## 修改备份目录

```bash
sudo BACKUP_ROOT=/data/backups/tms ./backup_tms.sh
```

---

## 同时修改

```bash
sudo \
    PROJECT_DIR=/opt/tms \
    BACKUP_ROOT=/data/backups/tms \
    ./backup_tms.sh
```

---

## 显式指定数据库名

通常不需要。

只有明确知道需要覆盖 Django 自动识别结果时：

```bash
sudo DB_NAME=tms ./backup_tms.sh
```

如果这个值与 Django 当前实际数据库不同，脚本会给出警告。

正常生产使用不建议人为指定。

---

## 完整 PostgreSQL 恢复验证

```bash
sudo VERIFY_RESTORE=1 ./backup_tms.sh
```

---

## 不备份 `.env`

不推荐用于正式完整备份，但可以：

```bash
sudo INCLUDE_ENV=0 ./backup_tms.sh
```

---

## 不生成 Django dumpdata

```bash
sudo INCLUDE_DJANGO_FIXTURE=0 ./backup_tms.sh
```

这不会影响 PostgreSQL 主 `.dump`。

---

## 不保存源码工作区

```bash
sudo INCLUDE_SOURCE=0 ./backup_tms.sh
```

---

## 不生成 Git bundle

```bash
sudo INCLUDE_GIT_BUNDLE=0 ./backup_tms.sh
```

---

## Samba

自动：

```bash
sudo INCLUDE_SAMBA_STATE=auto ./backup_tms.sh
```

强制：

```bash
sudo INCLUDE_SAMBA_STATE=1 ./backup_tms.sh
```

关闭：

```bash
sudo INCLUDE_SAMBA_STATE=0 ./backup_tms.sh
```

---

# 14. PostgreSQL 在远程服务器上的情况

当前脚本最适合：

```text
TMS
+
本机 PostgreSQL
```

这种生产部署。

如果 Django `DATABASE_URL` 指向远程 PostgreSQL，例如：

```text
db.example.local
```

脚本不会自动猜测管理连接方式，而会要求显式指定：

```text
PGHOST
PGPORT
PG_ROLE
```

以及对应 PostgreSQL 认证。

例如：

```bash
sudo \
    PGHOST=10.0.0.20 \
    PGPORT=5432 \
    PG_ROLE=postgres \
    ./backup_tms.sh
```

远程 PostgreSQL 的认证方式应单独规划。

不要为了运行备份脚本而把生产 PostgreSQL 临时改成 `trust` 认证。

---

# 15. 如何判断一次备份成功

对于普通备份，至少满足：

- [ ] 脚本以退出码 0 完成；
- [ ] PostgreSQL `.dump` 存在；
- [ ] `postgres-globals.sql` 存在；
- [ ] `media.tar.gz` 存在；
- [ ] `media-private.tar.gz` 存在；
- [ ] `.env` 已按预期备份；
- [ ] `SHA256SUMS` 生成成功；
- [ ] `sha256sum --check SHA256SUMS` 全部通过；
- [ ] 终端出现 `TMS 备份完成`。

对于核心重构前基线，还应额外满足：

- [ ] 在维护窗口执行；
- [ ] 使用 `VERIFY_RESTORE=1`；
- [ ] 出现 `完整 PostgreSQL 恢复验证通过`；
- [ ] 已进行一次完整恢复演练；
- [ ] Django 能使用恢复数据库启动；
- [ ] 关键历史数据可以查看；
- [ ] `media-private` 中的实际业务附件可以打开；
- [ ] 该备份被明确标记并长期保存。

---

# 16. 备份失败时如何处理

脚本使用严格错误模式：

```bash
set -Eeuo pipefail
```

如果关键步骤失败，会退出并显示：

```text
ERROR
```

未完成的备份目录可能仍保留在：

```text
/var/backups/tms/
```

用于分析故障。

不要因为目录已经生成就把它当成有效备份。

只有：

```text
TMS 备份完成
```

并且：

```bash
sha256sum --check SHA256SUMS
```

全部通过，才可以认为文件级备份成功。

核心重构前还需要完整恢复验证。

---

# 17. 常见警告

## `Django dumpdata` 失败

如果看到：

```text
Django dumpdata 失败；PostgreSQL pg_dump 仍是权威主备份。
```

说明辅助 JSON fixture 没有生成。

如果：

```text
tms.dump
```

正常，则主数据库备份仍然有效。

但建议在核心重构前调查 `dumpdata` 为什么失败，因为 JSON 快照对后续数据迁移分析很有价值。

---

## `MEDIA_ROOT` 不存在

说明当前 Django settings 指向的公共媒体目录不存在。

如果 TMS 从未有公共上传文件，可能是正常情况。

如果你确认生产系统应该存在上传文件，则必须先调查路径配置。

---

## `PRIVATE_MEDIA_ROOT` 不存在

这通常需要重点调查。

当前 TMS 大量业务附件依赖 `PRIVATE_MEDIA_ROOT`。

在有历史资料的生产环境中，如果该目录不存在，不能忽略后继续把备份定义为“完整备份”。

---

## `NOTES_ROOT 位于 PRIVATE_MEDIA_ROOT 内`

这是正常情况。

表示 Notes 已经包含在：

```text
media-private.tar.gz
```

中，所以不会再生成：

```text
notes.tar.gz
```

---

# 18. 备份文件安全

完整 TMS 备份中可能包含：

```text
用户资料
训练记录
竞赛与考核资料
评分结果
会议与反馈附件
SECRET_KEY
数据库连接密码
Samba 密码哈希
PostgreSQL role 密码哈希
```

因此备份属于高敏感数据。

建议：

- 备份目录只允许 root 访问；
- 不上传到 Git；
- 不放入公开网盘；
- 跨服务器传输时使用 SSH/SFTP 等加密通道；
- 复制到 NAS 或对象存储前建议增加加密；
- 异机备份至少保留一个独立副本。

脚本本身不会自动删除旧备份。

备份保留周期、异机复制和自动轮换应单独制定策略。

---

# 19. 与 `restore_tms.sh` 的关系

`backup_tms.sh` 负责：

```text
生成恢复点
```

`restore_tms.sh` 负责：

```text
验证和恢复这个恢复点
```

日常恢复演练推荐：

```bash
sudo ./restore_tms.sh \
    --backup /var/backups/tms/<本次备份目录> \
    --dry-run
```

确认恢复计划后：

```bash
sudo ./restore_tms.sh \
    --backup /var/backups/tms/<本次备份目录>
```

默认 `drill` 模式会：

- 创建新的演练数据库；
- 恢复到隔离文件目录；
- 不覆盖正式数据库；
- 不覆盖正式 `media`；
- 不覆盖正式 `media-private`；
- 不覆盖生产 `.env`。

完整流程见：

```text
TMS-backup-restore-drill.md
```

---

# 20. 核心重构前推荐操作清单

当前 TMS 核心重构前，可以直接按下面执行。

```bash
# 1. 确认脚本权限
chmod 700 backup_tms.sh

# 2. 停止生产写入
sudo systemctl stop tms.service

# 3. 完整备份 + PostgreSQL 实际恢复验证
sudo VERIFY_RESTORE=1 ./backup_tms.sh

# 4. 找到刚生成的备份目录
ls -lh /var/backups/tms/

# 5. 检查 SHA256
cd /var/backups/tms/<本次备份目录>
sha256sum --check SHA256SUMS

# 6. 恢复旧 TMS 服务
sudo systemctl start tms.service

# 7. 执行隔离恢复演练
sudo ./restore_tms.sh \
    --backup /var/backups/tms/<本次备份目录> \
    --dry-run

sudo ./restore_tms.sh \
    --backup /var/backups/tms/<本次备份目录>
```

只有在：

```text
完整备份成功
+
SHA256 全部 OK
+
恢复演练通过
```

之后，才建议把这份备份标记为：

```text
TMS 核心重构前正式基线
```

并开始可能涉及 destructive migration 或大规模数据迁移的核心重构工作。

---

## 参考

- PostgreSQL Backup and Restore  
  https://www.postgresql.org/docs/17/backup.html

- PostgreSQL `pg_dump`  
  https://www.postgresql.org/docs/17/app-pgdump.html

- PostgreSQL `pg_restore`  
  https://www.postgresql.org/docs/17/app-pgrestore.html

- Django 6 `dumpdata`  
  https://docs.djangoproject.com/zh-hans/6.0/ref/django-admin/#dumpdata
