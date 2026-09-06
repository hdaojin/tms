import { lifecycle_outside_component as t } from "./errors.js";
function l(e) {
  let n = e.p;
  for (; n !== null && n.c === null; )
    n = n.p;
  return n?.c ?? null;
}
function r(e, n) {
  return e === null && t(), e.c ??= new Map(l(e) || void 0);
}
export {
  r as get_or_init_context_map
};
