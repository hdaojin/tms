import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL("../static/js/training-log-editor.js", import.meta.url),
  "utf8",
);

test("实时预览向当前草稿地址发送未保存的正文", () => {
  const draftUrl = "https://tms.example/training/logs/ai/7/?return_plan=3";
  const field = {
    name: "notes",
    value: "**未保存的正文**",
    matches: () => true,
  };
  const editor = {
    action: { toString: () => "[object RadioNodeList]" },
    getAttribute: () => null,
    elements: {
      csrfmiddlewaretoken: { value: "token" },
      revision: { value: "3" },
    },
    querySelector: () => null,
    querySelectorAll: () => [field],
    addEventListener: (_type, listener) => (editor.onInput = listener),
  };
  const requests = [];
  const preview = {
    replaceChildren: () => (preview.fields = []),
    append: (input) => preview.fields.push([input.name, input.value]),
    submit: () =>
      requests.push([
        String(preview.action),
        Object.fromEntries(preview.fields),
      ]),
  };
  vm.runInNewContext(source, {
    document: {
      querySelector: (selector) =>
        selector === "[data-log-editor]"
          ? editor
          : { hasAttribute: () => true },
      createElement: (tag) => (tag === "form" ? preview : {}),
      body: { append() {} },
    },
    window: { location: { href: draftUrl } },
    setTimeout: (callback) => callback(),
    clearTimeout() {},
  });

  assert.deepEqual(requests, []);
  editor.onInput({ target: field });
  assert.deepEqual(requests, [
    [
      draftUrl,
      {
        action: "preview",
        csrfmiddlewaretoken: "token",
        revision: "3",
        notes: field.value,
      },
    ],
  ]);
});

test("训练日志按模型和实际思考模式启用参数并清除旧值", () => {
  const settings = {
    1: { effort: true, default_thinking: "enabled" },
    2: { effort: false, default_thinking: "disabled" },
  };
  const context = {
    document: {
      querySelector: () => null,
      getElementById: () => ({ textContent: JSON.stringify(settings) }),
    },
  };
  vm.runInNewContext(source, context);

  const controls = Object.fromEntries(
    ["model", "thinking", "effort"].map((name) => [
      name,
      Object.assign(new EventTarget(), { value: "" }),
    ]),
  );
  const groups = { "[data-log-thinking]": {}, "[data-log-effort]": {} };
  const section = { querySelector: (selector) => groups[selector] };
  const form = { querySelector: () => section, elements: controls };
  const change = (name, value) => {
    controls[name].value = value;
    controls[name].dispatchEvent(new Event("change"));
  };
  const check = (thinking, effort) => {
    assert.equal(section.hidden, !thinking);
    assert.equal(groups["[data-log-thinking]"].disabled, !thinking);
    assert.equal(groups["[data-log-effort]"].hidden, !effort);
    assert.equal(groups["[data-log-effort]"].disabled, !effort);
  };

  context.initReasoningSettings(form);
  check(false, false);
  change("model", "1");
  check(true, true);
  change("effort", "max");
  change("thinking", "disabled");
  check(true, false);
  assert.equal(controls.effort.value, "");
  change("thinking", "enabled");
  change("effort", "high");
  change("model", "2");
  check(true, false);
  assert.equal(controls.thinking.value, "");
  assert.equal(controls.effort.value, "");
  change("thinking", "enabled");
  check(true, false);
  change("model", "3");
  check(false, false);
});
