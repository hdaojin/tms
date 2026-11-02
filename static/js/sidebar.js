(function () {
  const storageKey = "tms-desktop-nav-collapsed";
  let collapsed = false;
  try {
    collapsed = window.localStorage.getItem(storageKey) === "true";
  } catch {
    // 存储不可用时，导航开关仍在当前页面生效。
  }

  function sync() {
    document.documentElement.dataset.desktopNavCollapsed = String(collapsed);
    document.querySelectorAll("[data-desktop-nav-toggle]").forEach(function (button) {
      const label = collapsed ? "展开导航" : "收起导航";
      button.setAttribute("aria-expanded", String(!collapsed));
      button.setAttribute("aria-label", label);
      button.title = label;
    });
  }

  sync();
  document.addEventListener("DOMContentLoaded", function () {
    // 其他布局共用页头，但没有桌面侧栏。
    const sidebar = document.getElementById("tms-desktop-sidebar");
    document.querySelectorAll("[data-desktop-nav-toggle]").forEach(function (button) {
      if (!sidebar) {
        button.remove();
        return;
      }
      button.addEventListener("click", function () {
        collapsed = !collapsed;
        sync();
        try {
          window.localStorage.setItem(storageKey, String(collapsed));
        } catch {
          // 不影响当前页面切换。
        }
      });
    });
    sync();
  });
})();
