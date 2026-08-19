(function () {
  let pendingSkillRowId = null;

  document.body.addEventListener("skillAliasAdded", function (event) {
    if (event.detail && event.detail.skillId)
      pendingSkillRowId = `skill-row-${event.detail.skillId}`;
  });
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

  function initSkillCreateDrawer(root) {
    const dialogs = [];
    if (root.matches && root.matches("[data-skill-create-dialog]"))
      dialogs.push(root);
    if (root.closest) {
      const parentDialog = root.closest("[data-skill-create-dialog]");
      if (parentDialog) dialogs.push(parentDialog);
    }
    if (root.querySelectorAll) {
      root
        .querySelectorAll("[data-skill-create-dialog]")
        .forEach(function (dialog) {
          dialogs.push(dialog);
        });
    }

    function focusSkillName(dialog) {
      window.requestAnimationFrame(function () {
        const nameInput = dialog.querySelector("#id_name");
        if (nameInput) nameInput.focus();
      });
    }

    function openSkillDialog(dialog) {
      if (!dialog.open) dialog.showModal();
      document.body.classList.add("overflow-hidden");
      focusSkillName(dialog);
    }

    function hideDiscardPrompt(dialog) {
      const prompt = dialog.querySelector("[data-skill-discard-prompt]");
      if (!prompt) return;
      prompt.classList.add("hidden");
      prompt.classList.remove("flex");
      Array.from(prompt.parentElement.children).forEach(function (element) {
        if (element !== prompt) element.inert = false;
      });
    }

    function showDiscardPrompt(dialog) {
      const prompt = dialog.querySelector("[data-skill-discard-prompt]");
      if (!prompt) return;
      Array.from(prompt.parentElement.children).forEach(function (element) {
        if (element !== prompt) element.inert = true;
      });
      prompt.classList.remove("hidden");
      prompt.classList.add("flex");
      const cancelButton = prompt.querySelector("[data-skill-discard-cancel]");
      if (cancelButton) cancelButton.focus();
    }

    function resetSkillForm(dialog, focusAfterReset) {
      const resetButton = dialog.querySelector("[data-skill-form-reset]");
      if (!resetButton) return;
      resetButton.click();
      dialog.dataset.focusAfterReset = focusAfterReset ? "true" : "false";
    }

    function scrollToPendingSkill() {
      if (!pendingSkillRowId) return;
      const element = document.getElementById(pendingSkillRowId);
      if (!element) return;
      pendingSkillRowId = null;
      element.classList.add(
        "bg-success/10",
        "outline",
        "outline-2",
        "outline-success/40",
        "scroll-mt-24",
      );
      window.requestAnimationFrame(function () {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }

    function closeSkillDialog(dialog) {
      hideDiscardPrompt(dialog);
      resetSkillForm(dialog, false);
      dialog.dataset.dirty = "false";
      dialog.close();
    }

    function requestSkillDialogClose(dialog) {
      if (dialog.dataset.dirty === "true") {
        showDiscardPrompt(dialog);
        return;
      }
      closeSkillDialog(dialog);
    }

    dialogs.forEach(function (dialog) {
      let replacedPanel = null;
      if (root.matches && root.matches("#skill-create-panel"))
        replacedPanel = root;
      if (!replacedPanel && root.querySelector)
        replacedPanel = root.querySelector("#skill-create-panel");
      if (replacedPanel && dialog.contains(replacedPanel)) {
        dialog.dataset.dirty = replacedPanel.dataset.skillFormDirty || "false";
      }

      if (dialog.dataset.skillDrawerBound === "true") {
        if (dialog.dataset.focusAfterReset === "true") {
          delete dialog.dataset.focusAfterReset;
          focusSkillName(dialog);
        }
        return;
      }
      dialog.dataset.skillDrawerBound = "true";

      dialog.addEventListener("input", function (event) {
        if (event.target.closest("#skill-create-form"))
          dialog.dataset.dirty = "true";
      });
      dialog.addEventListener("change", function (event) {
        if (event.target.closest("#skill-create-form"))
          dialog.dataset.dirty = "true";
      });
      dialog.addEventListener("cancel", function (event) {
        event.preventDefault();
        const prompt = dialog.querySelector("[data-skill-discard-prompt]");
        if (prompt && !prompt.classList.contains("hidden")) {
          hideDiscardPrompt(dialog);
          focusSkillName(dialog);
          return;
        }
        requestSkillDialogClose(dialog);
      });
      dialog.addEventListener("click", function (event) {
        if (event.target === dialog) requestSkillDialogClose(dialog);
      });
      dialog.addEventListener("close", function () {
        document.body.classList.remove("overflow-hidden");
        scrollToPendingSkill();
      });
      dialog.addEventListener("click", function (event) {
        if (event.target.closest("[data-skill-drawer-close]"))
          requestSkillDialogClose(dialog);
        if (event.target.closest("[data-skill-discard-cancel]")) {
          hideDiscardPrompt(dialog);
          focusSkillName(dialog);
        }
        if (event.target.closest("[data-skill-discard-confirm]"))
          closeSkillDialog(dialog);
        if (event.target.closest("[data-skill-form-reset]"))
          dialog.dataset.focusAfterReset = "true";
      });

      if (dialog.dataset.skillAutoOpen === "true") {
        openSkillDialog(dialog);
        const url = new URL(window.location.href);
        url.searchParams.delete("focus");
        window.history.replaceState(window.history.state, "", url);
      }
    });

    if (root.querySelectorAll) {
      root
        .querySelectorAll(".js-skill-drawer-open")
        .forEach(function (trigger) {
          if (trigger.dataset.skillDrawerBound === "true") return;
          trigger.dataset.skillDrawerBound = "true";
          trigger.addEventListener("click", function (event) {
            const dialog = document.querySelector("[data-skill-create-dialog]");
            if (!dialog) return;
            event.preventDefault();
            openSkillDialog(dialog);
          });
        });
    }
  }

  function initScrollAfterSwap(root) {
    let element =
      root.matches && root.matches("[data-scroll-after-swap]")
        ? root
        : root.querySelector && root.querySelector("[data-scroll-after-swap]");
    if (!element && pendingSkillRowId) {
      element = document.getElementById(pendingSkillRowId);
      if (element) {
        element.classList.add(
          "bg-success/10",
          "outline",
          "outline-2",
          "outline-success/40",
          "scroll-mt-24",
        );
        pendingSkillRowId = null;
      }
    }
    if (!element) return;
    const openSkillDialog = document.querySelector(
      "[data-skill-create-dialog][open]",
    );
    if (openSkillDialog) {
      if (element.id) pendingSkillRowId = element.id;
      return;
    }
    window.requestAnimationFrame(function () {
      element.scrollIntoView({ behavior: "smooth", block: "center" });
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
    initSkillCreateDrawer(root);
    initScrollAfterSwap(root);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAll(document);
  });
  document.body.addEventListener("htmx:afterSwap", function (event) {
    initAll(event.target);
  });
  document.body.addEventListener("skillCreated", function (event) {
    const dialog = document.querySelector("[data-skill-create-dialog]");
    if (!dialog) return;
    dialog.dataset.dirty = "false";
    if (event.detail && event.detail.skillId)
      pendingSkillRowId = `skill-row-${event.detail.skillId}`;
    window.requestAnimationFrame(function () {
      const nameInput = dialog.querySelector("#id_name");
      if (nameInput) nameInput.focus();
    });
  });
})();
