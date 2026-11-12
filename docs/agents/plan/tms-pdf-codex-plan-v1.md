# TMS 全局可复用 PDF 文档转换与模板预览服务 — Codex 实施 Plan（V1）

> **计划状态**：方案草案，可由 Codex 执行；不代表代码已修改。  
> **目标仓库**：`hdaojin/tms`  
> **目标分支**：`develop`  
> **审查基线**：2026-11-12，`develop` tree SHA `72b2b23e8bb50144bffab3e8aa32a57f599d5e40`。Codex 开始时必须重新核对仓库现状。  
> **任务边界**：只实现 Markdown/安全 HTML → 指定模板 HTML 预览 → PDF 预览/下载的全局通用能力；**不实现 DOCX、不接入具体 AI 模型、不创建独立文档管理 APP**。

## 0. 给 Codex 的执行指令

1. 先阅读仓库根目录 `AGENTS.md`，如涉及业务术语再读 `CONTEXT.md`、相关 ADR；遵守其“最小必要修改、聚焦测试、禁止无关重构”规则。
2. 审阅 `develop` 当前实际代码；下文文件路径只是 2026-11-12 的基线，若分支已变化，以代码为准，并在实施总结中说明差异。
3. 本 Plan 要求**实现并验证**通用服务；不要仅生成新的设计文档。必须完成至少一个 `DEBUG=True` 的端到端演示入口，验证选择模板、HTML 预览、PDF 预览、下载。
4. 任何有 UI/CSS 修改先按项目 `AGENTS.md` 使用全局 DaisyUI 技能、遵循 `docs/developer/ui.md`。若改动 Tailwind/Iconify 源码，重建对应 CSS 产物；PDF 专用打印 CSS 不强行依赖 Tailwind。
5. 不改动 `notes`、`training` 等业务 APP 的现有页面行为，不顺手统一其 Markdown 处理。优先建立新接口，现有调用保持兼容。
6. 不新增无业务必要的模型、迁移、导航菜单、全局 URL/公开转换端点、任务队列或文档中心。公共服务只负责转换，存储、授权和生命周期由业务 APP 决定。

## 1. 本次确认的架构与业务结论

### 1.1 核心原则

- **Markdown 是 AI 文档正文推荐的标准输入，不是 AI API 天然的数据格式**。AI 默认通常输出文本或可配置的结构化内容；后续接入 AI 时在 prompt/输出协议中明确要求正文使用 Markdown。
- PDF 转换器**不调用模型、不感知模型厂商、不直接保存 AI 对话**，只接收已确定的正文与元数据。
- 输入支持 `markdown` 和 `html_fragment` 两类；`html_fragment` 是受约束的 HTML 正文片段，**不接受任意完整网页、外部 CSS 或 JavaScript**。
- 内容、模板、排版相互解耦。文档使用稳定 `template_id` 选择**开发维护的可信模板**，不允许 AI/用户提供 Django 模板源码或 CSS。
- **先套模板，再预览，然后生成 PDF**：浏览器 HTML 模板预览用于快速检查；真正 PDF 预览用于核对分页、页码、表格跨页等，作为最终版式依据。
- HTML 预览和 PDF 输出应共享正文清理、元数据、模板注册信息及同一来源的排版 CSS；浏览器与 WeasyPrint 引擎不同，HTML 预览不保证像素级、逐页一致。
- 生成 PDF 是**纯转换服务**：输入数据 → PDF bytes；是否下载或保存，由调用 APP 决定。

### 1.2 V1 范围

**必须支持**：

