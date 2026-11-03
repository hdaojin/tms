import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../static/js/sidebar.js", import.meta.url),
  "utf8",
);

function setup(stored = null, storageFails = false) {
  const events = {};
  const attributes = {};
  const dataset = {};
  const button = {
    setAttribute: (key, value) => {
      attributes[key] = value;
    },
    addEventListener: (name, handler) => {
      events[name] = handler;
    },
  };
  const storage = {
    getItem() {
      if (storageFails) throw new Error("unavailable");
      return stored;
    },
    setItem(key, value) {
      if (storageFails) throw new Error("unavailable");
      stored = value;
    },
  };
  vm.runInNewContext(source, {
    window: { localStorage: storage },
    document: {
      documentElement: { dataset },
      querySelectorAll: () => [button],
      getElementById: () => ({}),
      addEventListener: (name, handler) => {
        events[name] = handler;
      },
    },
  });
  events.DOMContentLoaded();
  return {
    dataset,
    attributes,
    button,
    click: () => events.click(),
    stored: () => stored,
  };
}

test("默认展开，切换后保存状态并在新页面恢复", () => {
  const page = setup();
  assert.equal(page.attributes["aria-expanded"], "true");
  page.click();
  assert.equal(page.dataset.desktopNavCollapsed, "true");
  assert.equal(page.attributes["aria-label"], "展开导航");
  const next = setup(page.stored());
  assert.equal(next.attributes["aria-expanded"], "false");
  next.click();
  assert.equal(next.stored(), "false");
  assert.equal(next.button.title, "收起导航");
});

test("存储被禁用时仍然可以收起和展开", () => {
  const page = setup(null, true);
  page.click();
  assert.equal(page.dataset.desktopNavCollapsed, "true");
  page.click();
  assert.equal(page.attributes["aria-expanded"], "true");
});
