(function () {
  function getCsrfToken() {
    const meta = document.querySelector("meta[name='csrf-token']");
    return document.body.dataset.csrfToken || (meta && meta.getAttribute("content")) || "";
  }

  document.body.addEventListener("htmx:configRequest", function (event) {
    const token = getCsrfToken();
    if (token) event.detail.headers["X-CSRFToken"] = token;
  });

  document.body.addEventListener("htmx:beforeRequest", function (event) {
    const target = event.detail.target;
    if (target) target.classList.add("htmx-loading");
  });

  document.body.addEventListener("htmx:afterRequest", function (event) {
    const target = event.detail.target;
    if (target) target.classList.remove("htmx-loading");
  });

  document.body.addEventListener("htmx:responseError", function () {
    window.dispatchEvent(new CustomEvent("tms:toast", { detail: { type: "error", message: "请求失败，请稍后重试。" } }));
  });
})();
