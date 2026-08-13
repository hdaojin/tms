# TMS Project Overview

本文件用于 `$tms-dev` 快速定位代码。它是**地图，不是规范**；工程规则以仓库根目录 `AGENTS.md` 为准，领域语义以 `CONTEXT.md` 为准。

## 领域主链路

```text
standards
  SkillProject / CapabilityDomain / SkillTreeVersion / SkillNode
        |
        v
events
  CompetitionSeries / CompetitionLevel / Event / EventModule / Participant
        |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
examcontent                scoring                archives
ExamPaper                  ScoringScheme          ArchiveAsset
ExamRequirement            ScoringAspect          原始业务文件
        |                      |
        +-----------+----------+
                    v
                knowledge
        KnowledgeEvidence
        KnowledgeEvidenceSkillMap
                    |
                    v
             技能覆盖/表现分析
                    |
                    v
                training
        TrainingCycle / TrainingLog
```

核心原则：事件模块是某次比赛/考核的实际模块，长期标准落在 `standards`；评分点和试题要求先形成考点证据，再映射到当前技能树中的标准技能点。

## 当前 APP 地图

### 平台基础

- `core`
  - 通用表单、table、mixin、上传、权限包、导航与首页。
  - 关键入口：`core/constants.py`、`core/uploads.py`、`core/tables.py`、`core/utils/mixins.py`、`core/permissions/`、`core/navigation.py`。
- `accounts`
  - Django 默认 User 的扩展资料、GroupProfile、权限包授权、用户显示 helper。
- `samba`
  - Samba 集成及相关异步/同步操作。

### 领域主链路

- `standards`
  - 长期技能项目、能力领域、技能树版本、技能节点。
- `events`
  - 赛事系列/级别、具体竞赛或考核、事件模块、参与人员、结果汇总。
- `archives`
  - 统一资料资产登记、私有存储、SHA256、业务对象泛型绑定。
- `training`
  - 训练周期与训练日志；训练日志文件通过 ArchiveAsset 关联。
- `examcontent`
  - 事件模块下的试题与结构化试题要求。
- `scoring`
  - 评分表 parser、导入预览/确认、评分方案、评分点、参评对象和评分结果。
  - `scoring/services.py` 是当前跨模型事务工作流的重要参考。
- `knowledge`
  - 考点证据、技能点映射、审核状态、覆盖统计。
  - `knowledge/selectors.py` 是当前复杂读取/统计拆分的重要参考。

### 业务扩展

- `glossary`：专业词库、词条提案、学习会话与统计。
- `worldskills_forum`：WorldSkills 论坛主题、帖子、中文翻译、附件、阅读状态。
- `notes`：教学笔记仓库、Markdown/代码/Mermaid 展示与文件访问。
- `meetings`：会议记录。
- `notices`：通知公告。
- `behaviors`：奖惩记录与汇总。
- `event_countdown`：比赛/活动倒计时大屏。
- `demo`：UI/组件演示，仅 `DEBUG=True`。

## 全局入口

- `tmsproject/settings.py`
  - INSTALLED_APPS、middleware、CSP、数据库、static/media/private media。
- `tmsproject/urls.py`
  - 当前 APP URL 汇总；`demo` 只在 DEBUG 加载。
- `core/config/navigation.yml`
  - Header/dashboard/sidebar 的唯一导航配置入口。
- `templates/layouts/`
  - `app.html`：常规登录后业务页面。
  - `minimal.html`：简化页面/特殊展示。
  - `auth.html`：认证页面。
  - `print.html`：打印页面。
  - `htmx.html`：HTMX fragment 基础布局。
  - `base.html`：底层/兼容入口，不是新业务页首选。
- `templates/common/`、`templates/components/`
  - 通用表单、表格和可复用 UI 组件。
- `static/css/main.css`
  - Tailwind CSS 4 CSS-first 入口；注册 DaisyUI、Iconify Tailwind 4 和项目组件层。

## 权限入口

- Django permission 是后端授权基础。
- `core/permissions/bundles.py` 将业务权限组合为可分配权限包。
- `accounts.GroupProfile.codename` 是稳定组标识；Django `Group.name` 更适合作为显示名/兼容数据，不应成为新业务角色判断的唯一依据。
- 常用 mixin 位于 `core/utils/mixins.py`。

## 文件入口

- 公共上传：`media/`，只能放允许直接提供的文件。
- 私有上传：`settings.PRIVATE_MEDIA_ROOT`，默认 `media-private/`。
- 统一上传规则：`core/uploads.py`。
- 领域主链路原始文件：优先 `archives.ArchiveAsset`。
- 多文件 form：`core/forms/fields.py`。
- 文件清理：按现有模型使用 `register_file_cleanup_signals`。

## 前端入口

- HTMX：`django_htmx.middleware.HtmxMiddleware` 提供 `request.htmx`。
- django-tables2：列表页常见 `SingleTableView` + `core.tables` 封装。
- Tailwind 4：完整静态 class，源码检测由 `static/css/main.css` 的 `@source` 控制。
- DaisyUI 5：组件 class + Tailwind utility。
- Alpine：使用 `@alpinejs/csp`，复杂表达式/逻辑放静态 JS。
- Iconify：`icon-[tabler--...]` 等完整静态 selector。

## 探索一个功能时

推荐顺序：

1. `CONTEXT.md` 中确认术语和业务对象。
2. 找 URL/导航入口。
3. 读 view/form/table/template。
4. 追到 service/selector/model。
5. 看 migration 和 tests，确认已有约束与兼容要求。
6. 跨 APP 时沿领域主链路继续追下游，而不是只看当前 APP。

不要再按照旧 `traininglogs` / `assessments` / `competitions` / `skills` / `articles` 项目地图工作，也不要寻找已淘汰的 `core/config/menus/*.yml`。
