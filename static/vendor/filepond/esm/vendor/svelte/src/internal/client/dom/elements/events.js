import { teardown as y } from "../../reactivity/effects.js";
import { define_property as k } from "../../../shared/utils.js";
import { set_active_reaction as v, set_active_effect as m, active_reaction as E, active_effect as L } from "../../runtime.js";
import { queue_micro_task as T } from "../task.js";
import { without_reactive_context as M } from "./bindings/shared.js";
const o = /* @__PURE__ */ Symbol("events"), S = /* @__PURE__ */ new Set(), q = /* @__PURE__ */ new Set();
function x(e, t, n, i = {}) {
  function a(r) {
    if (i.capture || B.call(t, r), !r.cancelBubble)
      return M(() => n?.call(this, r));
  }
  return e.startsWith("pointer") || e.startsWith("touch") || e === "wheel" ? T(() => {
    t.addEventListener(e, a, i);
  }) : t.addEventListener(e, a, i), a;
}
function j(e, t, n, i, a) {
  var r = { capture: i, passive: a }, l = x(e, t, n, r);
  (t === document.body || // @ts-ignore
  t === window || // @ts-ignore
  t === document || // Firefox has quirky behavior, it can happen that we still get "canplay" events when the element is already removed
  t instanceof HTMLMediaElement) && y(() => {
    t.removeEventListener(e, l, r);
  });
}
function z(e, t, n) {
  (t[o] ??= {})[e] = n;
}
function A(e) {
  for (var t = 0; t < e.length; t++)
    S.add(e[t]);
  for (var n of q)
    n(e);
}
let s = null, d = !1;
function B(e) {
  var t = this, n = (
    /** @type {Node} */
    t.ownerDocument
  ), i = e.type, a = e.composedPath?.() || [], r = (
    /** @type {null | Element} */
    a[0] || e.target
  );
  s = e, d || (d = !0, setTimeout(() => {
    d = !1, s = null;
  }));
  var l = 0, _ = s === e && e[o];
  if (_) {
    var u = a.indexOf(_);
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
        return r || n;
      }
    });
    var b = E, w = L;
    v(null), m(null);
    try {
      for (var c, h = []; r !== null && r !== t; ) {
        try {
          var g = r[o]?.[i];
          g != null && (!/** @type {any} */
          r.disabled || // DOM could've been updated already by the time this is reached, so we check this as well
          // -> the target could not have been disabled because it emits the event in the first place
          e.target === r) && g.call(r, e);
        } catch (f) {
          c ? h.push(f) : c = f;
        }
        if (e.cancelBubble) break;
        l++, r = l < a.length ? (
          /** @type {Element} */
          a[l]
        ) : null;
      }
      if (c) {
        for (let f of h)
          queueMicrotask(() => {
            throw f;
          });
        throw c;
      }
    } finally {
      e[o] = t, delete e.currentTarget, v(b), m(w);
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