1. Markdown 转 HTML；安全 HTML 片段作为输入；无脚本与网络依赖。
2. 显式指定文档模板，提供 `standard`（标准文档，默认）与 `formal`（正式业务文档）两个预置模板；正式模板**不是未经核对即宣称符合某项公文国家标准的模板**。
3. 标题、副标题/作者/日期/单位等有限的可选纯文本元数据；正文标题、段落、强调、链接、列表、表格、引用、代码块、分页、页码、基本中文排版。
4. 规范的受控图片能力（图片资源由业务 APP 已授权地提供，不能从 Markdown 任意访问远端 URL 或服务器文件）；支持 PNG/JPEG/WebP 等经检验的有限格式。图片缺失或过大必须有明确错误/警告，不可悄悄吞掉。
5. HTML 模板预览、PDF 最终预览、PDF 下载；模板切换时不需要重新让 AI 生成正文。
6. 兼容 TMS 当前 `markdown2`、Django 6、Python 3.13、`PrivateMediaStorage`、现有 PDF.js 预览组件和严格 CSP。
7. 有明确的转换失败反馈、大小限制、输入校验、安全限制与聚焦测试。

**明确不做**：DOCX、富文本所见即所得编辑器、AI 文档库/版本表、普通用户模板上传或模板管理后台、目录数据库、全站通用 PDF 转换 API/匿名 URL、异步任务系统、远程图片抓取、任意 CSS、JavaScript 渲染、自动生成复杂 Mermaid 图形、公式渲染引擎、PDF/A 等合规特性。

## 2. 已核实的仓库基线与复用范围

| 位置 | 已有能力/现状 | 本次动作 |
|---|---|---|
| `core/utils/markdown.py` | `render_markdown_text()` 基于 `markdown2`，返回 `RenderedMarkdown(html, meta, toc)`；异常后当前返回空字符串 | 复用；为 PDF 场景增加不破坏旧调用的**可选严格失败模式**，或通过外层可靠判断并抛出领域异常；不得把生成空白 PDF 视为成功 |
| `notes/utils.py` | `render_note_markdown()` 包含专用 URL 重写、Mermaid/details 逻辑 | 维持现状，公共 PDF 服务不依赖讲义 APP 的私有规则 |
| `training/process_views.py` | 有局部 `markdown(text)` 适配并进行 HTML 转义、简单链接处理 | 不修改，公共 PDF 服务拥有独立、严格的输入清理边界 |
| `core/uploads.py` | `PrivateMediaStorage`，文件签名校验等基础设施 | 将来由业务 APP 复用保存；公共转换器不负责持久化 |
| `core/file_preview.py` | `build_inline_preview_response()`、`build_download_response()`、PDF 类型识别 | 已保存 PDF 的预览/下载可复用；临时内存结果由业务视图包装响应 |
| `templates/components/pdf_preview.html` | PDF.js 页面组件，接收 `file_preview.preview_url` | 可复用 UI，必要时增加向已生成的 Blob URL 传值的**轻量适配**；不得重写 PDF.js |
| `static/js/pdf-preview.mjs` | 导出 `initializePdfPreview(root, pdfjs)`；目前从 `data-pdf-url` 加载同源 PDF | 演示页可按需导入该函数并使用浏览器内存 Blob URL；注意清理对象 URL、避免资源泄漏 |
| `templates/layouts/print.html` | 现有网页打印布局，继承完整站点基础布局 | 保持兼容；独立新增文档 HTML 外壳，避免混入导航、HTMX、Alpine 与 Tailwind 运行脚本 |
| `demo/urls.py`, `demo/views.py` | `demo` 只在 `DEBUG=True` 时加载 | 第一批端到端验证可增加演示入口；正式环境不暴露 |
| `tmsproject/settings.py` | `PRIVATE_MEDIA_ROOT`、CSP、Django 6 设置 | 必要时新增明确的限制参数；不要放宽现有 CSP |
| `pyproject.toml`, `uv.lock` | Python 3.13、`markdown2` 已存在，没有 WeasyPrint | `uv add weasyprint`，审查并提交锁文件 |

基线特别注意：`core/utils/markdown.py` 当前默认 extras 比一般印刷文档多（如 `mermaid` 仅 notes 场景、`toc`、`metadata`、`admonitions`、`highlightjs-lang` 等），**文档转换应通过 `extensions=` 显式提供受控的打印预设**，而不是假定浏览器插件生成的所有 HTML 都能被 WeasyPrint 绘制。

