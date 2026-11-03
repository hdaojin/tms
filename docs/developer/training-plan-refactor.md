# 训练计划重构：升级与验证

对应 Plan：`docs/agents/plan/TMS_Training_Plan_Refactor_Codex_Plan.md`；现状审查与迁移设计见同目录 `TMS_Training_Plan_Refactor_Phase0_Review.md`。业务定义见 `CONTEXT.md` 与 ADR 0011（替代 ADR 0010 的发布和锁定规则）。

## 本轮补充确认

2026-11-01 更新：计划、排班、任务分开发布；时间配置归每个计划。当前规则在发布时锁定起止日期及每日时段，训练周期首次保存后固定。未过期任务直接留痕修改，已发布排班由涉及教练依次确认后终审，过期补改直接交指定审批人员或超级管理员终审。完成状态仅展示，不阻断修改。详见 ADR 0011。

此前 2026-10-31 的确认（冲突处以本次更新为准）：

- 保留执行后、时段锁定后及计划归档后的独立技能关联修正例外，必须留痕。
- 自主任务的可读/可反馈教练，是同计划中曾负责该选手官方任务的教练，包含未选时段或领域的自主任务；其他教练不可见。
- 既有计划任务管理员关系仅保留历史；具备对应权限的排班人员可维护时段任务和整理历史任务，全部明确分配的负责教练可按基础权限维护本时段任务。
- 使用用户提供的原 Excel 文件，源文件不变。项目运行资源副本为 `training/resources/templates/training_plan.xlsx`。

## 实施范围与阶段

| 阶段 | 实现 | 主要验证 |
| --- | --- | --- |
| 0 | 审查现有工作区、审批/权限/附件/表格、迁移和本地数据，先报告差异 | 改动前 training 基线 141 通过、1 个既有失败；迁移漂移及 Ruff 通过 |
| 1 | 增加参与选手/创建快照、计划内时间配置、时段快照、状态历史、进度修订、独立反馈、自主任务及历史负责关系 | `test_process_refactor.py` 的模型、锁定、权限、状态及完成率测试 |
| 2 | 自动生成日程，一天四格、31 日期分页、日期选择、清空预览、分层发布及教练依次确认／终审 | 日程分页、清空签名、审批过期和 HTMX 测试 |
| 3 | 时段任务保存草稿、逐条发布，时段负责教练权限、任务名单快照、带原因撤销、软取消/清空、任务附件及可选技能 | `test_scheduling.py`、任务权限/历史及附件测试 |
| 4 | 本人有效官方任务、四状态与历史、追加/修订进度、私有进度附件、独立教练反馈 | `test_process_refactor.py`、`test_process_files.py` |
| 5 | 休息日/无时段自主任务，本人维护、历史负责教练只读和反馈，独立统计 | 自主任务对象范围及官方完成率隔离测试 |
| 6 | 原模板复制导出、四行合并布局、整格任务、部分导入预览、签名确认及审批/锁定重检 | `test_plan_workbooks.py` |
| 7 | 历史迁移及权限/文档/静态产物核对 | `test_process_migration.py`、`test_schedule_migration.py`、相关 APP 回归、Ruff、Django check、迁移漂移和 CSS 构建 |

主改动在 training；复用 accounts 用户、standards 领域/技能、meetings 人员选择、core 权限/表格/私有上传。standards 的既有训练投入统计兼容新增“未完成”状态。没有新增一级 APP、独立任务菜单、训练日志自动生成或完整训练分析界面。

## 新模型和写入边界

