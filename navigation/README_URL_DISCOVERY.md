# URL 自动发现功能

## 概述

URL 自动发现功能能够自动扫描所有已安装的 Django 应用（排除 admin），提取命名 URL 模式，并将其整合到导航菜单的 `named_url` 字段中，使其成为一个选择字段。

## 功能特性

- **自动扫描**：扫描所有已安装的 Django 应用，自动发现命名 URL
- **排除管理员**：自动排除 Django admin 相关的 URL
- **智能分组**：按应用分组显示 URL，提供更好的组织结构
- **URL 验证**：提供 URL 验证功能，确保 URL 的有效性
- **多种格式**：支持表格、列表、JSON 多种输出格式
- **命令行工具**：提供管理命令查看和调试 URL

## 核心组件

### 1. URL 发现模块 (`url_discovery.py`)

提供核心的 URL 发现功能：

```python
from navigation.url_discovery import discover_urls, get_named_url_choices

# 发现所有 URL
urls = discover_urls()

# 获取模型选择字段的选项
choices = get_named_url_choices()
```

#### 主要函数

- `discover_urls()`: 发现所有命名 URL，返回按应用分组的字典
- `get_named_url_choices()`: 获取适用于 Django 模型选择字段的选项列表
- `get_all_urls_for_app(app_name)`: 获取特定应用的所有 URL
- `validate_named_url(url_name)`: 验证命名 URL 是否有效

### 2. 管理命令 (`list_urls.py`)

提供命令行工具查看和调试 URL：

```bash
# 查看所有 URL
python manage.py list_urls

# 查看特定应用的 URL
python manage.py list_urls --app meeting

# 验证 URL 有效性
python manage.py list_urls --validate

# 输出 JSON 格式
python manage.py list_urls --format json

# 输出列表格式
python manage.py list_urls --format list
```

### 3. 模型集成

在 `navigation/models.py` 中，`MenuItem` 模型的 `named_url` 字段自动使用发现的 URL 作为选择选项：

```python
class MenuItem(models.Model):
    named_url = models.CharField(
        "命名路由", 
        max_length=200, 
        blank=True, 
        choices=get_named_url_choices(),
        help_text="Django 命名路由名称，从已发现的URL列表中选择"
    )
```

## 使用指南

### 1. 基本使用

创建菜单项时，`named_url` 字段将显示为下拉选择框，包含所有发现的 URL：

1. 打开 Django 管理界面
2. 创建或编辑菜单项
3. 在 "命名路由" 字段中选择目标 URL
4. 保存菜单项

### 2. 命令行工具使用

```bash
# 查看帮助
python manage.py list_urls --help

# 查看所有发现的 URL（表格格式）
python manage.py list_urls

# 查看特定应用的 URL
python manage.py list_urls --app accounts
python manage.py list_urls --app meeting

# 验证 URL 有效性
python manage.py list_urls --validate

# 不同的输出格式
python manage.py list_urls --format table    # 表格格式（默认）
python manage.py list_urls --format list     # 列表格式
python manage.py list_urls --format json     # JSON 格式
```

### 3. 编程接口

```python
from navigation.url_discovery import (
    discover_urls, 
    get_named_url_choices, 
    validate_named_url
)

# 获取所有发现的 URL
all_urls = discover_urls()
print(f"发现 {len(all_urls)} 个应用的 URL")

# 获取特定应用的 URL
meeting_urls = get_all_urls_for_app('meeting')

# 验证 URL
is_valid = validate_named_url('meeting:meeting_list')

# 获取模型选择字段选项
choices = get_named_url_choices()
```

## 输出格式示例

### 表格格式
```
================================================================================
应用              URL名称                          URL路径                     状态        
================================================================================

[MEETING] (4 URLs)
                meeting:meeting_detail         meeting/detail/<int:pk>             
                meeting:meeting_list           meeting                             
                meeting:meeting_pdf_inline     meeting/pdf_inline/<int:pk>           
                meeting:upload_meeting         meeting/upload                      
================================================================================
```