## 3. 推荐的新代码结构（按实际仓库作最小调整）

```text
core/
  documents/
    __init__.py              # 暴露稳定的全局调用接口
    types.py                 # DocumentInput / DocumentAsset / DocumentTemplate 等轻量类型
    service.py               # 准备正文、套模板、返回 HTML/PDF
    security.py              # HTML 标签/属性净化与受限图片引用
    templates.py             # 内置模板注册、白名单及受控样式读取
    exceptions.py            # 可识别的输入错误/资源错误/渲染错误
  test_document_export.py    # 聚焦测试（也可根据风格拆分）
  utils/markdown.py          # 仅必要的兼容性扩展

templates/documents/
  base.html                 # 独立、无脚本的完整 HTML 文档外壳
  standard.html             # 标准文档版式
  formal.html               # 正式业务文档版式

static/css/documents/
  base.css                  # 公共打印布局、正文、代码/表格样式
  standard.css              # 标准模板差异样式
  formal.css                # 正式模板差异样式

demo/
  ...                       # 新增「文档转换实验」页面、POST 预览/导出路由及聚焦测试

docs/developer/
  document-export.md        # 使用说明、模板扩展、资源与安全约束
```

不强制拆成大量小文件；若 `types/service/security` 数量已经足够清晰，则按 `AGENTS.md` 的最小修改原则适度合并。

## 4. 后端服务接口契约

以下为**建议的语义接口**，Codex 可按项目风格选择具体实现命名，但须保持职责及测试可见性。

```python
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Mapping

@dataclass(frozen=True)
class DocumentAsset:
    content: bytes
    media_type: Literal["image/png", "image/jpeg", "image/webp"]

@dataclass(frozen=True)
class DocumentInput:
    title: str
    content: str
    content_format: Literal["markdown", "html_fragment"] = "markdown"
    template_id: str = "standard"
    author: str = ""
    organization: str = ""
    document_date: date | None = None
    assets: Mapping[str, DocumentAsset] = field(default_factory=dict)

# 服务入口（仅示意，不是现有代码）
def render_document_html(document: DocumentInput) -> str: ...
def generate_document_pdf(document: DocumentInput) -> bytes: ...
def list_document_templates() -> tuple[...]: ...
```

具体要求：

- `render_document_html()` 返回**包含完整文档外壳的 HTML**，用于受隔离的 HTML 预览；正文必须已净化。
- `generate_document_pdf()` 使用相同的可信内容准备步骤与注册模板，返回 `bytes`，首部为 `%PDF-`。两者不能各自重新实现 Markdown 规则。
- 必要时内部使用 `prepare_document()` 返回不可变的中间对象，便于 HTML 预览和 PDF 导出共用“净化后的 HTML 正文 + 元数据 + 模板”。
- `template_id` 必须来自明确的注册表，未知 ID **直接报错**，不可把用户传入值拼成模板文件路径。
- `title/author/organization` 一律为文本，使用 Django autoescape，绝不由 AI 注入模板代码。标题为空、内容无效、输入过大应有明确的验证错误。
- PDF 输出不写磁盘、不建记录、不绑定用户；将 PDF 数据保存到 `PrivateMediaStorage` 是业务 APP 的独立步骤。
- 响应包装由业务 APP 完成；`Content-Type: application/pdf`，下载时使用安全文件名及 `Content-Disposition: attachment`；在线预览设置 `inline`、`Cache-Control: private, no-store`、`X-Content-Type-Options: nosniff`，遵循项目 CSP 和权限策略。
- 如果业务 APP 要归档 PDF，应保存其自身记录、授权范围和文件版本，不应在 `core` 中引入通用文件绑定模型。

## 5. Markdown/HTML 的处理原则

