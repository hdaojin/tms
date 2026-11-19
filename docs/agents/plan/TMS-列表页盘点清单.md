# TMS 列表页盘点

基线为 `develop` 的 `2e0cf94`。按 URL 配置、列表视图、表格模板、GET 表单和公共工具栏调用点核对。列表的现有查询和权限逻辑仍由业务视图负责。

| 应用／URL name | 当前页面与条件 | 类别和处理 |
| --- | --- | --- |
| Accounts · `user_list` | 用户表格，姓名、账号与角色筛选，支持批量操作 | A，复用公共工具栏并调整搜索顺序 |
| Accounts · `role_list` | 角色表格 | F，保持无独立筛选栏 |
| Training · `cycle_list`、`plan_list` | 周期按原条件搜索；计划已有范围和展示状态 | A／B，继承公共布局，计划状态使用快捷分类，保留默认状态和范围规则 |
| Training · `cycle_members`、`plan_members` | 成员表格，筛选与批量操作从属对应周期或计划 | A，继承公共布局，保留固定路径和操作边界 |
| Training · `log_list`、`monthly_stats` | 日志按计划、日期和身份检索；月度统计保留计划表单 | C／D，日志日期和周期身份放入高级区；保留原有校验和统计口径 |
| Training · `plan_detail` 的日程、任务、参与选手及负责人员 | 使用计划 tab 和目标容器；日程含日期、星期多选及批量入口 | D／E，保留专用局部渲染、白名单重置链接及人员交互 |
| Training · `my_training`、`board`、`task_list`、`log_template_list` | 我的训练、看板、兼容路由、日志模板管理 | D／E／F，分别保留模式选择、看板、跳转或无筛选表格 |
| Meetings · `meeting_list` | 会议表格，搜索和现有筛选 | A，继承公共布局 |
| Feedback · `list` | 标题或正文、类型、查看范围和处理状态，卡片结果 | B，状态移至快捷分类，保留结果 partial |
| Standards · `project_list`、`tree_list`、`tree_node_list`、`current_domain_tree_list`、`wsos_list` | 技能项目、技能树版本和节点、WSOS；版本和节点的有效范围依赖领域或项目 | A／E／F，沿用现有表格及节点专用结构，复用现有筛选入口 |
| Assessments · `assessment_list`、`module_list`、`competition_person_list`、`competition_role_list` | 考核已有名称、类型及状态查询；人员按姓名；模块及角色无筛选 | A／B／F，考核和人员复用工具栏，考核状态移至快捷分类，其余保留 |
| Evidence · `evidence_list` | 考点证据表格 | F，保留现有表格 |
| Scoring · `scheme_list`、在线评分 | 评分方案表格及交互式评分矩阵 | F／E，保留表格和评分专用结构 |
| Behaviors · `conductrecord_list`、`conductsummary_list` | 行为记录和汇总，独立列表动作与表格 | F，保留现有表格与统计 |
| Glossary · `browse` | 英文、中文、缩写；技能项目和专业词库 | A，改用公共工具栏，保留完整 GET 和原有 queryset |
| Glossary · `glossary_list`、`manage_entry_list`、`proposal_list`、`import_list`、`my_stats`、`all_stats` | 管理表格、导入与学习统计 | D／F，保留统计表单及既有管理入口 |
| WorldSkills Forum · `topic_list` | 搜索、模块和分类；年份、标签、类型、状态、重要度 | C，拆分基础和高级条件，保持卡片及 HTMX 结果 |
| WorldSkills Forum · `feed` | 全部、重要、官方、未读；全文及多条件过滤 | B／C，复用状态分类、基础和高级条件，保留完整 GET |
| Notices · `notice_list` | 通知列表 | F，保持原有查询和展示 |
| Notes · `repo_list`、`note_repo_index` | 仓库列表和笔记目录 | E／F，保持文档导航结构 |
| AI · `list`、提供商目录 | 模型筛选与提供商卡片 | A／F，模型沿用共享工具栏，提供商保留卡片 |
| Articles · `list`；Demo · `list` | 实验内容和开发示例 | D／F，保持各自用途 |
 # TMS 列表页盘点