- `TrainingPlan` 的八个时间字段保存计划独立作息，早读、晚上可成对为空；`published_at` 与 `schedule_published_at` 分别控制计划和排班发布。`TrainingScheduleSlot.starts_at/ends_at` 保存具体日期快照，`is_configured` 区分主动未设置和旧快照缺失。`TrainingPeriodConfig` 为后台维护的新计划默认时间。
- `TrainingPlanParticipant` 保存参与状态及 `was_initial` 创建名单。退出不删除任务分配；默认新任务发布时使用当前参与名单，Excel 使用创建名单。
- `TaskExecution` 继续使用原主键，增加独立撤销人、时间、原因及 `legacy_status`；正常新执行只有四种可选状态，撤销不改写为另一种执行结果。
- `TrainingStateChange`、`TrainingProgress`、`TrainingProgressRevision`、`TrainingCoachFeedback` 分别保存状态、进度及修订、各作者独立反馈。历史记录不允许覆盖。
- `TrainingAssignmentCoach` 保存官方分配的历史负责关系，作为自主任务教练范围依据。`PersonalTrainingTask` 与官方任务分别存储，进度/反馈通过明确外键及“恰好一个目标”数据库约束关联。
- `TrainingProgressAttachment` 独立关联进度；原教练任务附件和旧执行附件不移动、不混用。下载入口逐次校验业务对象及附件权限。
- 官方定义/排班/审批/分配统一从 `training/scheduling.py` 写入；执行事实、进度、反馈、自主任务从 `training/process.py` 写入。后台业务工作流及附件只读；计划时间由计划表单写入，涉及已发布／过期内容通过 `training/change_workflow.py` 申请及终审。待审附件由 `TrainingChangeAttachment` 私有存储，批准后复制到正式任务。

## 迁移顺序与数据保留

保留已经存在的 `training.0010`，不重写已应用迁移。

1. `0011_training_process_and_slot_times` 增加结构及兼容字段；旧时间快照允许为空。
2. `0012_preserve_training_process_facts` 使用历史模型保留旧执行状态，将现存完成/问题/总结文本标记为“历史汇总导入”，将现存单条反馈按原作者和发生时间迁入独立反馈。无法恢复已被覆盖的反馈、旧进度版本或状态变化，不虚构历史。
3. `0013_training_snapshot_constraint_and_status_label` 增加时间快照成对且结束晚于开始的数据库约束，并调整状态/分配标签。
4. `0014_plan_publication_times_and_change_confirmations` 增加计划发布、八个作息字段、教练确认链及待审附件。从旧计划自身一致快照提取时间，缺失或不一致者不伪造；旧待审请求保留并标记升级驳回，须重新申请。

旧任务、执行、文件记录主键与文件路径不变，日志执行引用保留。既有分配只能证明选手曾被分配任务，因此迁移形成的参与关系标记为非创建快照且非当前参与；管理员须明确整理参与名单。旧的“部分完成”“受阻”等状态原样保留，不能自动等价转换为本次训练已结束的“未完成”；选手后续明确更新为四种状态时保留状态变化历史。

旧时段没有快照时视为过期，不能直接写定义。不能将当前配置悄悄当作历史创建时配置；新计划按需要填写时段。旧计划可配置未来时段时间，已结束快照由超级管理员按补录流程明确处理。

## 升级操作

本地管理命令从仓库根目录执行。服务器使用 README 规定的部署流程应用迁移，普通生产管理命令使用 `sudo tms-deploy manage`，不在发布目录执行普通 uv。

1. 升级前备份数据库和训练业务私有文件；检查迁移目标。不能用开发重建命令代替迁移。
2. 应用新迁移：本地执行 `uv run manage.py migrate`；生产迁移仍走发布工具。
3. 核对权限包变化，使用已有 `reconcile_permission_assignments --dry-run` 预览，需要时再由管理员显式应用。迁移不自动修改账号成员或强制重跑 Bootstrap。
4. 在各计划编辑表单核对真实业务时间；普通编辑不改已结束快照，历史纠正须勾选并说明原因提交终审。
5. 在计划表单明确维护参与选手。无法追溯创建名单的旧计划不伪造初始快照，因此不能默认导入分配任务。
6. 对确需整理的旧计划，预览时间补录，核对后再确认。例如，以下编号均须替换为实际目标：

```powershell
uv run manage.py snapshot_training_plan 123 --actor 1
uv run manage.py snapshot_training_plan 123 --actor 1 --confirm
```

`--actor` 必须是有效超级管理员。命令只填缺失快照，不改已有快照；缺少日期/时段框架时也只在确认后生成框架，不推断旧任务的时段归属。记录“采用管理员在该计划明确配置补录、不代表历史真实时间”的审计说明，并增加时段版本，使旧审批预览失效。重复执行不重写已有快照。已到结束时间的补录时段后续修改须审批。

## 回退

