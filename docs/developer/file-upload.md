# TMS 通用文件上传设计

## 目标

TMS 的文件上传能力统一由一个公共组件提供，业务 APP 不分别实现上传交互。

目标体验：

- 点击选择文件；
- 拖放文件；
- 点击或聚焦目标上传区域后支持 Ctrl+V / Cmd+V 粘贴截图或普通文件；
- 多文件队列；
- 图片缩略图预览；
- 删除待提交文件；
- 文件类型、单文件大小、数量等浏览器端即时提示；
- 普通 Django 表单和 HTMX 表单均可复用；
- JavaScript 失效时仍保留原生 `<input type="file">` 的基本上传能力。

本设计采用 FilePond v5 作为浏览器端底层实现。对应架构决策见 `docs/adr/0004-filepond-v5-unified-upload.md`。

## 核心原则

### 1. FilePond 不进入业务层

业务 APP 继续定义 Django Form / ModelForm：

```python
attachments = MultipleFileField(
    label="附件",
    upload_spec=ATTACHMENT_UPLOAD_SPEC,
    required=False,
)
```

业务模板继续通过 `components/form.html` / `components/field.html` 渲染字段。

业务 APP 不应该：

- 自己 `import filepond`；
- 自己调用 `defineFilePond()`；
- 自己监听 FilePond 内部事件来完成业务保存；
- 自己维护另一套拖放、粘贴、预览组件。

FilePond API 只允许出现在 TMS 的公共上传适配层中。

### 2. 服务端规则永远是最终事实来源

现有后端体系保持：

```text
MultipleFileField
    -> UploadSpec
        -> 扩展名校验
        -> 单文件大小校验
        -> 文件签名校验
    -> 业务 Form.clean()/service
        -> 数量、累计大小、对象归属等业务规则
```

FilePond 的 accept、size、count 等 validator 只是提前给用户反馈。任何前端限制都可以被绕过，所以服务端必须继续完整校验。

### 3. 第一阶段不改变上传协议

FilePond 第一阶段仍使用浏览器原生表单提交，具体链路是：

```text
FilePond entries
    -> form-associated custom element
    -> ElementInternals.setFormValue(FormData)
    -> multipart/form-data
    -> Django request.FILES
    -> Django Form
```

普通表单继续使用 `enctype="multipart/form-data"`。

HTMX 文件表单同时使用：

```html
hx-encoding="multipart/form-data"
```

`components/form.html` 可以在 `form.is_multipart` 时统一输出该属性；普通浏览器提交会忽略 `hx-encoding`，因此不需要业务页面分别判断。

暂不增加上传临时表、上传 token、独立 upload endpoint、后台清理任务等异步上传基础设施。

## FilePond v5 的表单关联机制

FilePond v5 的 `<file-pond>` 是 form-associated custom element。组件升级时会读取并移除 slot 中的原生文件 input，把 `name`、`id`、`accept`、`multiple`、`required` 等语义转移到主机，并通过 `ElementInternals.setFormValue()` 将当前 entries 写入表单 `FormData`。

因此 TMS 不绑定 FilePond Shadow DOM 内部 input，也不加载 `FileInputStore`。选择、拖放和粘贴得到的文件都由同一 entries 列表进入普通或 HTMX multipart 提交；JavaScript 完全加载失败时，未升级的原生 input 仍保留基础上传能力。

## 前端依赖管理

### npm

在 `package.json` 中增加 FilePond v5 beta 依赖。

TMS 接受跟随 beta channel，但仍保留 `package-lock.json`：

- `package.json` 表达“跟随 beta”；
- `package-lock.json` 固定某次提交实际验证过的版本；
- 升级 FilePond 时显式更新 lockfile，并执行上传组件聚焦回归。

不从 CDN 运行生产依赖，避免 TMS 运行时依赖外网。

### 第一阶段不引入 JS bundler

TMS 当前没有 Vite/Webpack/Rollup 的必要。FilePond v5 官方 ESM 可以直接部署，因此第一阶段保持现有轻量前端构建方式。