基线为 `develop` 的 `2e0cf94`。按 URL 配置、列表视图、表格模板、GET 表单和公共工具栏调用点核对。列表的现有查询和权限逻辑仍由业务视图负责。

| 应用／URL name | 当前页面与条件 | 类别和处理 |
| --- | --- | --- |
| Accounts · `user_list` | 用户表格，姓名、账号与角色筛选，支持批量操作 | A，复用公共工具栏并调整搜索顺序 |
| Accounts · `role_list` | 角色表格 | F，保持无独立筛选栏 |
| Training · `cycle_list`、`plan_list` | 周期和计划表格，维持现有搜索及筛选 | A，继承公共布局 |
| Training · `cycle_members`、`plan_members` | 成员表格，筛选与批量操作从属对应周期或计划 | A，继承公共布局，保留固定路径和操作边界 |
| Training · `log_list`、`monthly_stats` | 日志按计划、日期和身份检索；月度统计保留计划表单 | C／D，日志日期和周期身份放入高级区；保留原有校验和统计口径 |
| Training · `plan_detail` 的日程、任务、参与选手及负责人员 | 使用计划 tab 和目标容器；日程含日期、星期多选及批量入口 | D／E，保留专用局部渲染、白名单重置链接及人员交互 |
| Training · `my_training`、`board`、`task_list`、`log_template_list` | 我的训练、看板、兼容路由、日志模板管理 | D／E／F，分别保留模式选择、看板、跳转或无筛选表格 |
| Meetings · `meeting_list` | 搜索会议名称、文件名及上传人，筛选会议起止日期 | C，日期移入高级区，保留原校验及结果 partial |
| Feedback · `list` | 标题或正文、类型、查看范围和处理状态，卡片结果 | B，状态移至快捷分类，保留结果 partial |
| Standards · `project_list`、`tree_list`、`tree_node_list`、`current_domain_tree_list`、`wsos_list` | 技能项目、技能树版本和节点、WSOS；版本和节点的有效范围依赖领域或项目 | A／E／F，沿用现有表格及节点专用结构，复用现有筛选入口 |
| Assessments · `assessment_list`、`module_list`、`competition_person_list`、`competition_role_list` | 考核已有名称、类型及状态查询；人员按姓名；模块及角色无筛选 | A／B／F，考核和人员复用工具栏，考核状态移至快捷分类，其余保留 |
| Evidence · `evidence_list` | 考点证据表格 | F，保留现有表格 |
| Scoring · `scheme_list`、在线评分 | 评分方案表格及交互式评分矩阵 | F／E，保留表格和评分专用结构 |
| Behaviors · `conductrecord_list`、`conductsummary_list` | 行为记录和汇总，独立列表动作与表格 | F，保留现有表格与统计 |
| Glossary · `browse` | 英文、中文、缩写；技能项目和专业词库 | A，改用公共工具栏，保留完整 GET 和原有 queryset |
| Glossary · `glossary_list`、`manage_entry_list`、`proposal_list`、`import_list`、`my_stats`、`all_stats` | 管理表格、导入与学习统计 | D／F，保留统计表单及既有管理入口 |
| WorldSkills Forum · `topic_list` | 搜索、模块和分类；年份、标签、类型、状态、重要度 | C，拆分基础和高级条件，保持卡片及 HTMX 结果 |
| WorldSkills Forum · `feed` | 全部、重要、官方、未读；全文及多条件过滤 | B／C，复用状态分类、基础和高级条件，保留完整 GET |
| Notices · `notice_list` | 通知列表 | F，保持原有查询和展示 |
| Notes · `repo_list`、`note_repo_index` | 仓库列表和笔记目录 | E／F，保持文档导航结构 |
| AI · `list`、提供商目录 | 模型筛选与提供商卡片 | A／F，模型沿用共享工具栏，提供商保留卡片 |
| Articles · `list`；Demo · `list` | 实验内容和开发示例 | D／F，保持各自用途 |
