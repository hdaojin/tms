(function () {
  let pendingSkillRowId = null;
  let pendingSkillTreeDialogTrigger = null;

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

  function syncSkillTreeEmptyState(container) {
    if (!container || !container.children) return;
    const children = Array.from(container.children);
    const emptyState = children.find(function (child) {
      return child.hasAttribute("data-skill-tree-empty");
    });
    if (!emptyState) return;
    const hasContent = children.some(function (child) {
      return (
        child.hasAttribute("data-skill-tree-node") ||
        child.hasAttribute("data-skill-tree-inline-editor")
      );
    });
    emptyState.classList.toggle("hidden", hasContent);
  }

  function removeSkillTreeInlineEditor(editor) {
    if (!editor) return;
    const container = editor.parentElement;
    editor.remove();
    syncSkillTreeEmptyState(container);
  }

  function removeSkillTreeInlineEditors() {
    document
      .querySelectorAll("[data-skill-tree-inline-editor]")
      .forEach(removeSkillTreeInlineEditor);
  }

  function focusSkillTreeNode(nodeId) {
    const node = document.getElementById(`skill-tree-node-${nodeId}`);
    if (!node) return;
    let ancestor = node.parentElement;
    while (ancestor) {
      if (ancestor.tagName === "DETAILS") ancestor.open = true;
      ancestor = ancestor.parentElement;
    }
    const highlight = node.querySelector("[data-skill-tree-node-row]") || node;
    highlight.classList.add(
      "bg-success/10",
      "outline",
      "outline-2",
      "outline-success/40",
    );
    node.setAttribute("tabindex", "-1");
    window.requestAnimationFrame(function () {
      node.scrollIntoView({ behavior: "smooth", block: "center" });
      node.focus({ preventScroll: true });
    });
    window.setTimeout(function () {
      highlight.classList.remove(
        "bg-success/10",
        "outline",
        "outline-2",
        "outline-success/40",
      );
    }, 1800);
  }

  function initSkillTreeInlineEditor(root) {
    const editors = [];
    if (root.matches && root.matches("[data-skill-tree-inline-editor]"))
      editors.push(root);
    if (root.closest) {
      const parentEditor = root.closest("[data-skill-tree-inline-editor]");
      if (parentEditor) editors.push(parentEditor);
    }
    if (root.querySelectorAll) {
      root
        .querySelectorAll("[data-skill-tree-inline-editor]")
        .forEach(function (editor) {
          editors.push(editor);
        });
    }

    const uniqueEditors = Array.from(new Set(editors));
    const activeEditor = uniqueEditors[uniqueEditors.length - 1];
    if (!activeEditor) return;
    document
      .querySelectorAll("[data-skill-tree-inline-editor]")
      .forEach(function (editor) {
        if (editor !== activeEditor) removeSkillTreeInlineEditor(editor);
      });
    [activeEditor].forEach(function (editor) {
      syncSkillTreeEmptyState(editor.parentElement);
      if (editor.dataset.skillTreeInlineBound !== "true") {
        editor.dataset.skillTreeInlineBound = "true";
        editor.addEventListener("keydown", function (event) {
          if (event.key !== "Escape") return;
          event.preventDefault();
          removeSkillTreeInlineEditor(editor);
        });
        editor.addEventListener("click", function (event) {
          if (event.target.closest("[data-skill-tree-inline-cancel]")) {
            event.preventDefault();
            removeSkillTreeInlineEditor(editor);
            return;
          }
          const locate = event.target.closest("[data-skill-tree-locate-node]");
          if (!locate) return;
          const nodeId = locate.dataset.skillTreeLocateNode;
          removeSkillTreeInlineEditor(editor);
          focusSkillTreeNode(nodeId);
        });
      }
      window.requestAnimationFrame(function () {
        const input = editor.querySelector("[data-skill-tree-name-input]");
        if (input) input.focus();
      });
    });
  }

  function initSkillTreeDialog(root) {
    const dialogs = [];
    if (root.matches && root.matches("[data-skill-tree-dialog]"))
      dialogs.push(root);
    if (root.closest) {
      const parentDialog = root.closest("[data-skill-tree-dialog]");
      if (parentDialog) dialogs.push(parentDialog);
    }
    if (root.querySelectorAll) {
      root
        .querySelectorAll("[data-skill-tree-dialog]")
        .forEach(function (dialog) {
          dialogs.push(dialog);
        });
    }

    if (dialogs.length) removeSkillTreeInlineEditors();
    Array.from(new Set(dialogs)).forEach(function (dialog) {
      if (dialog.dataset.skillTreeDialogBound !== "true") {
        dialog.dataset.skillTreeDialogBound = "true";
        dialog.addEventListener("click", function (event) {
          if (event.target === dialog) dialog.close();
          if (event.target.closest("[data-skill-tree-dialog-close]"))
            dialog.close();
        });
        dialog.addEventListener("close", function () {
          const host = dialog.closest("#skill-tree-dialog");
          if (host) host.replaceChildren();
          if (!document.querySelector(".tms-side-dialog[open]"))
            document.body.classList.remove("overflow-hidden");
          const trigger = pendingSkillTreeDialogTrigger;
          pendingSkillTreeDialogTrigger = null;
          if (trigger && trigger.isConnected) trigger.focus();
        });
      }
      if (!dialog.open && typeof dialog.showModal === "function")
        dialog.showModal();
      document.body.classList.add("overflow-hidden");
      window.requestAnimationFrame(function () {
        const focusTarget = dialog.querySelector(
          "[autofocus], #id_name, select, input:not([type='hidden']), button",
        );
        if (focusTarget) focusTarget.focus();
      });
    });

    if (
      dialogs.length === 0 &&
      !document.querySelector("[data-skill-tree-dialog][open]") &&
      !document.querySelector("[data-skill-create-dialog][open]")
    ) {
      document.body.classList.remove("overflow-hidden");
      if (
        pendingSkillTreeDialogTrigger &&
        !pendingSkillTreeDialogTrigger.isConnected
      )
        pendingSkillTreeDialogTrigger = null;
    }
  }

  function initSkillTreeRemoveForm(root) {
    const forms = [];
    if (root.matches && root.matches("[data-skill-tree-remove-form]"))
      forms.push(root);
    if (root.closest) {
      const parentForm = root.closest("[data-skill-tree-remove-form]");
      if (parentForm) forms.push(parentForm);
    }
    if (root.querySelectorAll) {
      root
        .querySelectorAll("[data-skill-tree-remove-form]")
        .forEach(function (form) {
          forms.push(form);
        });
    }
    Array.from(new Set(forms)).forEach(function (form) {
      const confirmation = form.querySelector("[data-skill-tree-subtree-confirm]");
      if (!confirmation) return;
      function sync() {
        const selected = form.querySelector("input[name='mode']:checked");
        confirmation.classList.toggle(
          "hidden",
          !selected || selected.value !== "subtree",
        );
      }
      if (form.dataset.skillTreeRemoveBound !== "true") {
        form.dataset.skillTreeRemoveBound = "true";
        form.addEventListener("change", function (event) {
          if (event.target.name === "mode") sync();
        });
      }
      sync();
    });
  }

  function initSkillTreeWorkbench(root) {
    initSkillTreeInlineEditor(root);
    initSkillTreeDialog(root);
    initSkillTreeRemoveForm(root);
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
    initSkillTreeWorkbench(root);
    initScrollAfterSwap(root);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAll(document);
  });
  document.addEventListener("click", function (event) {
    const searchResult = event.target.closest("[data-skill-tree-search-locate]");
    if (searchResult) {
      focusSkillTreeNode(searchResult.dataset.skillTreeSearchLocate);
      return;
    }
    const selectedMenu = event.target.closest("[data-skill-tree-node-menu]");
    document
      .querySelectorAll("[data-skill-tree-node-menu][open]")
      .forEach(function (menu) {
        if (menu !== selectedMenu) menu.open = false;
      });
  });
  document.addEventListener("change", function (event) {
    const field = event.target.closest("[data-cycle-version-field]");
    if (field) field.dataset.cycleVersionTouched = "true";
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") return;
    document
      .querySelectorAll("[data-skill-tree-node-menu][open]")
      .forEach(function (menu) {
        menu.open = false;
      });
  });
  document.body.addEventListener("htmx:beforeRequest", function (event) {
    const element = event.detail && event.detail.elt;
    if (!element || !element.closest) return;
    if (element.closest("[data-skill-tree-editor-trigger]")) {
      removeSkillTreeInlineEditors();
      const branchWrapper = element.closest("[data-skill-tree-branch-wrapper]");
      const branch = branchWrapper
        ? branchWrapper.querySelector("[data-skill-tree-branch]")
        : element.closest("[data-skill-tree-branch]");
      if (branch) branch.open = true;
    }
    const menu = element.closest("[data-skill-tree-node-menu]");
    if (element.closest("[data-skill-tree-dialog-trigger]"))
      pendingSkillTreeDialogTrigger = menu
        ? menu.querySelector("summary")
        : element;
    if (menu) menu.open = false;
  });
  document.body.addEventListener("htmx:configRequest", function (event) {
    const element = event.detail && event.detail.elt;
    if (!element || !element.matches("[data-cycle-version-context-trigger]"))
      return;
    const preserved = [];
    document
      .querySelectorAll(
        "[data-cycle-version-field][data-cycle-version-touched='true']",
      )
      .forEach(function (field) {
        if (!field.name) return;
        preserved.push(field.name);
        event.detail.parameters[field.name] = field.value;
      });
    event.detail.parameters.preserved = preserved;
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
  document.body.addEventListener("skillTreeNodeCreated", function (event) {
    if (!event.detail || !event.detail.nodeId) return;
    focusSkillTreeNode(event.detail.nodeId);
  });
  document.body.addEventListener("skillTreeNodeFocused", function (event) {
    if (!event.detail || !event.detail.nodeId) return;
    focusSkillTreeNode(event.detail.nodeId);
  });
})();
