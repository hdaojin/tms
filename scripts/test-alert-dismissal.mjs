import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../static/js/app.js", import.meta.url),
  "utf8",
);

function setup(t, autoDismissLevels) {
  t.mock.timers.enable({ apis: ["setTimeout", "Date"], now: 0 });
  const document = new EventTarget();
  document.body = new EventTarget();
  document.body.classList = { remove() {} };
  const alerts = autoDismissLevels.map((autoDismiss) => {
    const alert = new EventTarget();
    const button = new EventTarget();
    button.closest = () => alert;
    button.dataset = {};
    alert.button = button;
    alert.hasAttribute = (name) => name === "data-auto-dismiss" && autoDismiss;
    alert.contains = (element) => element === button;
    alert.matches = () => alert.hovered;
    alert.remove = () => {
      alert.removed = true;
    };
    return alert;
  });
  document.querySelector = () => null;
  document.querySelectorAll = (selector) =>
    selector === "[data-dismiss-alert]"
      ? alerts.map((alert) => alert.button)
      : [];
  vm.runInNewContext(source, {
    document,
    performance: { now: () => Date.now() },
    window: Object.assign(new EventTarget(), { setTimeout, clearTimeout }),
  });
  document.dispatchEvent(new Event("DOMContentLoaded"));
  return { alerts, document };
}

test("自动关闭仅影响有计时的提示，其他提示可独立手动关闭", (t) => {
  const { alerts } = setup(t, [true, false, true]);
  alerts[2].button.dispatchEvent(new Event("click"));
  assert.equal(alerts[2].removed, true);
  t.mock.timers.tick(5999);
  assert.equal(alerts[0].removed, undefined);
  t.mock.timers.tick(1);
  assert.equal(alerts[0].removed, true);
  assert.equal(alerts[1].removed, undefined);
  alerts[1].button.dispatchEvent(new Event("click"));
  assert.equal(alerts[1].removed, true);
});

test("悬停与焦点均离开后继续剩余计时", (t) => {
  const {
    alerts: [alert],
    document,
  } = setup(t, [true]);
  t.mock.timers.tick(2000);
  alert.hovered = true;
  alert.dispatchEvent(new Event("mouseenter"));
  document.activeElement = alert.button;
  alert.dispatchEvent(new Event("focusin"));
  alert.hovered = false;
  alert.dispatchEvent(new Event("mouseleave"));
  t.mock.timers.tick(6000);
  assert.equal(alert.removed, undefined);
  document.activeElement = null;
  alert.dispatchEvent(new Event("focusout"));
  t.mock.timers.tick(3999);
  assert.equal(alert.removed, undefined);
  t.mock.timers.tick(1);
  assert.equal(alert.removed, true);
});
