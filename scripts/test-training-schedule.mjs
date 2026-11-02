import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../static/js/training-schedule.js", import.meta.url), "utf8");

function fixture() {
  const events = {};
  const requests = [];
  const dialog = { open: false, opened: 0, showModal() { this.open = true; this.opened += 1; } };
  const elements = {
    "schedule-dialog": dialog,
    "schedule-results": { id: "schedule-results" },
    "schedule-activity": { id: "schedule-activity" },
  };
  vm.runInNewContext(source, {
    document: {
      addEventListener: (name, handler) => { events[name] = handler; },
      getElementById: (id) => elements[id] || null,
    },
    window: { htmx: { trigger: (element, name) => requests.push([element.id, name]) } },
  });
  return { events, requests, dialog, elements };
}

test("only a swapped editor opens the task dialog and an open dialog stays open", () => {
  const f = fixture();
  f.events["htmx:afterSwap"]({ detail: { target: { id: "schedule-results" } } });
  assert.equal(f.dialog.opened, 0);
  f.events["htmx:afterSwap"]({ detail: { target: { id: "schedule-editor" } } });
  f.events["htmx:afterSwap"]({ detail: { target: { id: "schedule-editor" } } });
  assert.equal(f.dialog.opened, 1);
});

test("a row update only refreshes activity and keeps other rows and selections intact", () => {
  const f = fixture();
  f.events.scheduleChanged({ detail: { rowsUpdated: true } });
  assert.deepEqual(f.requests, [["schedule-activity", "refreshActivity"]]);
});

test("filtered or structural changes reload results, while standalone task pages need no plan target", () => {
  const f = fixture();
  f.events.scheduleChanged({ detail: {} });
  assert.deepEqual(f.requests, [["schedule-results", "refreshSchedule"]]);
  delete f.elements["schedule-results"];
  f.events.scheduleChanged({ detail: {} });
  assert.equal(f.requests.length, 1);
});
