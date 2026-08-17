# ADR 0004：使用 FilePond v5 统一 TMS 文件上传前端

- 状态：Accepted
- 日期：2026-08-15

## 背景

TMS 已有 `MultipleFileField`、`UploadSpec`、`components/file_upload.html` 和统一表单组件，但当前文件上传前端只提供基础文件选择和文件列表。新的通用需求包括：拖放文件、Ctrl+V 粘贴截图/图片、图片预览、即时类型/大小提示，并希望这些能力可以在论坛翻译、会议记录、通知、训练记录等不同 APP 中复用。

继续自行扩展 `static/js/app.js` 会逐步重复实现成熟文件上传组件已经具备的交互、状态管理、可访问性和浏览器兼容逻辑。

## 决策

TMS 采用 **FilePond v5** 作为通用文件上传组件的前端底层实现。

1. FilePond 只作为基础设施实现细节。业务 APP 统一使用 TMS 的 Django 表单字段和 `templates/components/file_upload.html`，不直接初始化或依赖 FilePond API。
2. 后端校验继续由 `MultipleFileField`、`UploadSpec`、文件签名校验及各业务 service 负责，FilePond 的校验只提供浏览器端即时反馈。
3. 第一阶段继续使用普通 `multipart/form-data` / HTMX multipart 表单提交，不因为引入 FilePond 而建立独立异步上传 API。
4. 使用 FilePond v5 form-associated custom element 的 `ElementInternals.setFormValue()` 将 entries 写入浏览器 `FormData`，继续按普通 Django multipart 表单提交；不依赖 FilePond 的 Shadow DOM 内部 input。
5. 启用 `ClipboardSource`。所有上传字段默认支持截图和普通文件粘贴，但只有先点击或聚焦目标上传区域后才接管包含文件的剪贴板事件；纯文本粘贴不受影响，同页多个上传组件也不会重复接收。
6. 图片预览使用 FilePond v5 官方 template 能力（`appendEntryImageView`），不自行维护另一套预览组件。
7. 初始前端扩展集合保持克制：Clipboard、单文件大小、文件数量，以及图片预览；异步上传、分块上传、图片编辑/压缩等只在实际业务需要时再启用。
8. 接受 FilePond v5 beta 的版本风险。`package.json` 可以跟随 `beta` channel，`package-lock.json` 固定每次提交实际使用的版本；升级后进行上传组件聚焦回归。
9. 第一阶段不为 FilePond 单独引入 Vite/Webpack 等 JS bundler。通过 npm 管理依赖，并把 FilePond ESM 资源同步到 Django static 目录；未来只有在前端依赖明显增加时再单独评估 bundler。
10. 前端脚本规范采用“默认外置、按需内联”，不以禁止 inline JavaScript 为目标。可复用和复杂逻辑仍应外置；很短、局部且与模板强耦合的初始化或配置允许内联。若实际启用 CSP，则以真实 CSP 策略为约束。
11. 当前 FilePond v5 beta 的图片预览仍可能创建 Blob Worker。CSP 仅在 `worker-src` 中允许 `blob:`，图片预览在 `img-src` 中允许 `blob:`，`script-src` 不因此放宽。

## 结果

- 各 APP 获得一致的上传体验和复用入口。
- Django 当前上传、校验、权限和存储体系无需被 FilePond 重构。
- HTMX 动态插入的 `<file-pond>` 元素可依赖 Web Component 注册机制自动升级，不需要为每次 swap 重写初始化流程。
- FilePond v5 beta 变化被限制在 TMS 的通用上传组件和前端适配层中，不向业务 APP 泄漏。

详细实现约定见 `docs/developer/file-upload.md`。
