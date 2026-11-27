# TMS 笔记目录匿名访问 V1.0 --- Codex 实施 Plan

> 文档类型：Codex 可执行实施计划\
> 项目：TMS（Training Management System）\
> 目标分支：`develop`\
> 基线代码：本方案讨论时检查的 `develop` 提交
> `b57f4e024fec16adb5f5e8ef1c8b50a2a7697a48`（短 SHA：`b57f4e0`）\
> 日期：2026-11-27\
> 实施原则：最小改动、默认关闭、显式授权、保持现有私有访问行为

------------------------------------------------------------------------

## 1. 目标与范围

为 TMS 的 Notes APP
增加**笔记仓库目录级匿名只读访问**能力。超级管理员可以针对单个
`NoteRepo`
开启或关闭匿名访问。开启后，任何无需登录的访问者都可以通过已知的直接 URL
阅读该目录中的 Markdown 笔记、图片及附件。

本次只实现 Notes APP
的公开读取能力，不建设全站通用公共资源模型，不改变全站登录策略。

### 1.1 已确认的产品规则

1.  公开授权单位是一个完整的 `NoteRepo`，不是单篇
    Markdown，也不是某个附件。
2.  只允许通过直接链接访问公开仓库；**不提供匿名公开仓库列表、搜索或发现入口**。
3.  `/notes/` 笔记仓库列表仍然要求登录，并保留现有 `notes.view_noterepo`
    权限要求。
4.  公开开关默认关闭，现有所有仓库迁移后均为关闭状态。
5.  只有超级管理员可以开启或关闭公开访问。
6.  拥有 `notes.change_noterepo`
    的普通管理员可以查看公开状态，但不能修改该字段。
7.  公开访问仅对 `is_visible=True` 的仓库生效。`is_visible=False`
    的仓库继续沿用现有隐藏仓库规则，不允许匿名访问。
8.  公开仓库的只读访问不再要求登录、`notes.view_noterepo` 或属于
    `allowed_groups`。这对匿名用户和已登录用户一致。
9.  未公开仓库保持原有权限语义：必须登录、具有
    `notes.view_noterepo`，并通过现有 `allowed_groups` /
    超级管理员判断。
10. 未登录用户访问私有仓库时跳转登录；已登录但无权访问时返回 HTTP
    403；未登记仓库仍返回 HTTP 404。
11. 关闭公开开关后，后续请求立即重新执行权限判断。已经下载或另行保存的内容无法撤回。
12. 不提供分享密码、令牌、有效期、访问统计、公开目录列表等功能。

### 1.2 非目标

-   不修改 `LoginRequiredMiddleware` 的全局行为。
-   不改变 TMS 首页、倒计时、训练大屏等现有公开页面。
-   不将匿名访问抽象为 Core APP 的通用 `PublicResource` 模型。
-   不改变 `can_access_note_repo()` 现有语义及其调用方，特别是
    `training/teaching_notes.py`。
-   不改变 Notes APP 现有 Markdown 解析、附件 MIME
    类型处理和路径安全机制，除为公开访问增加必要的边界保护外。
-   不公开仓库列表，不向匿名用户增加 Notes APP 导航入口。
-   不把 `NOTES_ROOT` 或 `PRIVATE_MEDIA_ROOT` 直接配置为 Web
    服务器静态公开目录。

------------------------------------------------------------------------

## 2. 实施前必须核对的代码事实

本方案依据讨论时检查的 `develop` 代码制定。Codex
开始实施时必须重新读取当前工作树及最新分支，不能假定代码没有变化。