结构迁移的反向操作不能无损表达新系统中的多条进度、修订、反馈和状态历史。`0012` 反向代码不改写旧源字段，但反向撤销新增表仍会丢失新结构数据；一旦已产生新数据，不以反向 migrate 作为无损回退方案。需要回退时恢复升级前数据库和配套私有文件备份，并同时回退代码；新增数据须先另行导出保全。不要单独回退 schema 后继续运行新代码。

## 验证与已知基线

聚焦命令：

```powershell
uv run pytest training -q --tb=no -p no:cacheprovider
uv run ruff check training standards/selectors.py
uv run manage.py check
uv run manage.py makemigrations --check --dry-run
npm run build:css
node --test scripts/test-training-schedule.mjs scripts/test-meeting-recipients.mjs
```

改动前已确认存在日志详情时间断言失败：`training/test_log_workflow.py::TrainingLogWorkflowTests::test_list_and_detail_show_record_times_and_author_name`。该日志页面不属于本次重构，保留单独报告，不为使回归全绿扩大修改。

### 本地执行记录（2026-10-31）

- 训练及相关 accounts/standards/core 合并回归：242 通过、1 个上述既有失败，另有 37 个 subtest 通过。最终受影响训练功能/迁移聚焦回归：71 通过、4 个 subtest 通过。
- `npm run test:frontend`：34 项全部通过，第三方静态资源校验通过；`npm run build:css` 完成，已更新实际 CSS 产物。
- 受影响路径 Ruff、Django check、迁移漂移检查、Git 空白检查均通过。原模板与运行资源副本 SHA256 一致。
- 本地 SQLite 升级前备份为 `backups/training-plan-refactor-20261031/before-schema-20261031T115048909731Z.sqlite3`，SQLite 完整性检查通过；本地已应用 training 0011–0013。
- 升级后原业务数据仍为 1 个计划、120 个时段、0 个任务、5 条审计；未自行填入时间配置或历史时间。当前 120 个旧时段仍缺时间快照，等待管理员明确配置并按上述命令补录。
- 权限对账仅执行 `--dry-run`，发现 2 个组漂移；没有改变现有用户组授权。没有执行服务器部署，也未执行全仓无关测试或浏览器人工验收。


## 日视图与明细视图

两视图读取同一组日、时段及任务；按31个日期分页，仅按日期升序并保持日内时段顺序。`schedule_entries.py` 统一可见范围、筛选及分页，日级信息不与任务复制绑定。批量编排和撤回的预览/确认入口为 `entry_views.py`，事务服务为 `entry_operations.py`；沿用 `scheduling.py` 和 `change_workflow.py`，不新增平行计划模型。预览令牌绑定操作者、固定目标、来源/目标快照及发布状态，确认与终审重检；任务新建、执行事实及来源变化均使预览失效。无筛选局部保存返回当前页受影响行的 OOB 更新；筛选可能改变结果成员时重取结果区。


## 0017：分层发布与首次填写

计划可先保存草稿，发布前须选定负责教练、参与选手和值班人员。计划详情发布已保存的内容。只有未发布且无有效任务和排班内容时才能改日期和时段，保存时同步空白框架并保留历史任务引用。旧计划从已有时段教练和日值班人员回填对应名单，缺项须人工补齐后再新增分配或发布。Excel 保持八列，兼容旧版“值班教练”列名；预览和确认均以计划对应名单为准。计划发布后才可保存排班；排班统一发布要求全部日期值班和已启用时段完整（全天已启用时段均为休息或不安排时可免值班），发布后才允许任务写入。日级信息与时段各有 `has_been_filled`，首次填写（含过期）直接保存；未发布排班和草稿任务的后续修改也免原因、直接保存（含过期、撤回后），已发布排班的非首次修改及已发布任务的过期修改仍须原因并按审批规则处理。该标志不随清空、撤回重置；迁移通过实际内容和可靠审计快照回填，不使用 revision 猜测。主要教练字段及任务教练角色字段删除，保留成员关联、任务和执行事实。原始历史JSON不改写。当前版本批量与快捷调班的新请求被停用。

迁移前备份本地SQLite；0017撤回无执行事实的不完整排班，计划发布标记和其他内容保留。存在待审申请、异常旧教练归属或受影响执行事实时中止迁移，不自动扩大授权或隐藏执行事实。结构逆向迁移不能恢复已删除的主次标识；需要完整旧数据时使用升级前备份。