1. 调用现有 `core.utils.markdown.render_markdown_text()`，给 PDF 文档指定清晰的 Markdown extras 预设；保留站内其他调用的默认行为。
2. 解析失败应抛出可识别异常，而不是默默返回空 HTML。若修改旧函数，则新增 `strict=False` 等兼容参数并保留默认旧行为。
3. Markdown 允许普通格式元素、表格、代码围栏、引用和列表；文档标题来自 `DocumentInput.title`，不要依赖 Markdown YAML front matter 指挥模板或安全设置。AI 生成时建议 `content` 从正文第一节开始，避免封面标题重复；既有文档的 `#` 标题按正文标题正常处理。
4. 净化必须以**允许的标签和属性白名单**为核心：例如 `h1..h6`, `p`, `em`, `strong`, `ul`, `ol`, `li`, `blockquote`, `table`, `thead`, `tbody`, `tr`, `th`, `td`, `pre`, `code`, `br`, `hr`, `a`, `img` 等；确认表格 `colspan/rowspan` 等属性的处理。优先考虑经维护的成熟 HTML sanitizer 或充分测试的白名单实现，不使用简单正则过滤 HTML。
5. 禁止 `<script>`, `<style>`, `<iframe>`, `<object>`, `<embed>`, `<link>`, `<base>`, `<meta>`, `<form>`、事件处理器、任意 `style`、不可信 `class`、JavaScript URL、CSS `url()`/`@import` 等；高风险元素应连同其危险子内容移除。
6. `href` 只允许明确白名单（如 `https:`, `http:`, `mailto:`, 合法的 `#anchor`），**链接是注释/跳转，不是资源抓取许可**。去除控制字符与协议混淆；不要把任意 URL 用作图片、字体或样式来源。
7. 图片通过业务 APP 显式提供的 `assets` 映射解析（例如 Markdown `![拓扑](tms-asset:topology)`）；解析器只允许引用映射中的经过授权、校验及大小限制的资产。拒绝 HTTP(S)、`file:`, UNC、相对磁盘路径、用户原始 `data:` 等任意抓取方式。可由服务内部将受控图片变成可信内嵌 data URI 或使用**拒绝所有其他来源**的资源加载器。
8. 图片检查 MIME 与实际文件格式，限制大小/数量/解码像素数，并防范图像解压炸弹。不允许任意 SVG、EPS 或 PDF 作为输入图片。发生资源缺失/拒绝时，提供用户可理解的错误，不要静默生成不完整报告。
9. Mermaid、MathJax、Prism 高亮等浏览器 JavaScript 依赖**不在 V1 直接执行**。Mermaid 围栏保留可读代码/明确提示；若后续要导出图形，应增加经过审核的独立图像渲染步骤。
10. 保障中文字符、URL、表格内容和代码中的 `< > &` 正常转义；不得通过 `mark_safe` 绕过未经净化的正文。可考虑最终可信 HTML 标记仅在净化与资源检查**全部完成**后交给模板。

## 6. 模板系统与两级预览

### 6.1 可信模板注册表

两个预置模板：

| ID | 名称 | 主要用途 | 说明 |
|---|---|---|---|
| `standard` | 标准文档 | 训练总结、AI 报告、技术笔记 | A4、简洁现代、适量留白、正文与代码友好 |
| `formal` | 正式文档 | 会议纪要、内部报告、通知草稿 | A4、中文字体、较正式标题与段落行距、可选单位/日期 |

注册表描述模板 ID、中文显示名、Django 模板路径、可信 CSS 路径和默认页面参数。新增模板需新增源码并通过审查；V1 不接受用户上传模板文件，不做数据库配置页面。

### 6.2 HTML 模板预览（快速）