已检查的关键位置：

  -------------------------------------------------------------------------------------------------------------------------------------------------
  文件                                       当前职责                                                本次处理
  ------------------------------------------ ------------------------------------------------------- ----------------------------------------------
  `tmsproject/settings.py`                   启用 Django `LoginRequiredMiddleware`                   不修改

  `tmsproject/urls.py`                       注册 `/notes/`、`/notes-files/` 路由                    仅在确有必要时调整导入或装饰，不改变路由语义

  `notes/models.py`                          `NoteRepo` 数据模型                                     增加公开开关及路径层级校验

  `notes/permissions.py`                     `can_access_note_repo()`、`can_access_note_content()`   保持原函数语义，新增只读访问判断

  `notes/views.py`                           仓库列表、正文、打印、附件视图                          正文/打印/附件支持匿名授权

  `notes/urls.py`                            Notes APP 路由                                          仓库列表继续登录保护

  `notes/admin.py`                           `NoteRepoAdmin`                                         展示公开状态、只读保护、超级管理员修改

  `notes/templates/notes/note_detail.html`   笔记阅读页                                              匿名用户不出现指向私有仓库列表的面包屑

  `notes/templates/notes/print_note.html`    打印页面                                                支持同一匿名访问规则

  `notes/tests.py`                           Notes APP 测试                                          增加授权、视图、附件、Admin 和路径边界测试

  `notes/utils.py`、`notes/paths.py`         Markdown 路径解析、资源链接改写                         仅按安全需要增加仓库边界保护

  `training/teaching_notes.py`               Training APP 读取教学笔记                               确认旧权限行为不变
  -------------------------------------------------------------------------------------------------------------------------------------------------

当前 `NoteRepo` 已有
`slug`、`relative_path`、`title`、`description`、`is_visible`、`allowed_groups`、`tags`
等字段。`relative_path`
已有唯一约束和路径规范化，但目前没有阻止两个已登记仓库形成父子目录重叠。

当前三个 Notes 读取视图及附件视图使用固定的 `login_required` /
`permission_required` 装饰器。`note_asset_view` 在 `tmsproject/urls.py`
中单独注册为 `/notes-files/<str:repo>/<path:asset_path>`，不能遗漏。

当前 `notes_repo_list_view` 使用 `can_access_note_repo()`
过滤仓库列表。它必须继续保持登录及原权限要求。

------------------------------------------------------------------------

## 3. 执行前检查

### 3.1 阅读项目规范和工作区状态

1.  阅读仓库根目录 `AGENTS.md`，以及其引用的相关开发规范。
2.  阅读 `pyproject.toml`，确认 Python、Django、测试、Ruff
    等工具的实际配置和命令。
3.  检查
    `git status --short`。保留用户已有修改，不覆盖、不重置、不清理无关文件。
4.  确认当前分支和最新 `develop`
    HEAD。若当前代码与本方案基线不同，重新检查本方案涉及的文件并适配，不得直接覆盖较新的实现。
5.  搜索所有 `can_access_note_repo()` 调用点，确认除 Notes
    外的调用方，尤其是 `training/teaching_notes.py`。

### 3.2 检查现有 NoteRepo 路径重叠

在当前连接的开发数据库上进行只读检查，列出所有 `relative_path`
存在父子关系的仓库。路径比较必须按 POSIX
路径段进行，不能只用字符串前缀比较（例如 `course/a` 与 `course/abc`
不构成父子关系）。

可用 Django shell 编写只读检查脚本，读取全部
`NoteRepo.slug`、`relative_path`，将路径规范化为
`PurePosixPath(...).parts`，两条路径中较短路径的所有段与较长路径前缀完全相等时，判定为重叠。

要求：

-   不自动删除、重命名或修改任何现有仓库。
-   将检查结果记录在实施摘要中。
-   对存在父子重叠的仓库，公开访问必须有运行时保护，不能因数据尚未清理而绕过安全边界。
-   新增/修改仓库路径时禁止产生新的父子重叠。
-   若数据库不可用，明确记录"未能检查当前数据库"，不得声称不存在重叠。

------------------------------------------------------------------------

## 4. 数据模型与迁移

### 4.1 新增字段

在 `notes/models.py` 的 `NoteRepo` 中增加：

``` python
allow_anonymous_access = models.BooleanField(
    "允许匿名访问",
    default=False,
    help_text=(
        "开启后，任何人都可以通过直接链接访问该笔记仓库及其 Markdown、"
        "图片和附件。仅对“在笔记列表中显示”的仓库生效。"
    ),
)
```

要求：

-   默认值必须是 `False`。
-   字段名称固定为 `allow_anonymous_access`。
-   不增加独立授权表。
-   不增加冗余的 `public_url` 数据库字段。
-   不改变 `is_visible`、`allowed_groups` 的既有定义。

### 4.2 数据库迁移

