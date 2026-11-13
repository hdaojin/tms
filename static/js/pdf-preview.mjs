export async function initializePdfPreview(root, pdfjs, { data, signal } = {}) {
  if (signal?.aborted) return;
  const viewportElement = root.querySelector("[data-pdf-viewport]");
  const pagesElement = root.querySelector("[data-pdf-pages]");
  const pageTemplate = root.querySelector("[data-pdf-page-template]");
  const status = root.querySelector("[data-pdf-status]");
  const nearbyPages = new Set();
  const renderedPages = new Set();
  let loadingTask;
  let renderTask;
  let observer;
  let rendering = false;

  status.textContent = "正在加载 PDF；若无法显示，可下载文件查看。";

  function showError(error) {
    if (signal?.aborted) return;
    status.textContent =
      error?.name === "PasswordException"
        ? "此 PDF 需要密码，请下载后使用本地应用打开。"
        : "部分或全部 PDF 内容加载失败，请下载文件查看，或刷新页面重试。";
  }

  function releaseCanvas(element) {
    const canvas = element.firstElementChild;
    canvas.hidden = true;
    canvas.width = 0;
    canvas.height = 0;
  }

  async function renderPage(pdf, element) {
    const canvas = element.firstElementChild;
    let page;
    try {
      page = await pdf.getPage(Number(element.dataset.pageNumber));
      if (!nearbyPages.has(element)) return;
      const natural = page.getViewport({ scale: 1 });
      element.style.aspectRatio = `${natural.width} / ${natural.height}`;
      element.style.maxWidth = `${natural.width * 2}px`;
      const scale = Math.min(Math.max(1, element.clientWidth) / natural.width, 2);
      const viewport = page.getViewport({ scale });
      // Bound high-DPI canvas allocations, including unusually large PDF pages.
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
      if (nearbyPages.has(element)) {
        renderedPages.add(element);
        canvas.hidden = false;
      } else {
        releaseCanvas(element);
      }
    } catch (error) {
      releaseCanvas(element);
      if (!signal?.aborted) {
        // Keep the failed page's place and continue rendering the other pages.
        observer.unobserve(element);
        nearbyPages.delete(element);
        showError(error);
      }
    } finally {
      renderTask = undefined;
      page?.cleanup();
    }
  }

  async function renderNearbyPages(pdf) {
    if (rendering) return;
    rendering = true;
    try {
      for (const element of nearbyPages) {
        if (!renderedPages.has(element)) await renderPage(pdf, element);
      }
    } finally {
      rendering = false;
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
      observer?.disconnect();
      nearbyPages.clear();
      renderTask?.cancel();
      for (const element of renderedPages) releaseCanvas(element);
      renderedPages.clear();
      pagesElement.replaceChildren();
      void loadingTask.destroy().catch(() => {});
    }, { once: true });

    const pdf = await loadingTask.promise;
    if (signal?.aborted) return;

    observer = new IntersectionObserver((entries) => {
      if (signal?.aborted) return;
      for (const { target, isIntersecting } of entries) {
        if (isIntersecting) {
          nearbyPages.add(target);
        } else {
          nearbyPages.delete(target);
          if (renderedPages.delete(target)) releaseCanvas(target);
        }
      }
      void renderNearbyPages(pdf);
    }, { root: viewportElement, rootMargin: "250px 0px" });

    const pages = [];
    for (let number = 1; number <= pdf.numPages; number += 1) {
      const element = pageTemplate.content.firstElementChild.cloneNode(true);
      element.dataset.pageNumber = number;
      element.setAttribute("aria-label", `PDF 第 ${number} 页，共 ${pdf.numPages} 页`);
      element.style.aspectRatio = "210 / 297";
      pages.push(element);
    }
    pagesElement.replaceChildren(...pages);
    viewportElement.scrollTop = 0;
    for (const page of pages) observer.observe(page);
    status.textContent = `共 ${pdf.numPages} 页，可上下滚动浏览。`;
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
