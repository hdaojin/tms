# TMS (Training Management System) - Copilot 开发指南

## 技术栈

Django 6.0+ / Python 3.13+ / Tailwind CSS 4 + DaisyUI 5 / HTMX / Alpine.js / Iconify 图标
包管理: `uv` (Python) + `npm` (前端) / 代码格式化: Prettier (含 tailwindcss 与 jinja-template 插件)
本地化: `zh-hans` / `Asia/Shanghai`，所有 verbose_name、错误消息使用中文

## 架构概览

- **用户模型**: 使用 Django 默认 `auth.User`，通过 `accounts.UserProfile` (OneToOne) 扩展学号、性别等字段
- **角色体系**: `GROUP_COACH`("教练") / `GROUP_COMPETITOR`("选手") 两个组，常量定义在 `core/constants.py`
- **全局登录**: `LoginRequiredMiddleware` 中间件默认要求登录；公开页面用 `@login_not_required` 装饰
- **站点配置**: `core.SiteConfig` 单例模型，通过 context_processor 注入所有模板 (`{{ site_config.site_name }}`)
- **菜单系统**: `core/config/menus.yml` 定义 layouts/sections，`core/config/menus/*.yml` 定义各 app 菜单片段，自动按权限过滤渲染
- **Middleware 顺序** (顺序敏感，新增中间件须注意插入位置):
  1. `HtmxMiddleware` — 最先，注入 `request.htmx`
  2. Django 标准中间件 (Security → Session → Common → CSRF → Auth)
  3. `LoginRequiredMiddleware` — 紧跟 Auth 之后，全站强制登录
  4. Message → XFrameOptions
  5. `FlatpageFallbackMiddleware` — 最后，URL 未匹配时回退到 FlatPage

## 开发命令

```bash
# 首次设置
uv sync && npm install && cp .env.example .env
uv run manage.py migrate
uv run manage.py loaddata core/default accounts/default competitions/default

# 日常开发 (两个终端)
npm run watch:css          # 终端1: Tailwind CSS 热更新
uv run manage.py runserver # 终端2: Django 服务

# 测试
uv run manage.py test <app_name>

# 生产构建
npm run build:css
```

## 核心开发模式

### 新建视图：始终使用 TitleMixin + PermissionRequiredMixin
```python
from core.utils.mixins import TitleMixin, OwnerRequiredMixin, CrossGroupAccessMixin
from django_tables2 import SingleTableView

# 列表视图 — 使用 SingleTableView (django-tables2)
class MeetingListView(TitleMixin, PermissionRequiredMixin, SingleTableView):
    model = Meeting
    table_class = MeetingTable
    title = "会议记录列表"
    title_icon = "icon-[tabler--calendar]"
    permission_required = "meeting.view_meeting"
    paginate_by = 20

# 详情视图 — 动态标题，{field} 占位符自动从 object 取值
class MeetingDetailView(TitleMixin, DetailView):
    title = "{date_chinese}的{title}会议记录"
    title_icon = "icon-[tabler--file-text]"

# 创建视图 — form_valid 中设置 uploaded_by
class MeetingCreateView(TitleMixin, PermissionRequiredMixin, CreateView):
    def form_valid(self, form):
        form.instance.uploaded_by = self.request.user
        return super().form_valid(form)

# 删除视图 — OwnerRequiredMixin 仅所有者可删
class MeetingDeleteView(OwnerRequiredMixin, DeleteView):
    owner_field = "uploaded_by"
```

**权限 Mixin 选择**:
- `PermissionRequiredMixin` — 按 Django 权限控制
- `OwnerRequiredMixin` — 仅对象所有者 (+ 超管) 可访问
- `CrossGroupAccessMixin` — 教练↔选手互查
- `SuperuserRequiredMixin` — 仅超级用户

### 新建表单：使用 StyledFormMixin
```python
from core.utils.forms import StyledFormMixin

class MeetingUploadForm(StyledFormMixin, forms.ModelForm):
    # StyledFormMixin 自动为 input/textarea/select/file-input/checkbox 添加 DaisyUI 类
    class Meta:
        model = Meeting
        fields = ["title", "date", "file"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}
```

### 新建表格：继承 BaseTable + ActionsColumn
```python
from core.utils.tables import BaseTable, BaseDateColumn, ActionsColumn

class MeetingTable(BaseTable):
    date = BaseDateColumn(verbose_name="会议日期")
    actions = ActionsColumn(
        view_url="meeting:meeting_detail",
        delete_url="meeting:meeting_delete",
        delete_perm="meeting.delete_meeting",  # 按权限显示按钮，删除使用 DaisyUI <dialog> 模态确认
    )
    class Meta(BaseTable.Meta):
        model = Meeting
        fields = ("date", "title", "filename", "uploaded_by", "actions")
```

### 模型文件字段：注册清理信号 + 使用常量验证器
```python
from core.constants import DEFAULT_ALLOWED_EXTENSIONS, DEFAULT_UPLOAD_MAX_SIZE_MB, MEETING_UPLOAD_DIR
from core.utils.signals import register_file_cleanup_signals
from core.utils.validators import validate_file_size, validate_pdf_file

class Meeting(models.Model):
    file = models.FileField(upload_to=meeting_upload_path, validators=[validate_pdf_file, validate_file_size])
    class Meta:
        verbose_name = "会议记录"
        ordering = ["-date"]

register_file_cleanup_signals(Meeting, "file")  # 模型文件末尾调用，删除/更新时自动清理旧文件
```

**文件存储**: 公共文件 → `media/`，私有文件 → `media-private/`（需 Django 视图控制访问）

