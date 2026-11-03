import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../static/js/training-plan-people.js", import.meta.url),
  "utf8",
);

class Element {
  constructor(dataset = {}) {
    this.dataset = dataset;
    this.children = [];
    this.events = {};
    this.hidden = false;
  }
  addEventListener(name, handler) {
    this.events[name] = handler;
  }
  click() {
    return this.events.click?.();
  }
  append(...children) {
    this.children.push(...children);
  }
  prepend(child) {
    this.children.unshift(child);
  }
  replaceChildren(...children) {
    this.children = children;
  }
  setAttribute(name, value) {
    this[name] = value;
  }
  querySelectorAll(selector) {
    if (selector === "[data-person-id]")
      return this.children.filter((node) => node.dataset?.personId);
    if (selector === "[data-result-id]")
      return this.children.filter((node) => node.dataset?.resultId);
    return [];
  }
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
  }
  focus() {}
}

function fixture(readyState = "loading") {
  const events = {},
    requests = [];
  const selected = new Element();
  selected.children = [
    new Element({
      personId: "1",
      personLabel: "甲（one）",
      unavailable: "false",
    }),
  ];
  const elements = Object.fromEntries(
    [
      "selected",
      "dialog",
      "query",
      "results",
      "staged",
      "status",
      "more",
      "open",
      "cancel",
      "confirm",
    ].map((name) => [
      `[data-plan-${name}]`,
      name === "selected" ? selected : new Element(),
    ]),
  );
  const root = new Element({
    fieldName: "competitors",
    searchUrl: "/training/search/?plan=3&role=competitor",
  });
  root.querySelector = (selector) => elements[selector];
  const form = new Element();
  form.querySelector = () => ({ value: "12" });
  root.closest = () => form;
  const document = {
    readyState,
    querySelectorAll: (selector) =>
      selector === "[data-plan-people]" ? [root] : [],
    addEventListener: (name, handler) => {
      events[name] = handler;
    },
    createElement: () => new Element(),
    createTextNode: (text) => ({ text }),
  };
  vm.runInNewContext(source, {
    document,
    URL,
    window: { location: { origin: "https://tms.example" } },
    setTimeout: (callback) => {
      callback();
      return 1;
    },
    clearTimeout: () => {},
    fetch: async (url) => {
      requests.push(url);
      return {
        ok: true,
        json: async () => ({
          results: [{ id: 2, label: "乙（two）" }],
          has_more: false,
        }),
      };
    },
  });
  events.DOMContentLoaded?.();
  return { elements, requests, form };
}

test("弹窗取消保留原选择，确认后才应用新选择，搜索携带周期", async () => {
  const f = fixture(),
    e = f.elements;
  e["[data-plan-open]"].click();
  e["[data-plan-query]"].value = "乙";
  e["[data-plan-query]"].events.input();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(f.requests[0].searchParams.get("cycle"), "12");
  assert.equal(f.requests[0].searchParams.get("plan"), "3");
  e["[data-plan-results]"].children[0].click();
  e["[data-plan-cancel]"].click();
  assert.deepEqual(
    e["[data-plan-selected]"].children.map((item) => item.dataset.personId),
    ["1"],
  );
  e["[data-plan-open]"].click();
  e["[data-plan-query]"].value = "乙";
  e["[data-plan-query]"].events.input();
  await new Promise((resolve) => setImmediate(resolve));
  e["[data-plan-results]"].children[0].click();
  e["[data-plan-confirm]"].click();
  assert.deepEqual(
    e["[data-plan-selected]"].children.map((item) => item.dataset.personId),
    ["1", "2"],
  );
});

test("页面加载完成后执行脚本也能打开添加弹窗", () => {
  const { elements: e } = fixture("complete");
  e["[data-plan-open]"].click();
  assert.equal(e["[data-plan-dialog]"].open, true);
  e["[data-plan-cancel]"].click();
  assert.equal(e["[data-plan-dialog]"].open, false);
});

test("清空选择后不显示占位人员", () => {
  const { elements: e } = fixture();
  e["[data-plan-open]"].click();
  e["[data-plan-staged]"].children[0].children.at(-1).click();
  e["[data-plan-confirm]"].click();
  assert.equal(e["[data-plan-selected]"].children.length, 0);
});

test("重置表单恢复初始人员名单并关闭弹窗", () => {
  const { elements: e, form } = fixture();
  e["[data-plan-open]"].click();
  e["[data-plan-staged]"].children[0].children.at(-1).click();
  e["[data-plan-confirm]"].click();
  e["[data-plan-open]"].click();
  form.events.reset();
  assert.deepEqual(
    e["[data-plan-selected]"].children.map((item) => item.dataset.personId),
    ["1"],
  );
  assert.equal(e["[data-plan-dialog]"].open, false);
});

test("全部选手隐藏并禁用个别指定，取消与重置恢复选择区状态", () => {
  const all = new Element();
  all.checked = true;
  const groups = new Element();
  const individuals = new Element();
  individuals.querySelector = () => groups;
  const form = new Element();
  const root = new Element();
  root.querySelector = (selector) =>
    selector === '[name="all_competitors"]' ? all : individuals;
  root.closest = () => form;
  const document = {
    readyState: "complete",
    querySelectorAll: (selector) =>
      selector === "[data-plan-participants]" ? [root] : [],
    addEventListener() {},
  };
  vm.runInNewContext(source, {
    document,
    setTimeout: (callback) => callback(),
  });
  assert.equal(individuals.hidden, true);
  assert.equal(individuals.disabled, true);
  all.checked = false;
  all.events.change();
  assert.equal(individuals.hidden, false);
  assert.equal(individuals.disabled, false);
  assert.equal(groups.disabled, false);
  all.checked = true;
  form.events.reset();
  assert.equal(individuals.hidden, true);
  assert.equal(groups.disabled, true);
});
