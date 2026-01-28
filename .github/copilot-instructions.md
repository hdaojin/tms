# TMS (Training Management System) - Copilot 开发指南

## 项目架构概览

这是一个基于 Django 6.0+ 的技能竞赛训练管理系统，前端使用 Tailwind CSS 4 + DaisyUI 5，通过 HTMX 实现动态交互。

### 核心技术栈
- **后端**: Django 6.0+, Python 3.13+
- **前端**: Tailwind CSS 4, DaisyUI 5, HTMX, Iconify 图标
- **数据库**: SQLite (开发) / PostgreSQL / MariaDB (生产)
- **包管理**: `uv` (Python), `npm` (前端)

### 应用模块结构
```
core/           # 核心工具库 (mixins, decorators, menus, context_processors)
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

### 1. 视图类模式 - 使用 TitleMixin 设置页面标题
```python
from core.utils.mixins import TitleMixin

class MeetingDetailView(TitleMixin, DetailView):
    title_object_fields = ['date_chinese', 'title']
    title_template = "{date_chinese}的{title}会议记录"
    title_icon = "icon-[tabler--file-text]"
```

### 2. 表单样式 - 使用 StyledFormMixin 自动添加 DaisyUI 类
```python
from core.utils.forms import StyledFormMixin

class TrainingLogCreateForm(StyledFormMixin, forms.ModelForm):
    # 自动为表单控件添加 DaisyUI 样式类
```

### 3. 表格展示 - 继承 BaseTable 配置统一样式
```python
from core.utils.tables import BaseTable, BaseDateColumn, ActionsColumn

class MeetingTable(BaseTable):
    date = BaseDateColumn(verbose_name="会议日期")
    actions = ActionsColumn(
        view_url="meeting:meeting_detail",
        delete_url="meeting:meeting_delete",
        delete_perm="meeting.delete_meeting"
    )
```

### 4. 菜单配置 - 每个应用的 menus.yml 定义侧边栏菜单
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

### 5. 权限控制模式
- 全局登录要求: 启用 `LoginRequiredMiddleware`，除非显式使用 `@login_not_required`
- 权限装饰器: `@superuser_required` (来自 `core.utils.decorators`)
- 权限 Mixin: `PermissionRequiredMixin`, `SuperuserRequiredMixin`

## 模板结构

### 基础模板继承链
- `base.html` → 完整布局 (header + left_sidebar + main + right_sidebar + footer)
- `base_no_right_sidebar.html` → 无右侧边栏
- `base_no_left_right_sidebar.html` → 无侧边栏

### 模板块 (可覆盖)
```django
{% block header %}{% endblock %}
{% block left_sidebar %}{% endblock %}
{% block title %}{% endblock %}
{% block content %}{% endblock %}
{% block right_sidebar %}{% endblock %}
{% block extra_css %}{% endblock %}
{% block extra_js %}{% endblock %}
```

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
