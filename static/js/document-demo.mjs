import { initializePdfPreview } from "./pdf-preview.mjs";

const form = document.querySelector("[data-document-form]");
const status = form.querySelector("[data-document-status]");
const iframe = document.querySelector("[data-document-html]");
const pdfSection = document.querySelector("[data-document-pdf]");
const viewer = pdfSection.querySelector("[data-pdf-preview-manual]");
let htmlRequest;
let pdfRequest;
let currentPdf;
let downloadUrl;
let downloadTimer;

for (const element of document.querySelectorAll("[data-document-js]")) {
  element.hidden = false;
}

function releaseDownloadUrl() {
  clearTimeout(downloadTimer);
  if (downloadUrl) URL.revokeObjectURL(downloadUrl);
  downloadUrl = undefined;
}

function resetPdf() {
  pdfRequest?.abort();
  currentPdf = undefined;
  pdfSection.hidden = true;
}

function invalidatePreviews() {
  htmlRequest?.abort();
  resetPdf();
  iframe.removeAttribute("srcdoc");
  status.textContent = "文档已修改，请重新预览。";
}

function downloadPdf({ blob, filename }) {
  releaseDownloadUrl();
  downloadUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = filename;
  link.click();
  downloadTimer = setTimeout(releaseDownloadUrl, 30_000);
}

function pdfFilename(response) {
  const disposition = response.headers.get("Content-Disposition") || "";
  const encoded = disposition.match(/filename\*=utf-8''([^;]+)/i);
  if (encoded) return decodeURIComponent(encoded[1]);
  return disposition.match(/filename="([^"]+)"/i)?.[1] || "文档.pdf";
}

async function requestDocument(action, signal) {
  const body = new FormData(form);
  body.set("action", action);
  const response = await fetch(form.getAttribute("action"), {
    method: "POST",
    headers: { Accept: "application/json" },
    body,
    signal,
  });
  if (!response.ok) {
    if (response.headers.get("Content-Type")?.includes("application/json")) {
      const { error, fields } = await response.json();
      const messages = Object.entries(fields).flatMap(([name, entries]) => {
        const field = form.elements.namedItem(name);
        const label = field?.labels?.[0]?.textContent.trim();
        return entries.map(({ message }) => label ? label + "：" + message : message);
      });
      throw new Error([error, ...messages].join(" "));
    }
    throw new Error("请求失败，请检查登录状态后重试。");
  }
  const expected = action === "html" ? "text/html" : "application/pdf";
  if (response.redirected || !response.headers.get("Content-Type")?.startsWith(expected)) {
    throw new Error("预览响应无效，请检查登录状态后重试。");
  }
  return response;
}

async function updateHtml() {
  htmlRequest?.abort();
  htmlRequest = new AbortController();
  const { signal } = htmlRequest;
  status.textContent = "正在更新 HTML 预览…";
  try {
    const response = await requestDocument("html", signal);
    const html = await response.text();
    if (signal.aborted) return;
    iframe.srcdoc = html;
    status.textContent = "HTML 预览已更新。";
  } catch (error) {
    if (!signal.aborted) status.textContent = error.message;
  }
}

async function updatePdf(action) {
  if (currentPdf && action === "download") {
    downloadPdf(currentPdf);
    return;
  }
  if (pdfRequest && !pdfRequest.signal.aborted && !currentPdf) return;
  resetPdf();
  const request = new AbortController();
  pdfRequest = request;
  const { signal } = request;
  status.textContent = "正在生成 PDF…";
  try {
    const response = await requestDocument(action, signal);
    const result = { blob: await response.blob(), filename: pdfFilename(response) };
    if (signal.aborted) return;
    if (action === "download") {
      downloadPdf(result);
    } else {
      currentPdf = result;
      pdfSection.hidden = false;
      try {
        const pdfjs = await import(viewer.dataset.pdfLibrary);
        const data = new Uint8Array(await result.blob.arrayBuffer());
        await initializePdfPreview(viewer, pdfjs, { data, signal });
      } catch {
        if (!signal.aborted) viewer.querySelector("[data-pdf-status]").textContent =
          "PDF 预览组件加载失败，请下载文件查看。";
      }
    }
    if (!signal.aborted) status.textContent = "PDF 已生成。";
  } catch (error) {
    if (!signal.aborted) status.textContent = error.message;
  } finally {
    // Retain the preview controller so edits can destroy the viewer.
    if (pdfRequest === request && !currentPdf) pdfRequest = undefined;
  }
}

form.addEventListener("input", invalidatePreviews);
form.elements.namedItem("template_id").addEventListener("change", () => void updateHtml());
form.addEventListener("submit", (event) => {
  const action = event.submitter?.value || "download";
  event.preventDefault();
  if (action === "html") void updateHtml();
  else void updatePdf(action);
});

addEventListener("pagehide", () => {
  htmlRequest?.abort();
  resetPdf();
  releaseDownloadUrl();
});

void updateHtml();