### 常量：使用 core/constants.py，禁止硬编码
```python
from core.constants import GROUP_COACH, GROUP_COMPETITOR, DEFAULT_UPLOAD_MAX_SIZE_MB
# 所有组名、文件扩展名/大小限制、上传路径均在 constants.py 集中定义
```

### 审核流模式 (参考 `conduct` app)
需要审核的记录使用 STATUS_CHOICES 状态机：`PENDING`(待审核) → `APPROVED`(已通过) / `REJECTED`(已驳回)
```python
# 创建时强制设为待审核
def form_valid(self, form):
    form.instance.recorded_by = self.request.user
    form.instance.status = 'PENDING'
    return super().form_valid(form)

# 编辑/审核视图通过 queryset 限制只操作 PENDING 记录
def get_queryset(self):
    return super().get_queryset().filter(status='PENDING')

# 审核视图设置审核人和审核时间
def form_valid(self, form):
    form.instance.reviewed_by = self.request.user
    form.instance.reviewed_at = timezone.now()
    return super().form_valid(form)
```
角色数据隔离：列表视图中教练/超管看全部，选手只看自己的记录 (`queryset.filter(student=user)`)。

### PDF 预览：使用 `create_pdf_preview_view` 工厂函数
```python
from core.utils.pdf_response import create_pdf_preview_view

# 简单用法 — 任何登录用户可预览 (meeting/views.py)
meeting_pdf_inline = create_pdf_preview_view(Meeting)

# 带权限检查 (traininglogs/views.py)
traininglog_pdf_inline = create_pdf_preview_view(
    TrainingLog,
    permission_checker=check_traininglog_access
)
```
生成的 FBV 直接在 `urls.py` 中注册：`path('pdf_inline/<int:pk>/', meeting_pdf_inline, name='meeting_pdf_inline')`

### demo 应用：仅开发模式可用
`demo/` app 仅在 `DEBUG=True` 时加入 `INSTALLED_APPS` 和 URL 路由。所有 demo 视图继承 `DemoBaseView`，该基类在 `dispatch()` 中检查 `settings.DEBUG`，生产环境自动返回 404。用于组件演示和测试，不要在其他 app 中依赖 demo。

## 用户显示约定

通过 `accounts.AppConfig.ready()` 动态为 User 模型添加属性，避免自定义 User 模型：

```python
# 在 templates 和代码中统一使用
{{ user.display_name }}      # 返回 "姓名" 或 "用户名"（拼接 last_name + first_name）
{{ user.full_info }}         # 返回 "姓名(用户名)" 或仅 "姓名"
```

在表格、表单、列表中使用 `display_name`：
```python
# tables.py
class UserTable(BaseTable):
    user = tables.Column(accessor="user.display_name", verbose_name="用户")

# 模板中
<td>{{ record.user.display_name }}</td>
```

## 模板约定

```django
{# base.html 可用 block: left_sidebar, title, content, right_sidebar, extra_css, extra_js #}
{# 覆盖 left_sidebar/right_sidebar 为空可隐藏对应侧栏 #}
{# TitleMixin 自动填充 title block，无需手写 #}
{# HTMX CSRF 已在 base.html 全局配置 hx-headers #}
```

- **图标**: Iconify + Tailwind 语法 `<span class="icon-[tabler--calendar] size-6 text-primary"></span>`
- **表单渲染**: `{% load form_extras %}` 提供 `is_checkbox_input`/`is_file_input`/`is_textarea_input` 等过滤器，参考 `accounts/templates/accounts/partials/form_field.html`
- **组件模板**: `core/templates/core/components/` 含 `doc_detail_with_pdf.html`、`file_uploader.html`、`form_snippet.html`、`table_block.html` 等可复用片段

## 菜单配置

新增 app 需要:
1. 在 app 根目录创建 `menus.yml`（参考 `meeting/menus.yml`）
2. 在 `core/config/menus/` 下创建对应 `<app>.yml` 菜单片段
3. 在 `core/config/menus.yml` 的 `sections` 中注册新 section 并 include

```yaml
# meeting/menus.yml 示例
- name: 会议记录管理
  icon: icon-[tabler--calendar]
  is_group_header: true
  children:
    - name: 会议记录列表
      named_url: meeting:meeting_list
      login_required: true
    - name: 上传会议记录
      named_url: meeting:meeting_upload
      required_perms: [meeting.add_meeting]
```

## URL 路由

每个 app 设置 `app_name` 命名空间，在 `tmsproject/urls.py` 中以 `path('<app>/', include('<app>.urls'))` 注册。URL 命名规范: `<app>:<model>_<action>`（如 `meeting:meeting_list`、`meeting:meeting_detail`）。

## HTMX 交互

- 全局 CSRF 已配置，无需额外处理
- 使用 `django-htmx` 中间件，视图通过 `request.htmx` 检测 HTMX 请求
- 局部更新返回 partial 模板片段

## Fixture 数据

使用 YAML 格式 fixture，位于各 app 的 `fixtures/` 目录。加载命令:
```bash
uv run manage.py loaddata core/default accounts/default competitions/default conduct/default
```

## CSS 配置

`static/css/main.css` 使用 Tailwind CSS 4 语法:
- `@plugin "daisyui"` — 28 个主题，`light` 默认，`dark` 为 prefers-dark
- `@plugin "@iconify/tailwind4"` — 图标使用 `icon-[tabler--xxx]` 类名
- `@plugin "@tailwindcss/typography"` — 文章内容渲染

## 可用的 MCP 工具

| 工具 | 用途 |
|------|------|
| `mcp_daisyui_*` | 查询 DaisyUI 5 组件文档和代码示例 |
| `mcp_github_*` | GitHub 仓库操作、PR 管理、Issue 管理 |
| `mcp_pylance_*` | Python 代码重构、导入整理、类型标注 |