生成 `notes` APP 的下一条迁移（预计为
`0004_noterepo_allow_anonymous_access.py`，以实际迁移依赖为准）。

迁移只新增 BooleanField，默认值为
`False`。不得在迁移中自动开放任何历史仓库，也不得改写现有用户组关系。

执行 `makemigrations` 后检查迁移依赖及内容，确认没有意外字段变更。

### 4.3 禁止新增父子路径重叠

为 `NoteRepo.relative_path` 增加路径层级校验：

-   `a/b` 与 `a/b/c` 是重叠路径，禁止新建或修改为这种关系。
-   `a/b` 与 `a/bc` 不重叠，允许。
-   `a/b` 与 `a/c` 不重叠，允许。
-   比较前必须调用现有路径规范化逻辑。
-   排除当前对象自身。
-   `clean()` 和 `save()` 均应覆盖校验，避免绕过 ModelForm
    校验后直接调用 `save()`。
-   更新其他字段（如标题、公开状态）时，不应因为一个历史路径冲突而无条件阻止保存；但开启公开访问时必须检查该仓库是否包含已登记的子仓库。
-   避免无意义的重复查询：更新对象时先判断 `relative_path`
    是否实际发生变化，再执行路径重叠校验。
-   错误应以 `ValidationError` 指向 `relative_path`，便于 Django Admin
    正常显示。

### 4.4 历史重叠的运行时保护

新增一个清晰、可测试的辅助判断，用于判断当前仓库是否包含其他已登记
NoteRepo 的子目录。

如果某个仓库
`allow_anonymous_access=True`，但它的目录内仍存在另一个已登记的子仓库：

-   匿名公开访问必须被阻止，不能通过父仓库 URL 读取子仓库内容。
-   对匿名请求返回
    404，避免暴露仓库内部登记结构；不得把该冲突错误地当作正常公开访问。
-   已登录用户仍按该仓库原有私有权限规则判断。
-   Django Admin
    应明确显示该公开配置因存在嵌套仓库而被阻止，并提示管理员先调整目录结构。
-   不自动修改历史数据。

若公开仓库本身是另一个私有父仓库的子目录，不因此阻止该公开子仓库；需要保护的是**当前公开仓库内部包含其他已登记仓库**的情况。

------------------------------------------------------------------------

## 5. 权限设计

### 5.1 保持旧函数不变

`notes/permissions.py` 中的：

``` python
can_access_note_repo(user, repo_slug, *, note_repo=None)
```

必须保持现有语义：

-   未登录用户返回 `False`。
-   仓库未登记返回 `False`。
-   `is_visible=False` 时，非超级管理员返回 `False`。
-   超级管理员按原规则允许。
-   `allowed_groups` 非空时，必须属于指定用户组之一。
-   `allowed_groups`
    为空时，保持原有"任意已登录且具备调用层所要求权限的用户可访问"语义。

不得把匿名公开逻辑直接塞入该函数，因为 `training/teaching_notes.py`
等现有调用方依赖它的私有授权语义。

### 5.2 新增只读访问判断

新增专用于 Notes HTTP 只读端点的函数，例如：

``` python
can_read_note_repo(user, note_repo) -> bool
```

规则：

1.  仓库不存在：拒绝。
2.  `is_visible=False`：不允许匿名；登录用户仍按原规则，仅超级管理员可访问。
3.  `is_visible=True` 且 `allow_anonymous_access=True`
    且不存在嵌套子仓库：允许匿名用户及所有已登录用户读取，不检查
    `notes.view_noterepo` 和 `allowed_groups`。
4.  公开开关开启但存在嵌套子仓库：不得匿名公开；已登录用户回退到原有权限规则。
5.  其他情况：必须登录，并同时满足
    `user.has_perm("notes.view_noterepo")` 和
    `can_access_note_repo(user, note_repo.slug, note_repo=note_repo)`。

权限函数应保持为纯授权判断，不直接返回 HttpResponse，也不负责跳转登录。

### 5.3 统一 HTTP 访问响应

在 `notes/views.py` 中建立统一辅助函数，供正文、打印和附件视图使用：

-   授权成功：返回 `None`，视图继续处理。
-   匿名访问私有仓库：返回
    `redirect_to_login(request.get_full_path())`。