1. 流程：`DocumentInput` → Markdown 转换 → 净化及资产解析 → 查注册模板 → `django.template.loader.render_to_string` → 完整 HTML。
2. 页面展示“模板选择器”和“HTML 预览”；切换 `template_id` 后**无需重新调用 AI**，只重新套用模板。
3. 预览内容必须在隔离的 `iframe` 中显示（推荐仅允许 `allow-same-origin`，**不允许 `allow-scripts`**；确保预览响应或 `srcdoc` 的安全策略与静态资源正常加载）。禁止将未经净化 HTML 直接加入 TMS 主 DOM。
4. HTML 外壳只加载已知可信 CSS 和受控图片，不加载全站 `layouts/base.html`、Alpine、HTMX、DaisyUI 的运行脚本。
5. 用 CSS 呈现 A4 纸张宽度、背景、正文、标题、页边距等；**浏览器屏幕预览不保证真实自动分页**。界面应明确提示“实际分页请以 PDF 预览为准”。
6. 同一个模板的 `base.css` + `template.css` 应在浏览器预览和 WeasyPrint 之间**保持单一来源**：浏览器使用静态资源链接，WeasyPrint 从可信本地样式读取并传入；根据 `@media screen`/`@media print` 做少量引擎差异处理。
7. CSP 默认较严格：不得通过放宽 `script-src`、开放远程样式或 `unsafe-inline` 解决预览。预览 CSS 最好来自本地静态资源；新 CSS 文件与部署流程一并检查。

### 6.3 PDF 最终预览（准确）

1. 使用同一个 `DocumentInput` 生成 PDF 字节数据。
2. 不为临时预览新建数据库表、永久文件或可猜测的公共 URL；演示页面通过已登录、CSRF 保护的 POST 生成数据，浏览器拿到 `application/pdf` 响应后通过 Blob URL 传给现有 PDF.js 预览初始化函数。
3. 复用 `static/js/pdf-preview.mjs` 已有 `initializePdfPreview(root, pdfjs)` 的单页 canvas 预览、翻页和内存限制。若需要新增动态渲染生命周期，做轻量适配，不复制 PDF.js 实现；换文档、换模板及页面离开时释放旧 Blob URL/渲染资源。
4. 允许用户“预览 PDF”与“下载 PDF”，下载使用当前输入与模板生成的相同文件内容。禁止未经授权直接读取其他业务 APP 的文件。
5. 生成中、转换失败、内容为空、模板不存在、图片无效、系统字体缺失时给出明确提示。

### 6.4 打印 CSS 最小规范

- 默认 A4 纵向；设置页边距、正文中文字体、行距、字号、标题层级。
- `@page` 支持页码；正式模板可有可信可选页眉/页脚。
- 表格边框与单元格留白，跨页时尽可能保留表头（可使用 `thead` 和符合引擎特性的 CSS）。
- 标题避免孤立页尾，代码块保留换行并合理断行，长 URL/大图不会导致页面横向溢出。
- 字体推荐选择系统安装的 Noto CJK，先验证 Debian 13 实际字体名、衬线/无衬线回退与字形覆盖；浏览器与服务器字体来源可能不同，不能承诺完全一致。

## 7. WeasyPrint 集成与部署

1. 添加 WeasyPrint Python 运行时依赖，通过 `uv add weasyprint` 更新 `pyproject.toml`、`uv.lock`，不得手动编辑锁文件。
2. 以 WeasyPrint 70.0 官方 API 为核对基线，最终以当时最新兼容版本和实际锁定版本为准；注意其 70.0 安全更新与图片资源加载注意事项。
3. 通过 Python API 从可信完整 HTML 和可信本地 CSS 生成 bytes；资源加载器默认**拒绝 HTTP(S)/FTP/file/未知协议**，只处理业务已经授权提供的图片资产。不要直接启用默认任意资源抓取。
4. 强制处理有界输入。建议从保守上限起步：正文 1 MiB UTF-8；图片单张不超过 5 MiB，总量不超过 20 MiB，数量不超过 20；最终限制和阈值应集中配置，并通过实际测试调整。上限只是服务层输入约束，不替代外部资源隔离或主机级运行保护。
5. WeasyPrint 大文档转换为 CPU/内存密集操作；第一版仅供受授权的内部业务场景，避免一次发起无限并发请求。遇到明确耗时或并发压力再评估后台执行/隔离 worker，不为 V1 引入队列。
6. Debian 13 使用发行版的 Pango 依赖与中文字体。使用系统包（具体包名、可用版本按部署镜像检查），例如 `libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz-subset0`, `fonts-noto-cjk`；应用的 WeasyPrint 仍由 `uv` 管理。若测试/生产部署采用精简发行版，必要时检查底层运行库的实际包依赖。
7. 对 Windows 开发环境做明确说明：WeasyPrint 依赖原生 Pango 等库，**不能假定 `uv add` 后 Windows 即可运行**。优先建议通过 WSL2 Debian 或与服务器一致的 Linux 环境进行 PDF 集成验证；也可按 WeasyPrint 官方 Windows 指引配置原生环境。
8. 更新与部署相关文档（至少 `docs/developer/document-export.md`；如现有生产部署文档需要声明系统依赖，做最小必要增补），确保首次部署、升级和验证步骤可复制。

