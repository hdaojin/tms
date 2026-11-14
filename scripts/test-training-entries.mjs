import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../static/js/training-entries.js", import.meta.url),
  "utf8",
);
function fixture({ result = null, checkboxes = [], preferences = [], now = Date.parse('2026-11-14T10:00:00Z') } = {}) {
  const listeners = {},
    storage = new Map(),
    requests = [];
  for (const [key, value] of preferences) storage.set(key, value);
  const dialog = { open: true, dataset: { dirty: "1" } };
  const context = {
    Date: class extends Date {
      static now() { return now; }
    },
    document: {
      getElementById: () => dialog,
      querySelectorAll: (selector) =>
        selector.includes("duty_all") ? checkboxes : [],
      querySelector: () => result,
      addEventListener: (name, fn) => (listeners[name] ||= []).push(fn),
    },
    window: {
      addEventListener: (name, fn) => (listeners[name] ||= []).push(fn),
      confirm: () => false,
      htmx: { ajax: (...args) => requests.push(args) },
    },
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    },
  };
  vm.runInNewContext(source, context);
  return {
    dialog,
    requests,
    storage,
    dispatch: (name, event) => listeners[name]?.forEach((fn) => fn(event)),
  };
}

test("opening another entry can be cancelled when its drawer has unsaved content", () => {
  const f = fixture();
  let cancelled = false;
  f.dispatch("htmx:beforeRequest", {
    detail: {
      target: { id: "schedule-editor" },
      requestConfig: { verb: "get" },
    },
    preventDefault: () => {
      cancelled = true;
    },
  });
  assert.equal(cancelled, true);
  cancelled = false;
  f.dispatch("htmx:beforeRequest", {
    detail: {
      target: { id: "schedule-editor" },
      requestConfig: { verb: "post" },
    },
    preventDefault: () => {
      cancelled = true;
    },
  });
  assert.equal(cancelled, false);
});

test("task links inside a card do not open the schedule drawer", () => {
  const f = fixture();
  f.dispatch("click", {
    target: {
      closest: (selector) =>
        selector === "[data-slot-edit]"
          ? { dataset: { slotEdit: "/slot/" } }
          : selector.startsWith("a,")
            ? {}
            : null,
    },
  });
  assert.equal(f.requests.length, 0);
  f.dispatch("click", {
    target: {
      closest: (selector) =>
        selector === "[data-slot-edit]"
          ? { dataset: { slotEdit: "/slot/" } }
          : null,
    },
  });
  assert.equal(f.requests[0][1], "/slot/");
});

test("weekly collapse changes only the selected week and is saved per plan", () => {
  const rows = [
    { dataset: { week: "2026-11-02" } },
    { dataset: { week: "2026-11-09" } },
  ];
  const result = { dataset: { planId: "12" }, querySelectorAll: () => rows };
  const button = {
    dataset: { weekToggle: "2026-11-02" },
    getAttribute: () => "true",
    setAttribute() {},
    closest: () => result,
  };
  const click = {
    target: {
      closest: (selector) =>
        selector === "[data-week-toggle]" ? button : null,
    },
  };
  const f = fixture();
  f.dispatch("click", click);
  assert.equal(rows[0].hidden, true);
  assert.equal(rows[1].hidden, undefined);
  const key = "training-week:12:2026-11-02";
  assert.deepEqual(JSON.parse(f.storage.get(key)), {
    collapsed: true,
    expiresAt: Date.parse("2026-11-15T10:00:00Z"),
  });
  const sunday = fixture({ now: Date.parse("2026-11-15T10:00:00Z") });
  sunday.dispatch("click", click);
  assert.equal(JSON.parse(sunday.storage.get(key)).expiresAt, Date.parse("2026-11-15T16:00:00Z"));
});