-   匿名访问"配置为公开但因嵌套仓库冲突而被阻止"的仓库：抛出/返回 HTTP
    404，不跳转登录，不泄露冲突细节。
-   已登录但没有权限：返回 HTTP 403。
-   仓库未登记：仍由现有 `_get_registered_repo()` 返回 HTTP 404。

不要让权限模块依赖 Django Request/Response。

------------------------------------------------------------------------

## 6. View 与 URL 实施

### 6.1 必须支持匿名访问的端点

以下读取视图统一采用 `login_not_required`，退出
`LoginRequiredMiddleware` 默认登录限制，并在视图内部执行第 5
节的授权判断：

1.  `note_detail_view`
    -   `/notes/<repo>/`
    -   `/notes/<repo>/<path:slug>/`
2.  `note_print_view`
    -   `/notes/<repo>/<path:slug>/print/`
3.  `note_asset_view`
    -   `/notes-files/<repo>/<path:asset_path>`

装饰器应确保 `login_not_required` 标记最终交给 URL resolver 的视图
callable。建议将 `@login_not_required` 放在最外层，并通过真实 Django
Test Client 测试 `LoginRequiredMiddleware` 的行为。

删除这些读取视图上固定的 `@login_required` 和
`@permission_required("notes.view_noterepo", raise_exception=True)`，因为它们会在视图授权逻辑执行前拒绝匿名用户。

不要简单删除装饰器后就认为安全；每个端点都必须执行统一授权辅助函数。

### 6.2 必须保持登录的端点

`notes_repo_list_view` 不改：

-   保留 `@login_required`。
-   保留
    `@permission_required("notes.view_noterepo", raise_exception=True)`。
-   不允许匿名用户通过 `/notes/` 获取仓库列表。
-   不为匿名用户增加公开仓库列表、搜索、标签筛选或导航入口。

### 6.3 附件 URL

`note_asset_view` 虽然位于 `notes/views.py`，但当前路由在
`tmsproject/urls.py` 单独注册。必须确保该视图也使用 `login_not_required`
并执行同一授权逻辑。

不得：

-   把 `NOTES_ROOT` 或其父目录加入 `static()` 或 Caddy 公共文件目录。
-   绕过 `build_inline_preview_response()`。
-   绕过当前路径穿越、软链接逃逸、文件类型和 `Content-Disposition`
    安全检查。
-   为匿名用户单独实现一条无权限校验的静态文件路径。

公开目录中的 Markdown 相对图片、PDF 和附件仍然使用当前
`/notes-files/...` URL 改写及受控响应。

### 6.4 缓存和搜索引擎响应头

正文、打印和附件响应均应：

-   设置 `X-Robots-Tag: noindex, nofollow`。
-   禁止共享缓存/CDN 缓存受权限控制的内容。
-   正文及打印视图使用 Django `never_cache` 或等效响应头，确保
    `Cache-Control` 包含 `private` 和 `no-store`。
-   附件继续保持当前
    `Cache-Control: private, no-store`，不得破坏已有测试。
-   权限判断必须在读取 Markdown 缓存内容或返回附件之前执行。

现有 Markdown
渲染缓存可以保留。不要把"是否公开"的授权结果放入可跨用户复用的缓存。

------------------------------------------------------------------------

## 7. Django Admin 管理界面

修改 `notes/admin.py` 中的 `NoteRepoAdmin`。

### 7.1 列表页

-   `list_display` 增加 `allow_anonymous_access` 状态。
-   `list_filter` 增加 `allow_anonymous_access`。
-   可增加公开链接展示列，但不增加数据库字段。
-   当公开开关已开启但存在嵌套子仓库时，展示"公开配置已开启，但因目录重叠被阻止"之类的明确状态，不得误显示为可正常公开。
-   不使用 `list_editable` 直接修改公开开关。

### 7.2 编辑页

-   超级管理员：`allow_anonymous_access` 可编辑。
-   非超级管理员：该字段加入动态 `readonly_fields`，仍可查看当前值。
-   公开 URL 使用
    `reverse("notes:note_repo_index", kwargs={"repo": obj.slug})`
    动态生成相对 URL，不存入数据库。
