# 文档预览与 PDF 导出

`core.documents` 提供纯转换接口。业务入口先校验对象访问权限，再准备正文及已经授权读取的图片。业务 APP 负责响应、下载和可选的归档。

```python
from datetime import date

from core.documents import (
    DocumentAsset,
    DocumentInput,
    generate_document_pdf,
    list_document_templates,
    render_document_html,
)

document = DocumentInput(
    title="网络训练总结",
    subtitle="连通性与故障排查",
    author="训练教练组",
    organization="网络系统管理项目组",
    document_date=date(2026, 11, 12),
    template_id="standard",
    content="## 验证结果\n\n![网络拓扑](tms-asset:topology)",
    assets={"topology": DocumentAsset(authorized_png_bytes, "image/png")},
)

templates = list_document_templates()
preview_html = render_document_html(document)
pdf_bytes = generate_document_pdf(document)
```

- 默认正文格式为 `markdown`。`html_fragment` 支持同一份正文结构白名单。AI 集成由业务 APP 在生成完成后校验数据，再传入正文、元数据和可信的 `template_id`。
- 文档预览可写入带 `sandbox="allow-same-origin"` 的 iframe 的 `srcdoc`。页面样式使用同源静态资源，外部链接在预览中显示为文本，文档内锚点可跳转。分页以 PDF 为准。
- PDF 生成返回内存字节。预览和下载响应应使用 `application/pdf`、`Cache-Control: private, no-store` 和合适的 `Content-Disposition`。当前输入已生成 PDF 时，下载复用预览字节。正文、模板或元数据修改后应清除旧结果。
- 输入和图片错误抛出 `DocumentError`，渲染环境、资源上限和执行失败抛出 `DocumentRenderError`，实例已有渲染时抛出其子类 `DocumentBusy`。

## 模板与内容边界

`standard` 采用无衬线技术报告版式，`formal` 采用中文衬线正文和居中标题。两套模板共享 `templates/documents/document.html` 和 `static/css/documents/base.css`。新增模板时，登记稳定 ID 和受版本控制的 CSS，并复用正文清理流程。默认输出为 A4 纵向，自动分页，打印页脚显示页码。表格用 `thead` 定义重复表头。

正文支持标题、段落、引用、列表、表格、代码、链接和受控图片。样式、脚本、表单和嵌入对象由 HTML 白名单过滤。PDF 链接只保留 HTTP、HTTPS、mailto 和文档锚点。渲染进程只接受调用方提供并由服务重新编码的图片资源，其他资源请求会终止渲染。

图片支持静态 PNG、JPEG 和 WebP。处理时按 EXIF 校正方向，重新编码并清除元数据。图片引用使用 `tms-asset:ID`，ID 允许 1–64 个 ASCII 字母、数字、下划线或连字符。缺图、动画、格式不符或超限会报错。正文上限为 UTF-8 1 MiB，图片最多提供 20 张、引用 20 次，单张限 5 MiB 与 800 万像素，总量限 20 MiB 与 2,400 万像素。

## Debian 13 验收

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends fontconfig fonts-noto-cjk libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
uv sync --frozen
uv run manage.py check_document_pdf
```

`check_document_pdf` 使用两套模板实际渲染含中文、图片、代码和跨页表格的样张。传入 `--output-dir` 和已有目录可保存样张供目视核对。生产服务器通过稳定部署入口安装依赖，并以服务账号运行自检，见 [生产部署手册](deploy-tms-production.md#31-安装-pdf-系统依赖)。

CI 在 Debian 13 容器中运行自检和 PDF 聚焦测试。安装 `poppler-utils` 后，聚焦测试会进一步核对真实 PDF 的分页、中文文字、表头、页码和插图。

运行时，每个 Linux 实例按服务 UID 和私有媒体根目录协调一个并发渲染名额。共享同一实例的 Web worker 应使用相同的临时目录。PDF 子进程初始上限为 20 秒和 512 MiB 虚拟地址空间，输出限 24 MiB。正文大小、结构及图片上限也适用于 HTML 预览。

以 `DEBUG=True` 启动后，登录并从 `/demo/` 进入「文档转换实验」，或直接访问 `/demo/documents/`。检查两套模板的 HTML、PDF 预览及下载。Windows 可以运行 TMS 和 HTML 预览。通过 Debian 13（例如独立开发虚拟机）执行 PDF 自检和端到端验收。

```sh
DEBUG=True uv run pytest -o django_debug_mode=keep core/test_document_export.py demo/test_documents.py
```
