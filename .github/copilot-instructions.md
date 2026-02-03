# TMS (Training Management System) - Copilot 开发指南

## 技术栈与架构

Django 6.0+ / Python 3.13+ / Tailwind CSS 4 + DaisyUI 5 / HTMX / Alpine.js / Iconify 图标  
包管理: `uv` (Python) + `npm` (前端) / 代码格式化: Prettier (含 tailwindcss 插件)

### 核心模块 (`core/`)
| 文件 | 用途 |
|------|------|
| `constants.py` | 全局常量 (组名 `GROUP_COACH`/`GROUP_COMPETITOR`、文件限制、上传路径) |
| `utils/mixins.py` | 视图 Mixin (`TitleMixin`, `OwnerRequiredMixin`, `CrossGroupAccessMixin`) |
| `utils/forms.py` | `StyledFormMixin` - 自动添加 DaisyUI 样式 |
| `utils/tables.py` | `BaseTable`, `ActionsColumn` - django-tables2 封装 |
| `utils/validators.py` | `validate_file_size`, `validate_date_not_future` |
| `utils/signals.py` | `register_file_cleanup_signals` - 自动清理文件 |
| `utils/pdf_response.py` | `create_pdf_preview_view` - PDF 预览工厂函数 |

## 开发命令

```bash
# 首次设置
uv sync && npm install && cp .env.example .env
uv run manage.py migrate
uv run manage.py loaddata core/default accounts/default competitions/default

# 日常开发 (两个终端)
npm run watch:css          # 终端1: CSS 热更新
uv run manage.py runserver # 终端2: Django 服务

# 测试
uv run manage.py test <app_name>  # 运行指定应用测试

# 生产构建
npm run build:css          # 压缩 CSS
```

## 核心开发模式

### 视图类：始终使用 TitleMixin
```python
from core.utils.mixins import TitleMixin, OwnerRequiredMixin, CrossGroupAccessMixin

class MeetingDetailView(TitleMixin, DetailView):
    title = "{date_chinese}的{title}会议记录"  # 动态标题，自动从 object 取值
    title_icon = "icon-[tabler--file-text]"

class TrainingLogDeleteView(OwnerRequiredMixin, DeleteView):  # 仅所有者可删
    owner_field = 'uploaded_by'
```

### 表单：使用 StyledFormMixin
```python
from core.utils.forms import StyledFormMixin

class MeetingUploadForm(StyledFormMixin, forms.ModelForm):
    # 自动添加 DaisyUI 类 (input, textarea, select, file-input 等)
    class Meta:
        model = Meeting
        fields = ['title', 'date', 'file']
```

### 表格：继承 BaseTable + ActionsColumn
```python
from core.utils.tables import BaseTable, BaseDateColumn, ActionsColumn

class MeetingTable(BaseTable):
    date = BaseDateColumn(verbose_name="会议日期")  # 统一 Y-m-d 格式
    actions = ActionsColumn(
        view_url="meeting:meeting_detail",
        delete_url="meeting:meeting_delete",
        delete_perm="meeting.delete_meeting",  # 按权限显示按钮
    )
```

### 模型文件字段：注册清理信号
```python
from core.utils.signals import register_file_cleanup_signals
from core.utils.validators import validate_file_size, validate_pdf_file

class Meeting(models.Model):
    file = models.FileField(upload_to=..., validators=[validate_pdf_file, validate_file_size])

register_file_cleanup_signals(Meeting, 'file')  # 删除/更新时自动清理旧文件
```

### 常量：使用 core/constants.py
```python
from core.constants import GROUP_COACH, GROUP_COMPETITOR, DEFAULT_UPLOAD_MAX_SIZE_MB
# 避免硬编码 "教练"、"选手" 等字符串
```

## 权限控制

- **全局**: `LoginRequiredMiddleware` 默认要求登录，公开页面用 `@login_not_required`
- **Mixin**: `PermissionRequiredMixin`, `SuperuserRequiredMixin`, `OwnerRequiredMixin`
- **跨组访问**: `CrossGroupAccessMixin` (教练↔选手互查)

## 模板约定

### 基础结构 (`base.html`)
```django
{% block left_sidebar %}{% endblock %}   {# 覆盖为空隐藏左栏 #}
{% block title %}{% endblock %}
{% block content %}{% endblock %}
{% block right_sidebar %}{% endblock %}  {# 覆盖为空隐藏右栏 #}
{% block extra_css %}{% endblock %}
{% block extra_js %}{% endblock %}
```

### 图标：Iconify + Tailwind 语法
```html
<span class="icon-[tabler--calendar] size-6 text-primary"></span>
```

### 模板标签 (`{% load form_extras %}`)
- `is_checkbox_input`, `is_file_input`, `is_textarea_input` - 字段类型判断
- 表单字段渲染参考: `accounts/templates/accounts/partials/form_field.html`

## 侧边栏菜单

每个应用创建 `menus.yml` 定义菜单:
```yaml
- name: 会议记录管理
  icon: icon-[tabler--calendar]
  is_group_header: true
  children:
    - name: 会议记录列表
      named_url: meeting:meeting_list
      login_required: true
      required_perms: [meeting.view_meeting]  # 可选
```

## 文件上传

| 类型 | 路径 | 说明 |
|------|------|------|
| 公共 | `media/` | 通知附件、会议记录等 |
| 私有 | `media-private/` | 考核文件、笔记等，需 Django 视图控制访问 |

## HTMX 交互

- 全局 CSRF: `base.html` 已配置 `hx-headers='{"x-csrftoken": "{{ csrf_token }}"}'`
- 使用 `django-htmx` 中间件，视图可通过 `request.htmx` 检测 HTMX 请求
- 局部更新时返回 partial 模板片段

## 本地化

- **语言**: `zh-hans` / **时区**: `Asia/Shanghai`
- 模型 `verbose_name`、表单错误信息均使用中文
- DaisyUI 组件样式配置: `static/css/main.css`

## 可用的 MCP 工具

开发时可使用以下 MCP 工具获取参考信息：

| 工具 | 用途 |
|------|------|
| `mcp_daisyui_*` | 查询 DaisyUI 组件文档和代码示例 |
| `mcp_github_*` | GitHub 仓库操作、PR 管理、Issue 管理 |
| `mcp_pylance_*` | Python 代码重构、导入整理、类型标注 |

**DaisyUI 查询示例**:
- `mcp_daisyui_fetch_daisyui_documentation` - 获取完整文档
- `mcp_daisyui_search_daisyui_documentation` - 搜索特定组件用法
