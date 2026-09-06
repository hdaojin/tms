import { active_effect as f } from "./runtime.js";
import { create_user_effect as c } from "./reactivity/effects.js";
import { get_or_init_context_map as r } from "../shared/context.js";
let n = null;
function _(t) {
  n = t;
}
function p(t) {
  return (
    /** @type {T} */
    r(n).get(t)
  );
}
function a(t, e) {
  return r(n).set(t, e), e;
}
function x(t, e = !1, o) {
  n = {
    p: n,
    i: !1,
    c: null,
    e: null,
    s: t,
    x: null,
    r: (
      /** @type {Effect} */
      f
    ),
    l: null
  };
}
function m(t) {
  var e = (
    /** @type {ComponentContext} */
    n
  ), o = e.e;
  if (o !== null) {
    e.e = null;
    for (var u of o)
      c(u);
  }
  return t !== void 0 && (e.x = t), e.i = !0, n = e.p, t ?? /** @type {T} */
  {};
}
function v() {
  return !0;
}
export {
  n as component_context,
  p as getContext,
  v as is_runes,
  m as pop,
  x as push,
  a as setContext,
  _ as set_component_context
};