-   只有开关开启且没有嵌套仓库冲突时才显示可用公开链接；否则显示未公开或阻止原因。
-   不需要自定义前端 JS；相对 URL 文本或普通链接即可。

### 7.3 后端保存保护

不能只依赖 `readonly_fields`。

在 `NoteRepoAdmin.save_model()` 中：

1.  修改已有对象时，从数据库读取原始 `allow_anonymous_access`。
2.  如果字段值发生变化且当前用户不是超级管理员，拒绝保存并抛出
    `PermissionDenied`。
3.  新建对象时，非超级管理员不能将该字段设置为 `True`。
4.  超级管理员正常保存。
5.  其他字段的管理权限和保存行为保持现状。

Django Admin 的变更历史继续使用现有日志机制，不另建审计 APP。

------------------------------------------------------------------------

## 8. 模板与匿名阅读体验

### 8.1 复用现有阅读页面

继续复用：

-   `notes/templates/notes/note_detail.html`
-   `notes/templates/notes/print_note.html`
-   `layouts/app.html` / `layouts/print.html`

不开发独立的匿名阅读模板，不复制 Markdown 渲染逻辑。

匿名用户应当可以正常使用：

-   仓库 README 首页。
-   笔记正文及相对链接。
-   左侧课程目录。
-   右侧文章大纲。
-   上一篇/下一篇。
-   图片、PDF 和附件。
-   现有打印页面。

### 8.2 面包屑和导航

当前 `note_detail_view` 的面包屑包含指向 `notes:repo_list`
的"笔记仓库"链接。匿名用户不能访问该列表，因此：

-   登录用户保持原面包屑。
-   匿名用户不显示指向 `notes:repo_list` 的链接。
-   可以保留当前公开仓库首页和当前文章之间的导航。
-   不修改全站导航系统；依赖现有导航可见性规则，确保需要登录的 APP
    菜单不会展示给匿名用户。
-   不增加匿名公开目录列表入口。

不要为了隐藏一个面包屑链接而修改全局 `core/navigation.py`。

------------------------------------------------------------------------

## 9. 自动化测试

测试优先扩展现有 `notes/tests.py`，遵循项目现有 Django TestCase
风格。必要时拆分测试类，但不要另建重复测试体系。

### 9.1 模型与默认值

-   新建 NoteRepo 时 `allow_anonymous_access is False`。
-   迁移后历史仓库默认关闭。
-   `relative_path` 父子重叠的新建被拒绝。
-   修改 `relative_path` 造成父子重叠被拒绝。
-   `a/b` 与 `a/bc` 不应误判为重叠。
-   仅修改标题、描述等非路径字段时，不因历史路径冲突而产生无关失败。
-   开启公开访问时，如果当前仓库包含已登记子仓库，应阻止保存或阻止公开生效，并在
    Admin 给出明确提示。

### 9.2 权限函数

覆盖下列组合：

  用户                           仓库状态                      预期
  ------------------------------ ----------------------------- ----------------
  匿名                           可见、公开、无子仓库冲突      允许只读
  登录但无 Notes 权限            可见、公开、无子仓库冲突      允许只读
  登录且不在 allowed_groups      可见、公开、无子仓库冲突      允许只读
  匿名                           可见、私有                    拒绝
  登录且有模型权限及用户组权限   可见、私有                    允许
  登录但无模型权限               可见、私有                    拒绝
  登录但不属于 allowed_groups    可见、私有                    拒绝
  匿名                           不可见，即使公开字段为 True   拒绝
  普通登录用户                   不可见                        拒绝
  超级管理员                     不可见                        按原有规则允许
  匿名                           公开父仓库包含已登记子仓库    拒绝公开访问

同时增加回归测试，确认 `can_access_note_repo()` 对公开字段不敏感，原有
Training 调用方语义不变。

### 9.3 HTTP 视图与中间件

使用真实 Django Test Client 测试，不能只直接调用 View 函数：

-   匿名 GET 公开仓库首页返回 200。
-   匿名 GET 公开 Markdown 正文返回 200。
-   匿名 GET 公开打印页面返回 200。
-   匿名 GET 公开图片返回 200。
-   匿名 GET 公开 PDF/附件返回 200，且沿用安全 MIME 和下载策略。
-   匿名 GET `/notes/` 仍跳转登录。
-   匿名访问私有目录跳转登录，并保留 `next` 参数。
-   已登录但无权访问私有目录返回 403。
-   已登录但无 Notes 权限的用户访问公开目录返回 200。
-   `is_visible=False` 的仓库不能匿名访问，即使
    `allow_anonymous_access=True`。
