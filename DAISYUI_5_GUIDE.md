# daisyUI 5 快速使用指南

## 🎨 主题切换

### 用户界面
在导航栏右侧点击主题选择器（调色板图标），可以选择以下主题：

**推荐主题：**
- **Light**: 默认浅色主题，适合日间使用
- **Dark**: 深色主题，适合夜间使用
- **Corporate**: 商务风格，专业严肃
- **Cupcake**: 温馨粉色，友好亲切
- **Forest**: 自然绿色，清新舒适

### 开发者
在模板中为 html 元素设置主题：
```html
<html data-theme="light">
```

## 🧩 组件使用

### 按钮
```html
<!-- 基础按钮 -->
<button class="btn">默认</button>
<button class="btn btn-primary">主要</button>
<button class="btn btn-secondary">次要</button>
<button class="btn btn-outline">轮廓</button>

<!-- 尺寸 -->
<button class="btn btn-xs">超小</button>
<button class="btn btn-sm">小</button>
<button class="btn btn-md">中等</button>
<button class="btn btn-lg">大</button>

<!-- 形状 -->
<button class="btn btn-circle">○</button>
<button class="btn btn-square">□</button>
```

### 卡片
```html
<div class="card bg-base-100 shadow-xl">
  <figure>
    <img src="image.jpg" alt="图片" />
  </figure>
  <div class="card-body">
    <h2 class="card-title">卡片标题</h2>
    <p>卡片内容描述</p>
    <div class="card-actions justify-end">
      <button class="btn btn-primary">操作</button>
    </div>
  </div>
</div>
```

### 表单
```html
<div class="form-control w-full max-w-xs">
  <label class="label">
    <span class="label-text">标签</span>
  </label>
  <input type="text" placeholder="请输入" class="input input-bordered w-full max-w-xs" />
  <label class="label">
    <span class="label-text-alt">帮助文本</span>
  </label>
</div>
```

### 导航菜单
```html
<ul class="menu bg-base-200 w-56 rounded-box">
  <li><a>首页</a></li>
  <li><a>关于</a></li>
  <li>
    <details>
      <summary>更多</summary>
      <ul>
        <li><a>子菜单1</a></li>
        <li><a>子菜单2</a></li>
      </ul>
    </details>
  </li>
</ul>
```

## 🎯 常用布局

### 响应式网格
```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  <div class="card bg-base-100 shadow-xl">...</div>
  <div class="card bg-base-100 shadow-xl">...</div>
  <div class="card bg-base-100 shadow-xl">...</div>
</div>
```

### Hero 区域
```html
<div class="hero min-h-screen bg-base-200">
  <div class="hero-content text-center">
    <div class="max-w-md">
      <h1 class="text-5xl font-bold">Hello there</h1>
      <p class="py-6">欢迎使用我们的系统</p>
      <button class="btn btn-primary">开始使用</button>
    </div>
  </div>
</div>
```

### 模态框
```html
<!-- 触发按钮 -->
<button class="btn" onclick="my_modal.showModal()">打开模态框</button>

<!-- 模态框 -->
<dialog id="my_modal" class="modal">
  <div class="modal-box">
    <h3 class="font-bold text-lg">标题</h3>
    <p class="py-4">内容</p>
    <div class="modal-action">
      <form method="dialog">
        <button class="btn">关闭</button>
      </form>
    </div>
  </div>
</dialog>
```

## 🌈 色彩系统

### 语义化颜色
- `primary`: 主要操作色
- `secondary`: 次要操作色
- `accent`: 强调色
- `neutral`: 中性色
- `base-100/200/300`: 背景色阶
- `info`: 信息色
- `success`: 成功色
- `warning`: 警告色
- `error`: 错误色

### 使用示例
```html
<div class="bg-primary text-primary-content">主要色块</div>
<div class="bg-base-200 text-base-content">背景色块</div>
<p class="text-success">成功文本</p>
<button class="btn btn-error">错误按钮</button>
```

## 📱 响应式设计

### 断点前缀
- `sm:`: 640px 及以上
- `md:`: 768px 及以上
- `lg:`: 1024px 及以上
- `xl:`: 1280px 及以上

### 示例
```html
<div class="flex flex-col md:flex-row gap-4">
  <div class="w-full md:w-1/2">左侧内容</div>
  <div class="w-full md:w-1/2">右侧内容</div>
</div>
```

## 🔧 最佳实践

### 1. 颜色使用
- 优先使用语义化颜色（primary, success 等）
- 避免使用固定颜色（red-500），确保主题切换正常

### 2. 组件组合
- 合理嵌套组件，如 card 内包含 form-control
- 使用 join 组件组合相关元素

### 3. 响应式设计
- 从移动端开始设计（mobile-first）
- 合理使用断点前缀

### 4. 性能优化
- 避免过度嵌套
- 合理使用工具类

## 🎨 自定义样式

### CSS 变量
daisyUI 提供了丰富的 CSS 变量，可以在需要时覆盖：

```css
:root {
  --rounded-btn: 0.5rem;
  --animation-btn: 0.25s;
  --btn-focus-scale: 0.95;
}
```

### 主题定制
如需创建自定义主题，请参考 daisyUI 文档或使用在线主题生成器。

## 📚 更多资源

- [daisyUI 官方文档](https://daisyui.com/)
- [Tailwind CSS 文档](https://tailwindcss.com/)
- [Iconify 图标库](https://iconify.design/)

## 🐛 常见问题

### Q: 主题切换后样式不生效？
A: 检查是否使用了固定颜色类，改用语义化颜色。

### Q: 图标不显示？
A: 确保图标名称正确，格式为 `icon-[collection--name]`。

### Q: 响应式布局问题？
A: 检查断点前缀使用是否正确，从小屏幕开始设计。
