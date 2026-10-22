import { run_all as n } from "../../shared/utils.js";
import { is_flushing_sync as o } from "../reactivity/batch.js";
let s = [];
function i() {
  var t = s;
  s = [], n(t);
}
function e(t) {
  if (s.length === 0 && !o) {
    var r = s;
    queueMicrotask(() => {
      r === s && i();
    });
  }
  s.push(t);
}
function f() {
  for (; s.length > 0; )
    i();
}
export {
  f as flush_tasks,
  e as queue_micro_task
};