-   未登记仓库仍返回 404。
-   公开开关关闭后，下一次匿名请求立即跳转登录。
-   公开父仓库存在嵌套子仓库时，匿名请求不能读取父仓库内容或附件。
-   路径穿越、软链接逃逸、非法附件路径继续被拒绝。

### 9.4 响应头

对正文、打印、附件分别验证：

-   `X-Robots-Tag` 为 `noindex, nofollow`。
-   `Cache-Control` 包含 `private` 和 `no-store`。
-   附件已有 `X-Content-Type-Options: nosniff`、安全 `Content-Type` 和
    `Content-Disposition` 行为不退化。

### 9.5 Admin 权限

-   超级管理员表单中公开字段可编辑。
-   普通管理员表单中公开字段只读。
-   普通管理员正常修改标题、简介、标签等字段不受影响。
-   普通管理员通过伪造 POST 尝试修改公开字段，字段值不得改变。
-   对 `save_model()` 的直接测试确认普通管理员修改公开字段会被拒绝。
-   超级管理员可以开启和关闭公开访问。
-   存在嵌套子仓库时 Admin 能显示阻止原因。

### 9.6 Training 回归

运行并检查 `training/teaching_notes.py` 相关测试：

-   不得因为 `allow_anonymous_access=True` 就改变 Training 原有
    `can_access_note_repo()` 授权结果。
-   不得允许匿名用户通过 Training 的教学笔记入口访问内容。
-   不修改 `training/teaching_notes.py`
    的权限调用逻辑，除非测试证明当前代码确有必要且能解释原因；默认不改。

------------------------------------------------------------------------

## 10. 实施步骤与建议顺序

按以下顺序执行，完成一阶段后再进入下一阶段：

### Phase 1 --- 基线与路径审计

1.  阅读 `AGENTS.md` 和项目工具配置。
2.  检查工作区及最新 `develop`。
3.  搜索所有 `can_access_note_repo()` 调用点。
4.  对当前数据库执行 NoteRepo 父子路径重叠只读审计。
5.  汇总现有路径冲突，不修改任何数据。

### Phase 2 --- 模型与迁移

1.  增加 `allow_anonymous_access=False`。
2.  增加父子路径重叠校验。
3.  增加"公开仓库不能包含已登记子仓库"的校验及运行时判断。
4.  生成并审查 Notes APP 迁移。
5.  增加模型和路径测试。

### Phase 3 --- 权限与视图

1.  保持 `can_access_note_repo()` 不变。
2.  新增 `can_read_note_repo()` 和嵌套仓库冲突判断。
3.  新增统一 HTTP 授权响应辅助函数。
4.  为正文、打印、附件视图增加 `login_not_required`。
5.  移除这些读取端点不再适用的固定登录/模型权限装饰器。
6.  保留仓库列表的登录和模型权限装饰器。
7.  增加 `never_cache`、`X-Robots-Tag` 等响应头。
8.  增加中间件集成测试及视图测试。

### Phase 4 --- Django Admin

1.  增加列表状态和过滤。
2.  动态设置普通管理员只读字段。
3.  增加 `save_model()` 超级管理员校验。
4.  增加公开 URL 和嵌套冲突提示。
5.  完成 Admin 权限测试。

### Phase 5 --- 模板与回归

1.  调整匿名用户面包屑，移除指向私有仓库列表的链接。
2.  确认课程目录、文章大纲、图片、附件和打印均正常。
3.  确认不需要改动全局导航、全站认证中间件。
4.  执行 Notes 和 Training 相关测试。
5.  执行 Django system check、迁移检查、格式与静态检查。

### Phase 6 --- 最终审查与交付

1.  检查最终 diff，确认没有修改无关 APP。
2.  检查迁移只新增一个默认关闭的 BooleanField。
3.  检查所有匿名入口均有统一授权判断。
4.  检查附件入口没有绕过授权。
5.  检查普通管理员不能通过 Admin POST 绕过公开字段只读保护。
6.  汇总修改文件、迁移、测试命令及结果。
7.  明确报告数据库路径重叠审计是否成功、发现了哪些冲突及其处理状态。
8.  不自动提交 Git commit，不推送远程分支，除非用户另行要求。

