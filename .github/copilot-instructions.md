# TMS (Training Management System) - Copilot 开发指南

## 项目架构概览

这是一个基于 Django 6.0+ 的技能竞赛训练管理系统，前端使用 Tailwind CSS 4 + DaisyUI 5，通过 HTMX 实现动态交互。

### 核心技术栈
- **后端**: Django 6.0+, Python 3.13+
- **前端**: Tailwind CSS 4, DaisyUI 5, HTMX, Iconify 图标
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **包管理**: `uv` (Python), `npm` (前端)

### 应用模块结构
```
core/           # 核心工具库
  constants.py      # 通用常量定义 (用户组名、文件大小限制等)
  utils/
    mixins.py       # 视图 Mixin (TitleMixin, OwnerRequiredMixin, CrossGroupAccessMixin 等)
    forms.py        # 表单 Mixin (StyledFormMixin)
    tables.py       # 表格工具 (BaseTable, ActionsColumn)
    validators.py   # 通用验证器 (FileSizeValidator, DateNotFutureValidator)
    signals.py      # 信号工具 (register_file_cleanup_signals)
    pdf_response.py # PDF 预览工具 (create_pdf_preview_view)
    decorators.py   # 装饰器 (superuser_required 等)
accounts/       # 用户认证与 Profile 管理
traininglogs/   # 训练日志上传与统计
meeting/        # 会议记录管理
notices/        # 通知发布系统
notes/          # Markdown 笔记库
competitions/   # 竞赛项目与模块管理
assessment/     # 考核评估
```

## 开发工作流

### 启动开发环境
```bash
uv sync                           # 安装 Python 依赖
npm install                       # 安装前端依赖
cp .env.example .env              # 配置环境变量
uv run manage.py migrate          # 数据库迁移
npm run watch:css                 # 监听 CSS 变更 (新终端)
uv run manage.py runserver        # 启动开发服务器
```

### 加载初始数据
```bash
uv run manage.py loaddata core/default accounts/default competitions/default
```

## 关键开发模式

### 1. 通用常量 - 使用 core/constants.py 避免硬编码
```python
from core.constants import GROUP_COACH, GROUP_COMPETITOR, DEFAULT_UPLOAD_MAX_SIZE_MB

# 检查用户组
if user.groups.filter(name=GROUP_COACH).exists():
    ...
```

### 2. 视图类模式 - 使用 TitleMixin 设置页面标题
```python
from core.utils.mixins import TitleMixin

# 静态标题
class MyListView(TitleMixin, ListView):
    title = "会议记录列表"

# 动态标题 - 使用对象字段（自动检测 {field} 占位符）
class MeetingDetailView(TitleMixin, DetailView):
    title = "{date_chinese}的{title}会议记录"  # 支持 Python 格式规范如 {date:%Y-%m-%d}
    title_icon = "icon-[tabler--file-text]"
```

### 3. 权限 Mixin - 使用内置 Mixin 控制访问
```python
from core.utils.mixins import OwnerRequiredMixin, CrossGroupAccessMixin

# 仅允许对象所有者访问
class TrainingLogDetailView(OwnerRequiredMixin, DetailView):
    owner_field = 'uploaded_by'  # 指定所有者字段

# 教练/选手跨组访问
class TrainingLogListView(CrossGroupAccessMixin, ListView):
    owner_field = 'uploaded_by'
    # 自动根据用户所属组过滤数据
```

### 4. 表单样式 - 使用 StyledFormMixin 自动添加 DaisyUI 类
```python
from core.utils.forms import StyledFormMixin

class TrainingLogCreateForm(StyledFormMixin, forms.ModelForm):
    # 自动为表单控件添加 DaisyUI 样式类
    # StyledFormMixin 会追加而非覆盖现有的 CSS 类
```

### 5. 表格展示 - 继承 BaseTable 配置统一样式
```python
from core.utils.tables import BaseTable, BaseDateColumn, ActionsColumn

class MeetingTable(BaseTable):
    date = BaseDateColumn(verbose_name="会议日期")
    actions = ActionsColumn(
        view_url="meeting:meeting_detail",
        edit_url="meeting:meeting_update",    # 可选: 编辑链接
        delete_url="meeting:meeting_delete",
        view_perm="meeting.view_meeting",     # 可选: 查看权限
        edit_perm="meeting.change_meeting",   # 可选: 编辑权限
        delete_perm="meeting.delete_meeting",
        view_label="查看",                    # 可自定义按钮文字
        edit_label="编辑",
        delete_label="删除",
    )
```

