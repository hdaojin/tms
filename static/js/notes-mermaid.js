(function () {
  const diagramSelector = "[data-mermaid-diagram]";
  const darkThemes = ["dark", "business", "night"];
  const isPrintPage = Boolean(document.querySelector("[data-note-print-page]"));
  let renderQueue = Promise.resolve();

  function activeMermaidTheme() {
    if (isPrintPage) return "default";
    const state = window.tmsTheme ? window.tmsTheme.currentState() : null;
    return state && darkThemes.includes(state.theme) ? "dark" : "default";
  }

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

  async function renderAll(theme) {
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
      theme,
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
      } catch (error) {
        showRenderError(diagram, source, error);
      }
    }
  }

  function queueRender(theme) {
    renderQueue = renderQueue
      .catch(function () {})
      .then(function () {
        return renderAll(theme);
      });
    window.tmsMermaidReady = renderQueue;
    return renderQueue;
  }

  window.tmsPreparePrint = function () {
    return queueRender("default");
  };

  window.addEventListener("tms:theme-changed", function () {
    if (!isPrintPage) queueRender(activeMermaidTheme());
  });
  window.addEventListener("beforeprint", function () {
    if (!isPrintPage) queueRender("default");
  });
  window.addEventListener("afterprint", function () {
    if (!isPrintPage) queueRender(activeMermaidTheme());
  });

  queueRender(activeMermaidTheme());
})();