建议增加：

```text
scripts/sync-filepond.mjs
```

负责把 npm 包中的 FilePond ESM 发布文件同步到：

```text
static/vendor/filepond/
```

同步整个所需 ESM 目录，不手工挑选上游内部文件，以免 beta 升级时遗漏依赖。

可增加 npm 命令：

```text
sync:filepond
build:frontend = sync:filepond + build:css
```

是否提交 `static/vendor/filepond/` 以当前部署流程为准；原则是生产环境不能直接暴露 `node_modules/`。

未来只有当前端 npm 依赖明显增加、tree-shaking 收益足够大或模块管理变复杂时，再单独评估 Vite/其他 bundler，不因 FilePond 一个依赖就立即改造整个前端工具链。

## 公共组件结构

建议最终结构：

```text
templates/components/form.html
templates/components/field.html
templates/components/file_upload.html

static/js/filepond.js
static/css/main.css
static/vendor/filepond/

core/forms/fields.py
core/uploads.py
```

### `components/field.html`

仍由它识别 Django file field，并把上传字段交给 `components/file_upload.html`。

### `components/file_upload.html`

建议从当前“根据 name 重新生成一个 `<input>`”改为**接收 Django BoundField 本身**：

```django
{% include "components/file_upload.html" with field=field %}
```

组件内部结构概念上为：

```django
<file-pond data-tms-file-upload>
  {{ field }}
</file-pond>
```

这样可以完整保留 Django widget 已经生成的：

- `id`；
- `name`；
- `accept`；
- `multiple`；
- `required`；
- 其他 widget attrs。

FilePond 升级该原生 input 后继承这些字段语义，并通过 form-associated custom element 提交；业务模板仍不直接创建另一套字段或隐藏 input。

## TMS 与 FilePond 的配置边界

### 全局配置

`static/js/filepond.js` 负责：

1. 导入 FilePond v5；
2. 导入中文 locale；
3. 注册 `<file-pond>` Web Component；
4. 注册 TMS 统一启用的 extensions；
5. 为页面上的 `file-pond[data-tms-file-upload]` 应用 TMS 配置；
6. 保证初始化幂等；
7. 支持 HTMX 后续插入的新上传组件。

建议第一阶段全局启用：

- `ClipboardSource`；
- `FileSizeValidator`；
- `ListCountValidator`（当字段提供数量限制时使用）。

FilePond 默认已经包含 FileInputSource、DataTransferLoader、扩展名/MIME validator 和 EntryListView，不重复添加同类实现。

### 图片预览

使用 FilePond v5 官方模板：

```text
createFilePondEntryList()
+ appendEntryImageView()
```

不再由 TMS 自己用 `FileReader` / object URL 维护另一套缩略图列表。

非图片附件继续显示文件名、大小和状态。

### per-field 配置

业务规则来自 Python，前端配置通过原生 input 的属性或 TMS 自己的 `data-upload-*` 属性传递，不在模板中硬编码某个 APP 名称。

建议支持：

```text
data-upload-max-size-mb
data-upload-max-files
data-upload-max-total-size-mb
data-upload-paste
data-upload-preview
```

其中：

- `accept` 继续直接来自原生 input；
- 单文件大小优先由 `UploadSpec` 自动输出 `data-upload-max-size-mb`，避免 Python/JS 各维护一份；
- `multiple=false` 时前端自然限制为单文件；
- 某些 APP 特有的最大文件数、累计大小可以按需提供 data attr，但服务端仍必须校验。

不要把这些属性命名为 `data-filepond-*`，避免业务 Form 与第三方库名称耦合。TMS adapter 再把 `data-upload-*` 翻译成 FilePond options。

## Ctrl+V 粘贴策略

### 默认启用范围

Ctrl+V 同时用于截图和操作系统剪贴板提供的普通文件。

默认所有上传字段启用粘贴：缺省、`auto` 和 `true` 都表示启用，`false` 表示显式禁用。文件是否允许加入仍由字段的 `accept`、前端 validator 和服务端校验共同决定。

