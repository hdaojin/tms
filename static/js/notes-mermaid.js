(function () {
  const diagramSelector = "[data-mermaid-diagram]";
  const diagramFontFamily =
    'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif';
  let renderQueue = Promise.resolve();

  function diagramSource(diagram) {
    if (!diagram.dataset.mermaidSource) {
      diagram.dataset.mermaidSource = diagram.textContent.trim();
    }
    return diagram.dataset.mermaidSource;
  }

  function showRenderError(diagram, source, error) {
    diagram.removeAttribute("data-processed");
    diagram.classList.add("mermaid-render-error");
    diagram.replaceChildren();

    const message = document.createElement("p");
    message.className = "font-semibold text-error";
    message.textContent = "Mermaid 图表渲染失败，请检查图表语法。";

    const detail = document.createElement("p");
    detail.className = "mt-1 text-sm text-base-content/70";
    detail.textContent = error && error.message ? error.message : "未知错误";

    const sourceBlock = document.createElement("pre");
    sourceBlock.className =
      "mt-3 overflow-x-auto rounded-box bg-base-200 p-3 text-sm";
    const sourceCode = document.createElement("code");
    sourceCode.textContent = source;
    sourceBlock.appendChild(sourceCode);
    diagram.append(message, detail, sourceBlock);
  }

  function restoreIntrinsicSvgSize(diagram) {
    const svg = diagram.querySelector("svg");
    if (!svg) return;

    const viewBox = (svg.getAttribute("viewBox") || "")
      .trim()
      .split(/[\s,]+/)
      .map(Number);
    if (viewBox.length === 4 && viewBox.every(Number.isFinite)) {
      const width = Math.max(1, viewBox[2]);
      const height = Math.max(1, viewBox[3]);
      svg.setAttribute("width", String(width));
      svg.setAttribute("height", String(height));
    }
    svg.style.removeProperty("max-width");
    if (!svg.getAttribute("style")) svg.removeAttribute("style");
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  }

  async function renderAll() {
    const diagrams = Array.from(document.querySelectorAll(diagramSelector));
    if (!diagrams.length) return;
    if (!window.mermaid) {
      diagrams.forEach(function (diagram) {
        const source = diagramSource(diagram);
        showRenderError(diagram, source, new Error("Mermaid 运行库未加载"));
      });
      return;
    }

    window.mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "default",
      darkMode: false,
      htmlLabels: false,
      wrap: true,
      markdownAutoWrap: true,
      fontFamily: diagramFontFamily,
      themeVariables: {
        background: "#ffffff",
        darkMode: false,
        fontFamily: diagramFontFamily,
        fontSize: "16px",
        textColor: "#111827",
        primaryTextColor: "#111827",
        lineColor: "#374151",
      },
      flowchart: {
        useMaxWidth: false,
      },
      sequence: {
        useMaxWidth: false,
        width: 200,
        height: 65,
        actorMargin: 80,
        wrap: true,
        wrapPadding: 12,
        actorFontFamily: diagramFontFamily,
        actorFontSize: 16,
        noteFontFamily: diagramFontFamily,
        noteFontSize: 16,
        noteAlign: "center",
        messageFontFamily: diagramFontFamily,
        messageFontSize: 16,
        messageAlign: "center",
      },
      suppressErrorRendering: true,
    });

    for (const diagram of diagrams) {
      const source = diagramSource(diagram);
      diagram.classList.remove("mermaid-render-error");
      diagram.removeAttribute("data-processed");
      diagram.textContent = source;
      try {
        await window.mermaid.parse(source);
        await window.mermaid.run({ nodes: [diagram] });
        restoreIntrinsicSvgSize(diagram);
      } catch (error) {
        showRenderError(diagram, source, error);
      }
    }
  }

  function queueRender() {
    renderQueue = renderQueue
      .catch(function () {})
      .then(function () {
        return renderAll();
      });
    window.tmsMermaidReady = renderQueue;
    return renderQueue;
  }

  window.tmsPreparePrint = function () {
    return queueRender();
  };

  queueRender();
})();
