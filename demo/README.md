# Demo 应用

此应用专门用于组件演示和测试，**仅在开发模式（DEBUG=True）下可用**。

## 目录结构

```
demo/
├── __init__.py
├── apps.py
├── admin.py
├── models.py
├── views.py          # 演示视图
├── urls.py           # URL 配置
└── templates/demo/   # 演示模板
    ├── components_list.html      # 组件列表首页
    └── file_upload_demo.html     # 文件上传组件演示
```

## 访问方式

开发环境启动后，访问：

- 组件演示首页：`http://127.0.0.1:8000/demo/`
- 文件上传演示：`http://127.0.0.1:8000/demo/file-upload/`

## 特性

1. **开发模式专用**：在 settings.py 中通过条件判断加载
2. **安全保护**：视图基类 `DemoBaseView` 会检查 DEBUG 设置，生产环境自动返回 404
3. **可扩展**：未来可以方便地添加更多组件演示

## 生产环境部署

生产环境设置 `DEBUG=False` 后，demo 应用会被自动排除，不会加载到 INSTALLED_APPS，也不会注册 URL 路由。