### 列表格式
```
meeting:
  - meeting:meeting_detail
  - meeting:meeting_list
  - meeting:meeting_pdf_inline
  - meeting:upload_meeting
```

### JSON 格式
```json
{
  "meeting": [
    {
      "name": "meeting:meeting_detail",
      "display_name": "meeting:meeting_detail (meeting/detail/<int:pk>)"
    },
    {
      "name": "meeting:meeting_list",
      "display_name": "meeting:meeting_list (meeting)"
    }
  ]
}
```

## 配置选项

### 排除特定 URL

如果需要排除特定的 URL 模式，可以在 `url_discovery.py` 中修改 `discover_urls()` 函数：

```python
def discover_urls():
    # 在现有的排除逻辑中添加更多条件
    for url_name, url_path in all_patterns:
        # 排除 admin URL
        if url_name.startswith('admin:'):
            continue
        
        # 排除其他不需要的 URL（示例）
        if url_name.startswith('debug:'):
            continue
        
        # ... 其余逻辑
```

### 自定义显示名称

可以在 `_create_display_name()` 函数中自定义 URL 的显示名称：

```python
def _create_display_name(url_name: str, url_path: str) -> str:
    # 自定义显示名称逻辑
    if url_name == 'home':
        return '首页'
    elif url_name.startswith('meeting:'):
        return f"会议 - {url_name.split(':')[1]}"
    
    # 默认逻辑
    return url_name
```

## 故障排除

### 常见问题

1. **URL 未出现在选择列表中**
   - 确保 URL 有正确的 `name` 参数
   - 检查 URL 是否被排除规则过滤
   - 运行 `python manage.py list_urls` 查看所有发现的 URL

2. **URL 验证失败**
   - 确保 URL 模式正确定义
   - 检查所需的参数是否正确传递
   - 使用 `python manage.py list_urls --validate` 检查 URL 状态

3. **性能问题**
   - URL 发现在应用启动时运行，大量 URL 可能影响启动时间
   - 考虑缓存机制或延迟加载

### 调试技巧

1. **使用管理命令调试**：
   ```bash
   python manage.py list_urls --validate
   ```

2. **查看特定应用**：
   ```bash
   python manage.py list_urls --app your_app_name
   ```

3. **使用 Python 交互式调试**：
   ```python
   from navigation.url_discovery import discover_urls
   urls = discover_urls()
   print(urls)
   ```

## 测试

运行测试确保功能正常：

```bash
# 运行所有 URL 发现相关测试
python manage.py test navigation.test_url_discovery

# 运行特定测试
python manage.py test navigation.test_url_discovery.URLDiscoveryTestCase
```

## 扩展功能

### 添加 URL 过滤器

可以添加自定义过滤器来进一步控制哪些 URL 被发现：

```python
def custom_url_filter(url_name: str, url_path: str) -> bool:
    """自定义 URL 过滤器"""
    # 只包含特定模式的 URL
    allowed_patterns = ['home', 'meeting:', 'accounts:']
    return any(url_name.startswith(pattern) for pattern in allowed_patterns)
```

### 添加 URL 分类

可以为 URL 添加分类标签：

```python
def get_url_category(url_name: str) -> str:
    """获取 URL 分类"""
    if url_name.startswith('meeting:'):
        return '会议管理'
    elif url_name.startswith('accounts:'):
        return '用户管理'
    else:
        return '其他'
```

## 版本历史

- **v1.0**: 初始版本，基本 URL 发现功能
- **v1.1**: 添加管理命令和多格式输出
- **v1.2**: 添加 URL 验证和测试覆盖
- **v1.3**: 改进显示名称和错误处理

## 贡献

如果您发现问题或有改进建议，请：

1. 提交 Issue 描述问题
2. 创建 Pull Request 包含修复或改进
3. 确保所有测试通过
4. 更新相关文档