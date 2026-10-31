import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../static/meetings/recipients.js", import.meta.url), "utf8");

function fixture(initial = []) {
  class Element {
    constructor() {
      this.dataset = {};
      this.handlers = {};
      this.children = [];
      this.attrs = {};
      this.value = "";
      this.textContent = "";
    }
    addEventListener(type, handler) { this.handlers[type] = handler; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    setAttribute(name, value) { this.attrs[name] = value; }
    removeAttribute(name) { delete this.attrs[name]; }
    focus() { this.focused = true; }
    get childElementCount() { return this.children.length; }
    querySelectorAll() { return this.children; }
  }
  const form = new Element();
  const all = new Element();
  all.checked = false;
  const selected = new Element();
  selected.children = initial.map((person) => {
    const tag = new Element();
    tag.dataset = { recipientId: String(person.id), recipientLabel: person.label, unavailable: person.unavailable ? "true" : "false" };
    return tag;
  });
  const results = new Element();
  const query = new Element();
  const status = new Element();
  const more = new Element();
  const area = new Element();
  form.querySelector = () => all;
  form.querySelectorAll = () => [area];
  const root = new Element();
  root.dataset = { searchUrl: "/meetings/recipients/search/", fieldName: "visible_users", meetingId: "17" };
  root.closest = () => form;
  root.querySelector = (selector) => ({
    "[data-recipient-selected]": selected, "[data-recipient-results]": results,
    "[data-recipient-query]": query, "[data-recipient-status]": status, "[data-recipient-more]": more,
  })[selector];
  const requests = [];
  const timers = new Map();
  let counter = 0;
  vm.runInNewContext(source, {
    document: { readyState: "complete", querySelectorAll: () => [root], createElement: () => new Element() },
    window: { location: { origin: "https://tms.example" } },
    URL, AbortController,
    fetch: (url, options) => new Promise((resolve) => { requests.push({ url, options, resolve }); }),
    setTimeout: (callback) => { const id = ++counter; timers.set(id, callback); return id; },
    clearTimeout: (id) => timers.delete(id),
  });
  function tick() { const callbacks = [...timers.values()]; timers.clear(); callbacks.forEach((callback) => callback()); }
  function enter(value) {
    query.value = value;
    query.handlers.keydown({ key: "Enter", preventDefault() {} });
  }
  async function respond(index, results, hasMore = false, ok = true) {
    requests[index].resolve({ ok, redirected: false, json: async () => ({ results, has_more: hasMore }) });
    await new Promise((resolve) => setImmediate(resolve));
  }
  return { form, all, selected, results, query, status, more, area, requests, tick, enter, respond };
}

test("empty search never fetches all users; requests include object scope and paging", async () => {
  const f = fixture();
  f.enter("   ");
  assert.equal(f.requests.length, 0);
  f.enter(" 李 ");
  assert.equal(f.requests[0].url.searchParams.get("q"), "李");
  assert.equal(f.requests[0].url.searchParams.get("meeting_id"), "17");
  await f.respond(0, [{ id: 1, label: "李一(u1)" }], true);
  assert.equal(f.more.hidden, false);
  f.more.handlers.click();
  assert.equal(f.requests[1].url.searchParams.get("page"), "2");
  await f.respond(1, [{ id: 2, label: "李二(u2)" }]);
  assert.equal(f.results.children.length, 2);
  assert.equal(f.more.hidden, true);
});

test("selections survive searches, deduplicate, remove and reset to original unavailable users", async () => {
  const f = fixture([{ id: 9, label: "原人员(original)", unavailable: true }]);
  f.enter("李");
  await f.respond(0, [{ id: 1, label: "李一(u1)" }]);
  f.results.children[0].handlers.click();
  f.results.children[0].handlers.click();
  assert.equal(f.selected.children.length, 2);
  assert.equal(f.results.children[0].disabled, true);
  assert.equal(f.query.focused, true);
  assert.equal(f.selected.children[1].children[0].name, "visible_users");
  assert.equal(f.selected.children[1].children[0].value, "1");
  f.enter("其他");
  await f.respond(1, [{ id: 2, label: "其他(u2)" }]);
  assert.equal(f.selected.children.length, 2);
  f.selected.children[1].children[2].handlers.click();
  assert.equal(f.selected.children.length, 1);
  f.results.children[0].handlers.click();
  f.form.handlers.reset();
  f.tick();
  assert.equal(f.selected.children.length, 1);
  assert.equal(f.selected.children[0].children[0].value, "9");
  assert.match(f.selected.children[0].children[1].textContent, /当前不可阅读/);
  assert.equal(f.results.children.length, 0);
});

test("late responses cannot overwrite new searches and failures show an error", async () => {
  const f = fixture();
  f.enter("旧");
  f.enter("新");
  assert.equal(f.requests[0].options.signal.aborted, true);
  await f.respond(1, [{ id: 2, label: "新人员" }]);
  await f.respond(0, [{ id: 1, label: "旧人员" }]);
  assert.equal(f.results.children.length, 1);
  assert.equal(f.results.children[0].dataset.label, "新人员");
  f.enter("失败");
  await f.respond(2, [], false, false);
  assert.match(f.status.textContent, /搜索失败/);
});

test("public toggle hides audience without dropping selections; Escape cancels search", async () => {
  const f = fixture([{ id: 1, label: "已选人员" }]);
  f.all.checked = true;
  f.all.handlers.change();
  assert.equal(f.area.hidden, true);
  assert.equal(f.selected.children.length, 1);
  f.all.checked = false;
  f.all.handlers.change();
  assert.equal(f.area.hidden, false);
  f.query.value = "待搜索";
  f.query.handlers.input();
  f.query.handlers.keydown({ key: "Escape" });
  f.tick();
  assert.equal(f.requests.length, 0);
  assert.equal(f.query.value, "");
  assert.equal(f.selected.children.length, 1);
});