## 8. DEBUG 演示页：验证完整复用流程

为了让用户先直观看到效果，**V1 应提供一个仅开发环境启用的真实端到端演示页**，而不是把全局 PDF 服务绑定到尚未完成的 AI APP。

建议新路径（仅供参考）：`/demo/documents/`。

页面包含：

- Markdown / HTML 片段输入模式（默认 Markdown）；
- 一个示例文档（中文标题、段落、列表、表格、代码块、跨页内容）；
- 文档标题、可选元数据；
- 内置模板选择器（`standard` / `formal`）；
- “更新 HTML 预览”“预览 PDF”“下载 PDF”三项有效操作；
- 清晰的状态、错误提示；HTML iframe 快速预览与 PDF.js 最终预览区域。

实现要求：

- `demo` APP 仅在 `DEBUG=True` 注册，且各演示 View 本身仍需检查 `settings.DEBUG`；保持 TMS 的登录中间件和 CSRF；不要把演示端点作为开放的通用生产 PDF API。
- 可使用 Django Form + HTMX 改变 HTML 预览；前端只做状态/Blob 管理，服务端仍控制净化、模板与资源校验。
- 如 PDF.js 使用动态新建的根节点，复用并按需调用现有导出的初始化器；切换模板时移除旧预览并释放内存对象 URL。
- 无 JavaScript 时保留基本的“表单提交 → 服务端 HTML 响应”或下载能力（以现有 UI 规范可行的最小方式实现）。
- 页面样式复用现有 DaisyUI/Tailwind UI 组件，遵循 `docs/developer/ui.md`；打印 CSS 不依赖 DaisyUI 组件体系。
- 不修改 `demo` 之外其他业务入口；生产接入由后续 AI/Training/Meetings 等 APP 独立发起。

## 9. 将来 AI 接入时的数据协议（仅约定，不实现模型调用）

推荐 AI 文档正文用 Markdown，且标题/模板 ID 不内嵌在正文中：

```json
{
  "title": "网络系统管理训练分析报告",
  "content_format": "markdown",
  "content": "## 一、训练概况\n\n本周主要完成……",
  "template": "standard"
}
```

要求：

1. 这是**TMS 自定义文档数据协议**，不是模型原生保证的格式。一般文字生成接口不会天然承诺始终 Markdown。
2. 若 AI 能返回结构化 JSON，则使用 JSON Schema/应用层校验，提取 `content` 等字段。若当前模型只返回文字，则在提示词中要求 Markdown，校验/规范化后交给文档服务；绝不把任意 AI 文本当安全 HTML。
3. 流式输出期间 Markdown 片段可能尚未闭合（代码围栏、表格、列表），不能假设每个增量 chunk 都是可独立转换的有效文档；V1 在生成完毕后触发正式预览和 PDF 导出。
4. 模板选择应由用户/业务规则确认，并通过已登记 `template_id` 指定，不能直接信任 AI 生成的模板路径、CSS 或动态 Django 模板。
5. TMS 保存文档内容及版本属于未来 AI 文档业务设计范畴；当前公共服务不保存正文及导出历史。

