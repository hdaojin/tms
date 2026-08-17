(function () {
  function initThemeControls(root) {
    function syncThemeControls() {
      if (!window.tmsTheme) return;
      const state = window.tmsTheme.currentState();
      document.querySelectorAll("[data-theme-label]").forEach(function (label) {
        label.textContent = state.label;
      });
      document.querySelectorAll("[data-theme-option]").forEach(function (option) {
        const selected = option.dataset.themeValue === state.preference;
        option.classList.toggle("menu-active", selected);
        option.setAttribute("aria-checked", selected ? "true" : "false");
        const check = option.querySelector("[data-theme-check]");
        if (check) check.classList.toggle("hidden", !selected);
      });
    }

    root.querySelectorAll("[data-theme-value]").forEach(function (button) {
      if (button.dataset.themeBound === "true") return;
      button.dataset.themeBound = "true";
      button.addEventListener("click", function () {
        if (window.tmsTheme) window.tmsTheme.setTheme(button.dataset.themeValue);
      });
    });
    syncThemeControls();
    if (!window.tmsThemeControlsBound) {
      window.tmsThemeControlsBound = true;
      window.addEventListener("tms:theme-changed", syncThemeControls);
    }
  }

  function initModals(root) {
    root.querySelectorAll("[data-modal-target]").forEach(function (button) {
      button.addEventListener("click", function () {
        const dialog = document.getElementById(button.dataset.modalTarget);
        if (dialog && typeof dialog.showModal === "function") dialog.showModal();
      });
    });
    root.querySelectorAll("[data-modal-close]").forEach(function (button) {
      button.addEventListener("click", function () {
        const dialog = document.getElementById(button.dataset.modalClose);
        if (dialog && typeof dialog.close === "function") dialog.close();
      });
    });
  }

  function initDismissibleAlerts(root) {
    root.querySelectorAll("[data-dismiss-alert]").forEach(function (button) {
      button.addEventListener("click", function () {
        const alert = button.closest(".alert");
        if (alert) alert.remove();
      });
    });
  }

  function initHistoryBack(root) {
    root.querySelectorAll("[data-history-back]").forEach(function (button) {
      button.addEventListener("click", function () {
        if (window.history.length > 1) window.history.back();
      });
    });
  }

  function initPrint(root) {
    root.querySelectorAll("[data-print]").forEach(function (button) {
      if (button.dataset.printBound === "true") return;
      button.dataset.printBound = "true";
      button.addEventListener("click", async function () {
        if (button.dataset.printing === "true") return;
        button.dataset.printing = "true";
        button.disabled = true;
        try {
          if (typeof window.tmsPreparePrint === "function") {
            await window.tmsPreparePrint();
          }
          window.print();
        } finally {
          button.disabled = false;
          delete button.dataset.printing;
        }
      });
    });
  }

  function initClipboard(root) {
    root.querySelectorAll("[data-copy-target]").forEach(function (button) {
      button.addEventListener("click", function () {
        const input = document.querySelector(button.dataset.copyTarget);
        if (!input) return;
        const originalText = button.innerHTML;
        const copiedText = button.dataset.copiedLabel || "已复制";
        navigator.clipboard.writeText(input.value).then(
          function () {
            button.innerHTML = '<span class="icon-[tabler--check] size-4"></span>' + copiedText;
            button.classList.add("btn-success");
            button.classList.remove("btn-primary");
            window.setTimeout(function () {
              button.innerHTML = originalText;
              button.classList.remove("btn-success");
              button.classList.add("btn-primary");
            }, 2000);
          },
          function () {
            input.select();
          },
        );
      });
    });
  }

  function initConditionalGroups(root) {
    root.querySelectorAll("[data-toggle-target]").forEach(function (checkbox) {
      const target = document.querySelector(checkbox.dataset.toggleTarget);
      if (!target) return;
      function sync() {
        const showWhenUnchecked = checkbox.dataset.showWhen === "unchecked";
        target.classList.toggle("hidden", showWhenUnchecked ? checkbox.checked : !checkbox.checked);
      }
      checkbox.addEventListener("change", sync);
      sync();
    });
  }

  function initCountdown(root) {
    root.querySelectorAll("[data-countdown-screen]").forEach(function (screen) {
      const targetValue = screen.dataset.targetAt;
      if (!targetValue) return;
      const targetTime = new Date(targetValue).getTime();
      const days = screen.querySelector("[data-countdown-days]");
      const hours = screen.querySelector("[data-countdown-hours]");
      const minutes = screen.querySelector("[data-countdown-minutes]");
      const seconds = screen.querySelector("[data-countdown-seconds]");
      const progress = screen.querySelector("[data-countdown-progress]");

      function pad(value) {
        return String(value).padStart(2, "0");
      }

      function tick() {
        const diff = Math.max(0, targetTime - Date.now());
        const totalSeconds = Math.floor(diff / 1000);
        const nextDays = Math.floor(totalSeconds / 86400);
        const nextHours = Math.floor((totalSeconds % 86400) / 3600);
        const nextMinutes = Math.floor((totalSeconds % 3600) / 60);
        const nextSeconds = totalSeconds % 60;

        if (days) days.textContent = nextDays;
        if (hours) hours.textContent = pad(nextHours);
        if (minutes) minutes.textContent = pad(nextMinutes);
        if (seconds) seconds.textContent = pad(nextSeconds);
        if (progress) progress.value = Math.min(100, Math.max(0, 100 - (diff / (30 * 86400 * 1000)) * 100));
      }

      tick();
      window.setInterval(tick, 1000);
    });
  }

  function initAll(root) {
    initThemeControls(root);
    initModals(root);
    initDismissibleAlerts(root);
    initHistoryBack(root);
    initPrint(root);
    initClipboard(root);
    initConditionalGroups(root);
    initCountdown(root);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAll(document);
  });
  document.body.addEventListener("htmx:afterSwap", function (event) {
    initAll(event.target);
  });
})();
