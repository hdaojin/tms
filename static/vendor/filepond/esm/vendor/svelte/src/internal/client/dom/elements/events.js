import { teardown as y } from "../../reactivity/effects.js";
import { define_property as k } from "../../../shared/utils.js";
import { set_active_reaction as g, set_active_effect as m, active_reaction as E, active_effect as L } from "../../runtime.js";
import { queue_micro_task as T } from "../task.js";
import { without_reactive_context as M } from "./bindings/shared.js";
const o = /* @__PURE__ */ Symbol("events"), S = /* @__PURE__ */ new Set(), q = /* @__PURE__ */ new Set();
function x(e, t, i, n = {}) {
  function a(r) {
    if (n.capture || B.call(t, r), !r.cancelBubble)
      return M(() => i?.call(this, r));
  }
  return e.startsWith("pointer") || e.startsWith("touch") || e === "wheel" ? (a.__removed = !1, T(() => {
    a.__removed || t.addEventListener(e, a, n);
  })) : t.addEventListener(e, a, n), a;
}
function j(e, t, i, n, a) {
  var r = { capture: n, passive: a }, l = x(e, t, i, r);
  (t === document.body || // @ts-ignore
  t === window || // @ts-ignore
  t === document || // Firefox has quirky behavior, it can happen that we still get "canplay" events when the element is already removed
  t instanceof HTMLMediaElement) && y(() => {
    l.__removed = !0, t.removeEventListener(e, l, r);
  });
}
function z(e, t, i) {
  (t[o] ??= {})[e] = i;
}
function A(e) {
  for (var t = 0; t < e.length; t++)
    S.add(e[t]);
  for (var i of q)
    i(e);
}
let s = null, _ = !1;
function B(e) {
  var t = this, i = (
    /** @type {Node} */
    t.ownerDocument
  ), n = e.type, a = e.composedPath?.() || [], r = (
    /** @type {null | Element} */
    a[0] || e.target
  );
  s = e, _ || (_ = !0, setTimeout(() => {
    _ = !1, s = null;
  }));
  var l = 0, d = s === e && e[o];
  if (d) {
    var u = a.indexOf(d);
    if (u !== -1 && (t === document || t === /** @type {any} */
    window)) {
      e[o] = t;
      return;
    }
    var p = a.indexOf(t);
    if (p === -1)
      return;
    u <= p && (l = u);
  }
  if (r = /** @type {Element} */
  a[l] || e.target, r !== t) {
    k(e, "currentTarget", {
      configurable: !0,
      get() {
        return r || i;
      }
    });
    var b = E, w = L;
    g(null), m(null);
    try {
      for (var c, v = []; r !== null && r !== t; ) {
        try {
          var h = r[o]?.[n];
          h != null && (!/** @type {any} */
          r.disabled || // DOM could've been updated already by the time this is reached, so we check this as well
          // -> the target could not have been disabled because it emits the event in the first place
          e.target === r) && h.call(r, e);
        } catch (f) {
          c ? v.push(f) : c = f;
        }
        if (e.cancelBubble) break;
        l++, r = l < a.length ? (
          /** @type {Element} */
          a[l]
        ) : null;
      }
      if (c) {
        for (let f of v)
          queueMicrotask(() => {
            throw f;
          });
        throw c;
      }
    } finally {
      e[o] = t, delete e.currentTarget, g(b), m(w);
    }
  }
}
export {
  S as all_registered_events,
  x as create_event,
  A as delegate,
  z as delegated,
  j as event,
  o as event_symbol,
  B as handle_event_propagation,
  q as root_event_handles
};