------------------------------------------------------------------------

## 11. 验收标准

以下全部满足才算完成：

-   [ ] 新字段 `allow_anonymous_access` 已迁移，默认 False。
-   [ ] 所有历史仓库默认仍为私有。
-   [ ] 只有超级管理员能够修改公开开关。
-   [ ] 普通管理员能够查看状态但不能修改，伪造 POST 也不能绕过。
-   [ ] 公开目录只能通过直接链接访问，不存在匿名目录列表。
-   [ ] `/notes/` 仍然需要登录及原有模型权限。
-   [ ] 公开目录的首页、Markdown、打印页、图片和附件均可匿名读取。
-   [ ] 私有目录匿名访问会跳转登录。
-   [ ] 登录但无权限访问私有目录仍返回 403。
-   [ ] `is_visible=False` 不会因为公开开关而允许匿名访问。
-   [ ] 关闭公开开关后立即恢复原权限限制。
-   [ ] 未登记仓库、路径穿越和软链接逃逸仍安全。
-   [ ] 父仓库公开时不会暴露已登记的私有子仓库。
-   [ ] `can_access_note_repo()` 语义未改变。
-   [ ] Training 教学笔记授权行为未改变。
-   [ ] 响应使用 `noindex, nofollow`，且不允许共享缓存。
-   [ ] Django、Notes、Training 相关测试通过。
-   [ ] `makemigrations --check --dry-run` 无未提交模型变更。
-   [ ] 最终 diff 不包含无关重构或全局认证策略修改。

------------------------------------------------------------------------

## 12. Codex 执行指令

请在 TMS 仓库中按本 Plan 直接实施，不要只输出建议或伪代码。

执行要求：

1.  先读取 `AGENTS.md`、项目配置和当前工作区状态。
2.  以当前最新 `develop` 代码为准；若代码已变化，先理解变化再适配本
    Plan。
3.  严格遵守本 Plan 的已确认业务规则，不自行扩大功能范围。
4.  不改变全站 `LoginRequiredMiddleware`。
5.  不改变 `can_access_note_repo()` 的原有语义。
6.  不允许匿名访问仓库列表。
7.  不允许公开字段默认开启。
8.  不允许普通管理员修改公开字段。
9.  不允许父仓库公开访问穿透到已登记的子仓库。
10. 不自动删除或重命名任何现有 NoteRepo、笔记文件或附件。
11. 不覆盖用户未提交的代码修改。
12. 完成后运行测试和检查，并提供真实执行结果；未运行的检查必须明确标记，不能声称通过。
13. 不创建 Git commit，不推送远程分支。

最终回复应包含：

-   实施结果摘要。
-   修改文件清单。
-   新增迁移及迁移内容。
-   匿名访问、私有访问和 Admin 权限行为说明。
-   NoteRepo 路径重叠审计结果。
-   实际执行的测试命令及通过/失败结果。
-   尚未解决的问题或需要人工处理的数据冲突。

------------------------------------------------------------------------

## 13. 参考文档

-   Django 6.0
    Authentication：<https://docs.djangoproject.com/en/6.0/topics/auth/default/>
-   Django 6.0
    Middleware：<https://docs.djangoproject.com/en/6.0/ref/middleware/>
-   Django 6.0
    ModelAdmin：<https://docs.djangoproject.com/en/6.0/ref/contrib/admin/>
-   TMS
    `notes/models.py`：<https://github.com/hdaojin/tms/blob/develop/notes/models.py>
-   TMS
    `notes/permissions.py`：<https://github.com/hdaojin/tms/blob/develop/notes/permissions.py>
-   TMS
    `notes/views.py`：<https://github.com/hdaojin/tms/blob/develop/notes/views.py>
-   TMS
    `notes/admin.py`：<https://github.com/hdaojin/tms/blob/develop/notes/admin.py>
-   TMS
    `training/teaching_notes.py`：<https://github.com/hdaojin/tms/blob/develop/training/teaching_notes.py>