### paste scope

必须避免页面上多个 FilePond 同时接收同一次粘贴。

TMS 的 `ClipboardSource.shouldHandlePaste` 采用以下顺序：

1. 剪贴板不包含 `File` 项时不接管，普通文本粘贴保持浏览器默认行为；
2. 用户必须先点击或通过键盘聚焦目标上传区域；
3. 只有焦点所在上传区域的 FilePond 接收该次粘贴；
4. 页面存在多个上传器时不做唯一候选猜测，因此不会重复添加或投递到错误字段。

上传区域应可获得焦点，并显示简短提示，例如：

```text
先点击上传区域，再按 Ctrl+V / Cmd+V 粘贴截图或文件
```

粘贴图片与点击选择的图片进入同一个 FilePond entries 队列，后续处理完全一致。

## HTMX 生命周期

FilePond v5 使用 Web Component。`defineFilePond()` 注册后，浏览器会自动升级当前和之后出现的 `<file-pond>` 元素。

TMS 仍需给每个实例绑定 `ClipboardSource`、校验、浏览按钮和交互状态等 per-instance 配置，因此 `static/js/filepond.js` 提供一个幂等初始化函数，例如：

```text
initFilePonds(root)
```

调用时机：

- DOMContentLoaded；
- `htmx:afterSwap`，仅扫描 swap 的目标区域。

每个组件使用 WeakSet 或明确的 configured 标记避免重复绑定。

不把 FilePond 的初始化继续塞进越来越大的 `static/js/app.js`；上传组件拥有自己的 `static/js/filepond.js`。

当前 `app.js` 中旧的 `initFileUploads()` 在 FilePond 完成迁移后删除，避免两套文件列表 UI 同时工作。

## 表单提交与错误行为

### 普通 POST

原生 form：

```text
multipart/form-data -> request.FILES -> form.is_valid()
```

FilePond 不单独请求服务器。

### HTMX POST

multipart HTMX form：

```text
hx-encoding="multipart/form-data"
    -> FormData
    -> request.FILES
    -> form.is_valid()
```

仍遵循现有 TMS 规则：校验失败只返回表单 fragment。

浏览器出于安全原因不会在服务器校验失败后的新页面/fragment 中恢复本地文件选择；因此附件字段校验失败后需要重新选择/粘贴文件。这属于普通文件表单行为，不为此引入临时上传系统。

## “待上传文件”和“已保存附件”必须分开

编辑页面中：

- FilePond 只表示**本次准备新增/替换、尚未保存的文件**；
- 已经持久化的附件继续由业务页面的附件列表显示；
- 删除已保存附件必须调用现有有权限校验的 Django endpoint/service；
- 不能把 FilePond 的“移除队列文件”误认为删除服务器已有文件。

第一阶段不把已保存附件 preload 成 FilePond entries。

这样可避免临时队列状态与数据库状态混在一起。

## 样式与 DaisyUI

FilePond v5 使用 Web Component / Shadow DOM。TMS 不试图向 Shadow DOM 内部注入 Tailwind class。

统一通过：

- FilePond 提供的 CSS custom properties；
- `file-pond::part(...)`；
- DaisyUI 当前主题 CSS variables；

让上传区域与 TMS 的 `base-*`、`primary`、`error`、圆角和明暗主题保持一致。

保留 FilePond 原生上传区域和内置“浏览文件”入口，不在外部重复增加按钮。上传区域的边框、圆角和焦点态复用 DaisyUI 表单字段 token；说明文字保持正文样式，仅通过 locale 中的 `browse-label` part 为“浏览文件”提供主色及悬停强调。图片队列使用固定小缩略图，`<file-pond noattribution>` 关闭默认品牌标识。

样式集中放在 `static/css/main.css` 的明确 FilePond 区域，不由各 APP 覆盖。

## JavaScript 与 CSP

项目规范已调整为“默认外置、按需内联”。FilePond 是跨页面复用的基础能力，因此主体实现仍应放在 `static/js/filepond.js`，这是可维护性选择，而不是因为禁止 inline script。