## 10. 实施顺序

### 阶段 A — 依赖与 API 骨架

- [ ] 核对当前 `develop`、`AGENTS.md`、`core/utils/markdown.py`、`core/file_preview.py`、`static/js/pdf-preview.mjs`。
- [ ] 新增 WeasyPrint，并完成 Linux/开发环境原生依赖验证。
- [ ] 实现类型/异常、可信模板注册表及稳定的公共服务调用入口。
- [ ] 仅必要地扩展 Markdown 严格错误行为，保护原 API 测试。

### 阶段 B — 安全内容与资源

- [ ] Markdown → HTML，HTML 片段 → 净化 HTML，统一元数据与模板输入校验。
- [ ] 实现图片资源白名单映射、大小/MIME/像素检查和**禁止任意 URL/本地文件抓取**的加载策略。
- [ ] 实现 HTML 预览输出与 WeasyPrint PDF bytes 输出，异常必须清晰，不静默导出空 PDF。

### 阶段 C — 文档模板

- [ ] 实现 `standard` 与 `formal` 两套可信模板及公共打印 CSS。
- [ ] 实现 A4/中文字体/页码/标题/表格/代码/图片/跨页处理。
- [ ] 保证 HTML 浏览器预览与 PDF 使用相同来源的正文与样式，明确分页差异。

### 阶段 D — 演示和最终预览

- [ ] 仅在 `DEBUG=True` 的 `demo` 中新增文档实验页。
- [ ] 添加指定模板的 HTML iframe 预览，模板切换不重新解析/生成 AI 内容。
- [ ] 添加 PDF.js 最终预览，尽可能复用现有 `initializePdfPreview()`，无需临时模型/长期文件。
- [ ] 添加 PDF 下载、错误反馈、内存清理及响应头测试。

### 阶段 E — 验证、文档与交付

- [ ] 增加转换服务及 demo 端点聚焦测试。
- [ ] 使用 Debian 13 + 中文字体至少人工生成并核查两套模板的样本 PDF。
- [ ] 补充 `docs/developer/document-export.md` 使用示例、AI 输入约定、安全边界及部署依赖。
- [ ] 如确实新增 Tailwind/Iconify class，执行 `npm run build:css` 并提交对应生成产物；不触及则不要无意义重建。
- [ ] 报告修改文件、测试结果、尚未实现事项和集成注意事项。

## 11. 测试验收清单

**输入与兼容**

- [ ] Markdown 标题、表格、列表、代码块、中文、特殊字符正常生成 HTML/PDF。
- [ ] `html_fragment` 输入可以正常转换，且 HTML 正文危险标签和属性被移除。
- [ ] 无内容、非法模板 ID、缺少标题、超长文档、未知图片 ID 失败有明确异常，不成功生成空白 PDF。
- [ ] 原 `notes` 和 `training` 中 Markdown 渲染行为保持不变。
- [ ] 两套模板都可用；模板切换只影响版式，不改变正文内容。

**版式与预览**

- [ ] HTML 预览 A4 纸张样式、字体、表格、代码块、图片基本正确。
- [ ] PDF 真正采用 A4；有页码；长文跨页合理；中文不缺字、不乱码。
- [ ] PDF.js 能在未持久化前预览生成结果；多次生成/模板切换不会重复初始化或泄漏旧 Blob URL。
- [ ] PDF 下载文件头 `%PDF-` 且响应头/文件名正确；无缓存泄露。
- [ ] 缺失中文字体/底层库时给出可定位的服务错误及运维说明。

**安全**