test("only the current week opens by default and valid preferences take priority", () => {
  const weeks = ["2026-11-02", "2026-11-09", "2026-11-16"];
  const rows = weeks.map((week) => ({ dataset: { week } }));
  const expanded = new Map();
  const buttons = weeks.map((week) => ({
    dataset: { weekToggle: week },
    setAttribute: (key, value) => expanded.set(week, value),
  }));
  const result = {
    dataset: { planId: "8" },
    querySelectorAll: (selector) =>
      selector === "[data-week-toggle]" ? buttons : rows,
  };
  const now = Date.parse("2026-11-15T15:59:59Z");
  const keys = weeks.map((week) => `training-week:8:${week}`);
  const f = fixture({ result, now, preferences: [
    [keys[0], "0"],
    [keys[1], JSON.stringify({ collapsed: true, expiresAt: now })],
    [keys[2], JSON.stringify({ collapsed: false, expiresAt: now + 1000 })],
  ] });
  assert.deepEqual(rows.map((row) => row.hidden), [true, false, false]);
  assert.deepEqual([...expanded.values()], ["false", "true", "true"]);
  assert.deepEqual([...f.storage.keys()], [keys[2]]);
  fixture({ result, now: now + 1000, preferences: f.storage });
  assert.deepEqual(rows.map((row) => row.hidden), [true, true, false]);
});

test("all-duty disables the concrete list and unchecking enables it", () => {
  const field = { disabled: false, closest: () => null };
  const checkbox = {
    checked: true,
    name: "day-0-duty_all",
    form: {
      elements: {
        namedItem: (name) => (name === "day-0-duty_coaches" ? field : null),
      },
    },
  };
  const f = fixture({ checkboxes: [checkbox] });
  assert.equal(field.disabled, true);
  checkbox.checked = false;
  f.dispatch("change", { target: { closest: () => null } });
  assert.equal(field.disabled, false);
});

test("day-wide arrangement fills enabled slot fields and keeps them editable", () => {
  const f = fixture();
  const fields = {
    "unified-domain_choice": { value: "rest" },
    "unified-coaches": { selectedOptions: [{ value: "8" }] },
    "unified-coaches_all": { checked: false },
    "slot-0-coaches_all": { checked: true },
    "slot-0-coaches": {
      options: [
        { value: "8", selected: false },
        { value: "9", selected: true },
      ],
    },
  };
  const slotDomain = { name: "slot-0-domain_choice", value: "2" };
  const form = {
    elements: { namedItem: (name) => fields[name] },
    querySelectorAll: (selector) =>
      selector.startsWith("select") ? [slotDomain] : [],
    closest: () => f.dialog,
  };
  const button = { closest: () => form };
  f.dispatch("click", {
    target: {
      closest: (selector) => (selector === "[data-apply-day]" ? button : null),
    },
  });
  assert.equal(slotDomain.value, "rest");
  assert.equal(fields["slot-0-coaches_all"].checked, false);
  assert.equal(fields["slot-0-coaches"].options[0].selected, true);
  assert.equal(fields["slot-0-coaches"].options[1].selected, false);
  assert.equal(f.dialog.dataset.dirty, "1");
  slotDomain.value = "unused";
  assert.equal(slotDomain.value, "unused");
});

test("explicit reset reloads saved editor content without discard confirmation", () => {
  const f = fixture();
  let cancelled = false;
  f.dispatch("htmx:beforeRequest", {
    detail: {
      target: { id: "schedule-editor" },
      elt: { closest: () => ({}) },
      requestConfig: { verb: "get" },
    },
    preventDefault: () => {
      cancelled = true;
    },
  });
  assert.equal(cancelled, false);
  const target = {
    id: "schedule-editor",
    querySelector: () => null,
    querySelectorAll: () => [],
  };
  f.dispatch("htmx:afterSwap", { detail: { target } });
  assert.equal(f.dialog.dataset.dirty, "");
});

test("duty selection becomes optional only when every enabled slot is rest or unused", () => {
  const field = { closest: () => null };
  const slots = [{ value: "rest" }, { value: "unused" }];
  const checkbox = {
    checked: false,
    name: "day-0-duty_all",
    form: {
      elements: { namedItem: () => field },
      querySelectorAll: () => slots,
    },
  };
  const f = fixture({ checkboxes: [checkbox] });
  assert.equal(field.required, false);
  slots[1].value = "1";
  f.dispatch("change", { target: { closest: () => null } });
  assert.equal(field.required, true);
  slots[1].value = "";
  f.dispatch("change", { target: { closest: () => null } });
  assert.equal(field.required, true);
});