如果某个页面未来只有几行强页面耦合的 FilePond 配置，允许合理内联，不需要为了形式统一制造额外抽象。

若部署实际启用 Content-Security-Policy：

- 图片预览需要在 `img-src` 中允许 FilePond 所需的 `blob:` / `data:` 图像来源；
- `workersURL` 指向 TMS 本地 static 的 FilePond workers；当前 beta 的图片预览仍会回退到 Blob Worker，因此 `worker-src` 同时允许 `'self'` 和 `blob:`；
- `script-src` 不因 FilePond 放宽为 `blob:`；
- 具体 CSP 以实际启用的 header 为准，不仅凭代码风格假设。

## 无障碍和降级

- 保留原生 file input 作为 Web Component slot 内容；
- `<label>` 与 field id 保持关联；
- 必填、multiple、accept 等语义继续存在于原生 input；
- FilePond JS 加载失败时仍能进行基础文件选择和表单提交；
- 不用 div + click 模拟真正的文件输入。

## 第一阶段不做的事情

暂不实现：

- 上传即保存；
- 临时附件 token；
- FormPostStore 异步上传；
- ChunkedUploadStore 分块上传；
- 断点续传；
- 图片裁剪/编辑；
- 自动压缩和格式转换；
- 从 URL 抓取远程文件；
- 全局上传任务中心。

这些能力 FilePond v5 可以支持或扩展，但必须由真实业务需求触发。

## 后续异步上传升级路径

如果出现大文件、长时间上传或“先上传附件再编辑表单”的明确需求，再增加第二种模式：

```text
sync（默认）
async（按需）
```

异步模式可以评估：

- `FormPostStore`：普通异步 POST；
- `ChunkedUploadStore`：大文件分块；
- TMS 临时上传模型/token；
- 定时清理未绑定临时文件；
- CSRF、权限、幂等和最终绑定 service。

业务 APP 仍只选择上传模式，不直接操作 FilePond store extension。

## 建议的第一批验证场景

至少验证：

1. 单文件点击选择并提交；
2. 多文件点击选择并提交；
3. 拖放一个和多个文件；
4. 点击上传区域后 Ctrl+V 粘贴 Windows/浏览器截图；
5. 从操作系统复制普通文件，点击上传区域后粘贴，并与普通选择文件一起提交；
6. 删除待上传文件后不会进入 `request.FILES`；
7. 不允许的扩展名在前端提示，并且绕过前端后仍被 Django 拒绝；
8. 超过 `UploadSpec.max_size_mb` 前后端均拒绝；
9. 未聚焦上传区域时不接收文件，textarea 中 Ctrl+V 文本不被上传组件拦截；
10. 同页两个上传组件只由当前聚焦区域接收截图或文件；
11. HTMX swap 后新出现的上传组件正常工作且不会重复初始化；
12. HTMX multipart 提交能在 Django Form 中收到所有文件；
13. form reset 能清空待上传队列；
14. 服务端校验失败重新渲染表单时行为明确；
15. light/dark/DaisyUI 主题下上传组件可读；
16. JavaScript 加载失败时原生 file input 可用。

第一批业务验证优先选择已经真实使用 `MultipleFileField` 的论坛附件、通知附件等表单，不为了测试 FilePond 新建一套平行业务页面。

## 升级 FilePond beta

升级流程保持轻量：

1. 更新 `filepond@beta` 与 `package-lock.json`；
2. 重新同步 FilePond ESM static 资源；
3. 查看 v5 changelog / migration notes，重点关注 extensions、custom element 和 template API；
4. 运行上传组件相关后端测试；
5. 手工完成点击、拖放、Ctrl+V、HTMX swap 和 multipart 提交的最小回归；
6. 如果上游 beta API 改动，只修改 TMS adapter / component，不把兼容代码扩散到业务 APP。

TMS 是内部个人系统，因此不需要对 beta 升级采取企业级冻结策略，但仍要求每次仓库提交可复现、出问题可回退。