- [ ] Markdown 与 HTML 中的 `<script>`, `onerror`, `javascript:`, `<iframe>`, `<style>`, `<base>` 等不会执行或影响服务。
- [ ] 测试 `file:///etc/passwd`、`http://127.0.0.1/`、`http://169.254.169.254/`、`http://localhost/`、重定向/协议混淆、绝对路径、相对路径等引用，确认转换器**不会发起读取或请求**。
- [ ] 限制原始 `data:` 与任意外部字体、样式或图像。
- [ ] 非法图片 MIME、伪造扩展名、超大/压缩炸弹图片被拒绝。
- [ ] 预览 iframe 无脚本执行权限；HTML 不泄漏敏感数据；生产模式不注册 demo 端点。
- [ ] 用户无相应业务授权时不可通过后续业务接入页面生成/访问其他业务对象的内容；权限由调用 APP 测试保护。

**回归与项目规范**

- [ ] `uv run pytest core/test_document_export.py <demo相关测试>`（按最终文件路径替换）及与 `core.utils.markdown` 直接相关的旧测试。
- [ ] `uv run ruff check <实际修改的Python路径>`。
- [ ] 修改项目设置或 URL 时运行 `uv run manage.py check`。
- [ ] 修改 CSS/UI 后按 `AGENTS.md` 做必要构建，重点验证 TMS 严格 CSP。
- [ ] 不因本任务强制全量跑所有无关业务测试；如果公共核心变更造成可观跨 APP 回归风险再扩大范围。

## 12. 完成定义（Definition of Done）

符合以下要求才算完成：

1. 任意后续业务 APP 只需构建 `DocumentInput` 并调用公共接口，即可得到指定模板的 HTML 预览或 PDF bytes；不依赖 AI APP 或 `demo` 的代码。
2. `standard`/`formal` 可选，HTML 预览和 PDF 输出共用模板/样式来源，最终 PDF 预览采用真实 PDF。
3. 在 `DEBUG=True` 下可通过演示页完成输入、选模板、HTML 预览、PDF 预览、下载全流程。
4. 不能利用 Markdown/HTML/PDF 转换功能触发 SSRF、任意本地文件读取、脚本执行或未授权业务文件访问。
5. PDF 内容包含中文、表格和多页时正常；Python/系统依赖可在 Debian 13 部署，Windows 开发限制记录清楚。
6. `pyproject.toml` 和 `uv.lock` 一致；相关测试通过；开发使用文档完成。
7. **不含 DOCX，不含业务文档数据表，不含 AI API 调用，不含通用公开转换端点。**

## 13. 可直接给 Codex 的启动提示词

> 请在当前 TMS 仓库的 `develop` 分支按照 `TMS_Global_PDF_Conversion_Service_Codex_Plan.md` 执行 V1 的全部实施内容。首先阅读 `AGENTS.md` 并审查当前代码，尤其是 `core/utils/markdown.py`、`core/uploads.py`、`core/file_preview.py`、`static/js/pdf-preview.mjs`、`demo`。在 `core` 中建立不依赖任何业务 APP 的 Markdown/安全 HTML → 指定模板 HTML 预览 / WeasyPrint PDF 转换服务；实现 `standard` 和 `formal` 两套文档模板、受控图片资源、HTML 安全处理、中文 A4 打印版式，以及仅 `DEBUG=True` 可见的端到端 demo。复用既有 PDF.js，提供真实 PDF 预览和下载。严格遵守计划的权限、CSP、资源访问、最小修改和测试约束；不要做 DOCX、AI 接口对接、文档管理数据模型或无关重构。实施完成后报告改动文件、测试结果和部署要求。

---

### 资料与技术参考

- TMS develop：<https://github.com/hdaojin/tms/tree/develop>
- Django 6 模板文档：<https://docs.djangoproject.com/en/6.0/topics/templates/>
- WeasyPrint 70 安装与依赖：<https://doc.courtbouillon.org/weasyprint/stable/first_steps.html>
- WeasyPrint 70 Python API：<https://doc.courtbouillon.org/weasyprint/stable/api_reference.html>
- OpenAI API Text Generation：<https://developers.openai.com/api/docs/guides/text>
- OpenAI API Structured Outputs：<https://developers.openai.com/api/docs/guides/structured-outputs>
