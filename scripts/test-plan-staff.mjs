import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

test("教练筛选按姓名拼音和角色过滤，并清除被隐藏的勾选", () => {
  const handlers = {};
  vm.runInNewContext(readFileSync(new URL("../static/js/plan-staff.js", import.meta.url), "utf8"), {
    document: { addEventListener: (type, handler) => { handlers[type] = handler; } },
  });
  const search = { value: "zs", matches: () => true };
  const role = { value: "2" };
  const firstBox = { checked: true };
  const secondBox = { checked: true };
  const rows = [
    { dataset: { staffSearchText: "张三 zhangsan zs", staffRoles: "2" }, querySelector: () => firstBox },
    { dataset: { staffSearchText: "李四 lisi ls", staffRoles: "3" }, querySelector: () => secondBox },
  ];
  const section = {
    querySelector: (selector) => selector === "[data-staff-search]" ? search : role,
    querySelectorAll: () => rows,
  };
  search.closest = () => section;
  handlers.input({ target: search });
  assert.equal(rows[0].hidden, false);
  assert.equal(rows[1].hidden, true);
  assert.equal(firstBox.checked, true);
  assert.equal(secondBox.checked, false);
});
