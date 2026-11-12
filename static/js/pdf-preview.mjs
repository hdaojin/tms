// Keep a single page canvas: long PDFs must not exhaust mobile browser memory.
export async function initializePdfPreview(root, pdfjs, { data, signal } = {}) {
  if (signal?.aborted) return;
  const canvas = root.querySelector("[data-pdf-canvas]");
  const viewportElement = root.querySelector("[data-pdf-viewport]");
  const previous = root.querySelector("[data-pdf-previous]");
  const next = root.querySelector("[data-pdf-next]");
  const pageLabel = root.querySelector("[data-pdf-page]");
  const status = root.querySelector("[data-pdf-status]");
  let pdf;
  let loadingTask;
  let renderTask;
  let pageNumber = 1;
  let rendering = false;

  function updateButtons() {
    previous.disabled = rendering || !pdf || pageNumber <= 1;
    next.disabled = rendering || !pdf || pageNumber >= pdf.numPages;
  }

  function showError(error) {
    if (signal?.aborted) return;
    status.textContent =
      error?.name === "PasswordException"
        ? "此 PDF 需要密码，请下载后使用本地应用打开。"
        : "PDF 预览加载失败，请下载文件查看，或刷新页面重试。";
  }

  async function renderPage() {
    if (rendering || !pdf || signal?.aborted) return;
    rendering = true;
    updateButtons();
    status.textContent = "正在渲染 PDF…";
    let page;
    try {
      page = await pdf.getPage(pageNumber);
      if (signal?.aborted) return;
      const natural = page.getViewport({ scale: 1 });
      // Leave room for padding and cap high-DPI canvas allocation to 4M pixels.
      const width = Math.max(1, viewportElement.clientWidth - 24);
      const scale = Math.min(width / natural.width, 2);
      const viewport = page.getViewport({ scale });
      const ratio = Math.min(
        globalThis.devicePixelRatio || 1,
        2,
        Math.sqrt(4_000_000 / (viewport.width * viewport.height)),
      );
      canvas.width = Math.max(1, Math.floor(viewport.width * ratio));
      canvas.height = Math.max(1, Math.floor(viewport.height * ratio));
      renderTask = page.render({
        canvasContext: canvas.getContext("2d"),
        viewport,
        transform: [ratio, 0, 0, ratio, 0, 0],
      });
      await renderTask.promise;
      if (signal?.aborted) return;
      canvas.hidden = false;
      canvas.setAttribute(
        "aria-label",
        `PDF 第 ${pageNumber} 页，共 ${pdf.numPages} 页`,
      );
      pageLabel.textContent = `第 ${pageNumber} / ${pdf.numPages} 页`;
      status.textContent = "可使用上一页、下一页浏览，也可下载原文件。";
      viewportElement.scrollTop = 0;
    } catch (error) {
      if (!signal?.aborted) {
        canvas.hidden = true;
        showError(error);
      }
    } finally {
      page?.cleanup();
      renderTask = undefined;
      rendering = false;
      if (!signal?.aborted) updateButtons();
    }
  }

  try {
    let source = { data };
    if (!data) {
      const url = new URL(root.dataset.pdfUrl, globalThis.location.href);
      if (url.origin !== globalThis.location.origin)
        throw new Error("Expected same-origin PDF");
      source = { url: url.href };
    }
    pdfjs.GlobalWorkerOptions.workerSrc = root.dataset.pdfWorker;
    const assets = root.dataset.pdfAssets;
    loadingTask = pdfjs.getDocument({
      ...source,
      cMapUrl: `${assets}cmaps/`,
      cMapPacked: true,
      standardFontDataUrl: `${assets}standard_fonts/`,
      wasmUrl: `${assets}wasm/`,
      // Render font paths without blob fonts; keep the existing strict CSP.
      disableFontFace: true,
      isEvalSupported: false,
      useWasm: false,
    });
    signal?.addEventListener("abort", () => {
      renderTask?.cancel();
      void loadingTask.destroy().catch(() => {});
      previous.disabled = true;
      next.disabled = true;
      canvas.hidden = true;
      canvas.width = 0;
      canvas.height = 0;
      pageLabel.textContent = "尚未加载";
    }, { once: true });
    pdf = await loadingTask.promise;
    if (signal?.aborted) return;
    previous.addEventListener("click", () => {
      if (rendering || pageNumber <= 1) return;
      pageNumber -= 1;
      void renderPage();
    }, { signal });
    next.addEventListener("click", () => {
      if (rendering || pageNumber >= pdf.numPages) return;
      pageNumber += 1;
      void renderPage();
    }, { signal });
    // Native CSS resizing keeps the canvas usable through device rotation.
    await renderPage();
  } catch (error) {
    showError(error);
  }
}

if (typeof document !== "undefined") {
  for (const root of document.querySelectorAll("[data-pdf-preview]")) {
    import(root.dataset.pdfLibrary)
      .then((pdfjs) => initializePdfPreview(root, pdfjs))
      .catch(() => {
        root.querySelector("[data-pdf-status]").textContent =
          "PDF 预览组件加载失败，请下载文件查看。";
      });
  }
}
