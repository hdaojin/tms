import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../static/js/list-bulk-actions.js", import.meta.url),
  "utf8",
);

// A small event fixture exercises the delegated controller without browser globals.
function setup(
  total = 25,
  pageSize = 20,
  { allowSelectAll = true, selectionLabel = "条记录" } = {},
) {
  const handlers = {};
  const windowHandlers = {};
  const mode = { value: "selected" };
  const page = { checked: false };
  const operation = { value: "" };
  const status = {};
  const all = { hidden: true };
  const clear = { hidden: true };
  const error = { hidden: true };
  const boxes = Array.from({ length: pageSize }, () => ({
    checked: false,
    disabled: false,
  }));
  const nodes = {
    "[data-selection-mode]": mode,
    "[data-select-page]": page,
    "[data-bulk-operation]": operation,
    "[data-selection-status]": status,
    "[data-select-all]": allowSelectAll ? all : null,
    "[data-clear-selection]": clear,
    "[data-selection-error]": error,
  };
  const form = {
    dataset: { matchingCount: String(total), selectionLabel },
    querySelector: (selector) => nodes[selector],
    querySelectorAll: () => boxes,
  };
  vm.runInNewContext(source, {
    document: {
      addEventListener: (event, handler) => {
        handlers[event] = handler;
      },
      querySelectorAll: () => [form],
    },
    window: {
      addEventListener: (event, handler) => {
        windowHandlers[event] = handler;
      },
    },
  });
  function dispatch(event, selector, properties = {}) {
    const target = {
      ...properties,
      closest: (candidate) =>
        candidate === "[data-bulk-list]"
          ? form
          : candidate === selector
            ? {}
            : null,
      matches: (candidates) => candidates.split(", ").includes(selector),
    };
    let prevented = false;
    handlers[event]({
      target,
      preventDefault() {
        prevented = true;
      },
    });
    return prevented;
  }
  return {
    handlers,
    windowHandlers,
    form,
    boxes,
    mode,
    page,
    operation,
    status,
    all,
    clear,
    error,
    dispatch,
  };
}

test("the all-matching link appears only after selecting the entire current page", () => {
  const ui = setup();
  ui.boxes[0].checked = true;
  ui.dispatch("change", "[data-row-selection]");
  assert.equal(ui.all.hidden, true);
  assert.equal(ui.page.indeterminate, true);
  ui.dispatch("change", "[data-select-page]", { checked: true });
  assert.equal(ui.boxes.filter((box) => box.checked).length, 20);
  assert.equal(ui.all.hidden, false);
  ui.dispatch("click", "[data-select-all]");
  assert.equal(ui.mode.value, "all");
  assert.equal(ui.clear.hidden, false);
  assert.ok(ui.boxes.every((box) => box.disabled));
  assert.match(ui.status.textContent, /全部 25/);
  ui.dispatch("click", "[data-clear-selection]");
  assert.equal(ui.mode.value, "selected");
  assert.ok(ui.boxes.every((box) => !box.checked && !box.disabled));
  assert.equal(ui.all.hidden, true);
  assert.equal(ui.clear.hidden, true);
});

test("no all-matching link is offered when the whole result fits on one page", () => {
  for (const total of [0, 5]) {
    const ui = setup(total, total);
    ui.dispatch("change", "[data-select-page]", { checked: true });
    assert.equal(ui.all.hidden, true);
  }
});

test("submission requires both an operation and a non-empty selection", () => {
  const ui = setup();
  assert.equal(ui.dispatch("submit", "form"), true);
  assert.match(ui.error.textContent, /请选择要执行的操作/);
  ui.operation.value = "activate";
  assert.equal(ui.dispatch("submit", "form"), true);
  assert.match(ui.error.textContent, /请至少选择一条记录/);
  ui.boxes[0].checked = true;
  ui.dispatch("change", "[data-row-selection]");
  assert.equal(ui.error.hidden, true);
  assert.equal(ui.dispatch("submit", "form"), false);
  ui.dispatch("click", "[data-select-all]");
  assert.equal(ui.dispatch("submit", "form"), false);
});

test("all matching remains unavailable unless the backend supplies that capability", () => {
  const ui = setup(25, 20, { allowSelectAll: false });
  ui.dispatch("change", "[data-select-page]", { checked: true });
  assert.equal(ui.mode.value, "selected");
  ui.dispatch("click", "[data-clear-selection]");
  ui.mode.value = "all";
  ui.operation.value = "export";
  assert.equal(ui.dispatch("submit", "form"), true);
});

test("the shared controller supports user wording without a user-specific selector", () => {
  const ui = setup(25, 20, { selectionLabel: "位用户" });
  ui.operation.value = "activate";
  ui.dispatch("submit", "form");
  assert.equal(ui.error.textContent, "请至少选择一位用户。");
  ui.boxes[0].checked = true;
  ui.dispatch("change", "[data-row-selection]");
  assert.equal(ui.status.textContent, "已选择 1 位用户");
});

test("an unrelated HTMX swap does not clear another list's selection", () => {
  const ui = setup();
  ui.boxes[0].checked = true;
  ui.handlers["htmx:afterSwap"]({
    detail: { target: { querySelectorAll: () => [] } },
  });
  assert.equal(ui.boxes[0].checked, true);
  ui.handlers["htmx:afterSwap"]({
    detail: { target: { closest: () => ui.form } },
  });
  assert.equal(ui.boxes[0].checked, false);
});

test("page navigation, HTMX swaps and history restore clear selection", () => {
  const ui = setup();
  for (const reset of [
    ui.windowHandlers.pageshow,
    ui.handlers["htmx:afterSwap"],
    ui.handlers["htmx:historyRestore"],
  ]) {
    ui.dispatch("click", "[data-select-all]");
    reset();
    assert.equal(ui.mode.value, "selected");
    assert.ok(ui.boxes.every((box) => !box.checked && !box.disabled));
    assert.equal(ui.page.checked, false);
    assert.equal(ui.all.hidden, true);
    assert.equal(ui.clear.hidden, true);
  }
});