### 6. 文件验证 - 使用通用验证器
```python
from core.utils.validators import FileSizeValidator, DateNotFutureValidator

class Meeting(models.Model):
    date = models.DateField(validators=[DateNotFutureValidator()])
    file = models.FileField(validators=[FileSizeValidator(max_size_mb=50)])
```

### 7. 文件清理信号 - 自动删除关联文件
```python
from core.utils.signals import register_file_cleanup_signals

class Meeting(models.Model):
    file = models.FileField(...)

# 在模型定义后注册信号 (自动处理删除和更新时的文件清理)
register_file_cleanup_signals(Meeting, 'file')
```

### 8. PDF 预览视图 - 使用工厂函数快速创建
```python
from core.utils.pdf_response import create_pdf_preview_view
from .models import Meeting

# 简单用法
meeting_pdf_view = create_pdf_preview_view(Meeting, 'file')

# 自定义权限检查
def check_permission(request, obj):
    return request.user == obj.uploaded_by or request.user.is_superuser

meeting_pdf_view = create_pdf_preview_view(
    Meeting, 'file', 
    permission_checker=check_permission
)
```

### 9. 菜单配置 - 每个应用的 menus.yml 定义侧边栏菜单
```yaml
# meeting/menus.yml
- name: 会议记录管理
  icon: icon-[tabler--calendar]
  is_group_header: true
  children:
    - name: 会议记录列表
      named_url: meeting:meeting_list
      login_required: true
```

### 10. 权限控制模式
- 全局登录要求: 启用 `LoginRequiredMiddleware`，除非显式使用 `@login_not_required`
- 权限装饰器: `@superuser_required` (来自 `core.utils.decorators`)
- 权限 Mixin: `PermissionRequiredMixin`, `SuperuserRequiredMixin`, `OwnerRequiredMixin`

### 11. 数据库查询优化
```python
# 在 ListView/DetailView 中使用 select_related 减少查询
class MeetingListView(TitleMixin, ListView):
    def get_queryset(self):
        return Meeting.objects.select_related('uploaded_by').order_by('-date')

# 多对多关系使用 prefetch_related
class TrainingLogListView(TitleMixin, ListView):
    def get_queryset(self):
        return TrainingLog.objects.select_related(
            'uploaded_by', 'module'
        ).prefetch_related('tags')
```

## 模板结构

### 基础模板
- `base.html` → 完整布局 (header + left_sidebar + main + right_sidebar + footer)
- 通过覆盖空 block 控制侧边栏显示

### 模板块 (可覆盖)
```django
{% block header %}{% endblock %}
{% block left_sidebar %}{% endblock %}  {# 覆盖为空可隐藏左侧边栏 #}
{% block title %}{% endblock %}
{% block content %}{% endblock %}
{% block right_sidebar %}{% endblock %}  {# 覆盖为空可隐藏右侧边栏 #}
{% block extra_css %}{% endblock %}
{% block extra_js %}{% endblock %}
```

### 隐藏侧边栏示例
```django
{# 隐藏右侧边栏 #}
{% extends 'base.html' %}
{% block right_sidebar %}{% endblock %}

{# 隐藏左右侧边栏 #}
{% extends 'base.html' %}
{% block left_sidebar %}{% endblock %}
{% block right_sidebar %}{% endblock %}
```

### 通用 Partials
- `partials/form_field.html` - 表单字段渲染

### APP 内部 Partials
- `accounts/partials/user_info_card.html` - 用户账号信息卡片
- `accounts/partials/form_field.html` - 表单字段渲染

## 图标使用

使用 Iconify + Tailwind 语法，图标类格式: `icon-[provider--name]`
```html
<span class="icon-[tabler--calendar] size-6 text-primary"></span>
```

## 文件上传路径

- 公共媒体: `MEDIA_ROOT` (media/)
- 私有文件: `PRIVATE_MEDIA_ROOT` (media-private/)，通过 Django 视图控制访问权限

## 环境配置

核心环境变量 (`.env`):
- `SECRET_KEY` - Django 密钥
- `DEBUG` - 调试模式
- `DATABASE_URL` - 数据库连接 (默认 SQLite)
- `ALLOWED_HOSTS` - 允许的主机名

## 注意事项

- 所有模型 verbose_name 使用中文
- 时区设置为 `Asia/Shanghai`
- 语言设置为 `zh-hans`
- 表单验证错误信息应使用中文
