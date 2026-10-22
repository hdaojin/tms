import { active_effect as f } from "./runtime.js";
import { create_user_effect as c } from "./reactivity/effects.js";
import { COMPONENT_SYMBOL as i } from "./constants.js";
import { define_property as l } from "../shared/utils.js";
import { get_or_init_context_map as o } from "../shared/context.js";
let n = null;
function v(t) {
  n = t;
}
function d(t) {
  return (
    /** @type {T} */
    o(n).get(t)
  );
}
function g(t, e) {
  return o(n).set(t, e), e;
}
function C(t, e = !1, r) {
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
function O(t) {
  var e = (
    /** @type {ComponentContext} */
    n
  ), r = e.e;
  if (r !== null) {
    e.e = null;
    for (var u of r)
      c(u);
  }
  return t !== void 0 && (e.x = t), e.i = !0, n = e.p, _(t);
}
function _(t = {}) {
  return l(t, i, { value: !0 }), t;
}
function M() {
  return !0;
}
export {
  n as component_context,
  d as getContext,
  M as is_runes,
  _ as mark_as_component,
  O as pop,
  C as push,
  g as setContext,
  v as set_component_context
};
