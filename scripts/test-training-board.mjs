import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../static/js/training-board.js", import.meta.url),
  "utf8",
);

function element(selectors = {}) {
  return {
    hidden: true,
    children: [],
    dataset: {},
    attributes: {},
    style: { setProperty() {} },
    querySelector(selector) {
      return (
        selectors[selector] ??
        this.children.find(
          (child) =>
            selector === `[data-screen-action="${child.dataset.screenAction}"]`,
        )
      );
    },
    replaceChildren(...children) {
      this.children = children;
    },
    setAttribute(key, value) {
      this.attributes[key] = value;
    },
    focus() {},
  };
}

function setup(ids, { reducedMotion = false } = {}) {
  const events = {};
  const timers = new Map();
  let interval;
  let nextId = 0;
  const date = element();
  const error = element();
  const content = {
    innerHTML: ids.join(","),
    querySelector() {
      return this.innerHTML ? { content: { textContent: "今日" } } : undefined;
    },
    querySelectorAll() {
      return (this.plans ??= this.innerHTML
        .split(",")
        .filter((id) => id && id !== "data-screen-date-value")
        .map((id) => {
          const dots = element();
          const page = element();
          const label = element();
          const controls = element({
            "[data-screen-page]": page,
            "[data-screen-pause-label]": label,
            '[data-screen-action="pause"]': element(),
            "[data-screen-dots]": dots,
          });
          return {
            dataset: { planId: id },
            contains: () => false,
            querySelectorAll: () => [],
            querySelector: (selector) =>
              selector === "[data-screen-controls]" ? controls : element(),
            controls,
            dots,
            page,
            label,
          };
        }));
    },
    contains: () => false,
    replaceChildren() {
      this.innerHTML = "";
      this.plans = undefined;
    },
    addEventListener: (name, handler) => {
      events[name] = handler;
    },
  };
  const root = element({
    "[data-screen-content]": content,
    "[data-screen-date-text]": date,
    "[data-screen-error]": error,
  });
  const document = {
    hidden: false,
    querySelector: () => root,
    createElement: () => element(),
    fonts: { ready: Promise.resolve() },
    addEventListener: (name, handler) => {
      events[name] = handler;
    },
  };
  let response = "data-screen-date-value";
  let fail = false;
  const scope = {
    document,
    URL,
    AbortSignal,
    getComputedStyle: () => ({
      borderBottomWidth: "1",
      paddingBottom: "2",
      marginTop: "3",
    }),
    ResizeObserver: class {
      disconnect() {}
      observe() {}
    },
    fetch: async (url, options) => {
      assert.equal(url.searchParams.get("fragment"), "1");
      assert.equal(options.cache, "no-store");
      content.plans = undefined;
      return { ok: !fail, text: async () => response };
    },
    window: {
      matchMedia: () => ({ matches: reducedMotion, addEventListener() {} }),
      location: new URL("http://localhost/training/board/"),
      cancelAnimationFrame() {},
      requestAnimationFrame(callback) {
        callback();
      },
      setTimeout(callback, delay) {
        assert.equal(delay, 15000);
        timers.set(++nextId, callback);
        return nextId;
      },
      clearTimeout: (id) => timers.delete(id),
      setInterval(callback, delay) {
        assert.equal(delay, 60000);
        interval = callback;
      },
      addEventListener() {},
    },
  };
  vm.runInNewContext(source, scope);
  return {
    active: () => content.querySelectorAll().find((plan) => !plan.hidden),
    timer: () => timers.values().next().value,
    click: (action) =>
      events.click({
        target: { closest: () => ({ dataset: { screenAction: action } }) },
      }),
    visibility: (hidden) => {
      document.hidden = hidden;
      events.visibilitychange();
    },
    refresh: (ids) => {
      response = ["data-screen-date-value", ...ids].join(",");
      return interval();
    },
    fail: async () => {
      fail = true;
      await interval();
      fail = false;
    },
    error,
    date,
    fit: scope.fitTaskBox,
  };
}

test("计划按顺序轮播，手动切换重置计时，暂停和后台停止轮播", () => {
  const board = setup(["12", "20"]);
  assert.equal(board.active().page.textContent, "1 / 2");
  board.timer()();
  assert.equal(board.active().page.textContent, "2 / 2");
  assert.equal(
    board.active().dots.children[1].attributes["aria-current"],
    "true",
  );
  const timer = board.timer();
  board.click("next");
  assert.equal(board.active().dataset.planId, "12");
  assert.notEqual(board.timer(), timer);
  board.click("pause");
  assert.equal(board.timer(), undefined);
  assert.equal(board.active().label.textContent, "继续轮播");
  board.click("pause");
  board.visibility(true);
  assert.equal(board.timer(), undefined);
  board.visibility(false);
  assert.equal(typeof board.timer(), "function");
});

test("刷新按计划 ID 保留当前计划，失去授权后切换，失败清除后可恢复", async () => {
  const board = setup(["12", "20"], { reducedMotion: true });
  assert.equal(board.timer(), undefined);
  board.click("1");
  await board.refresh(["20", "33"]);
  assert.equal(board.active().dataset.planId, "20");
  await board.refresh(["33"]);
  assert.equal(board.active().dataset.planId, "33");
  await board.fail();
  assert.equal(board.active(), undefined);
  assert.equal(board.error.hidden, false);
  assert.equal(board.date.textContent, "");
  await board.refresh(["20"]);
  assert.equal(board.error.hidden, true);
  assert.equal(board.active().dataset.planId, "20");
  assert.equal(board.active().controls.hidden, true);
});

test("只显示完整任务行，并为省略提示留出空间", () => {
  const { fit } = setup([]);
  const tasks = [30, 60, 90].map((bottom) => ({
    getBoundingClientRect: () => ({ bottom }),
  }));
  const more = { getBoundingClientRect: () => ({ height: 16 }) };
  let bottom = 75;
  const box = {
    getBoundingClientRect: () => ({ bottom }),
    querySelector: (selector) =>
      selector === "[data-screen-tasks]" ? { children: tasks } : more,
  };
  fit(box);
  assert.deepEqual(
    tasks.map((task) => task.hidden),
    [false, true, true],
  );
  assert.equal(more.textContent, "… 还有 2 项任务");
  bottom = 100;
  fit(box);
  assert.deepEqual(
    tasks.map((task) => task.hidden),
    [false, false, false],
  );
  assert.equal(more.hidden, true);
  tasks.push({ getBoundingClientRect: () => ({ bottom: 120 }) });
  bottom = 150;
  fit(box);
  assert.deepEqual(
    tasks.map((task) => task.hidden),
    [false, false, false, true],
  );
  assert.equal(more.textContent, "… 还有 1 项任务");
});
