import { init_operations as k, create_text as L } from "./dom/operations.js";
import { array_from as T } from "../shared/utils.js";
import { component_root as V } from "./reactivity/effects.js";
import { TEXT_CACHE as C } from "./constants.js";
import { push as j, component_context as x, mark_as_component as z, pop as A } from "./context.js";
import { all_registered_events as H, root_event_handles as E, handle_event_propagation as $ } from "./dom/elements/events.js";
import { is_passive_event as N } from "../../utils.js";
import { boundary as P } from "./dom/blocks/boundary.js";
let _ = !0;
function J(e) {
  _ = e;
}
function K(e, r) {
  var n = r == null ? "" : typeof r == "object" ? `${r}` : r;
  n !== /** @type {any} */
  (e[C] ??= e.nodeValue) && (e[C] = n, e.nodeValue = `${n}`);
}
function O(e, r) {
  return S(e, r);
}
const p = /* @__PURE__ */ new Map();
function S(e, { target: r, anchor: n, props: c = {}, events: h, context: g, intro: y = !0, transformError: M }) {
  k();
  var s = void 0, b = V(() => {
    var a = n ?? r.appendChild(L());
    P(
      /** @type {TemplateNode} */
      a,
      {
        pending: () => {
        }
      },
      (i) => {
        j({});
        var o = (
          /** @type {ComponentContext} */
          x
        );
        g && (o.c = g), h && (c.$$events = h), _ = y, s = e(i, c) || z(), _ = !0, A();
      },
      M
    );
    var m = /* @__PURE__ */ new Set(), l = (i) => {
      for (var o = 0; o < i.length; o++) {
        var t = i[o];
        if (!m.has(t)) {
          m.add(t);
          var f = N(t);
          for (const u of [r, document]) {
            var d = p.get(u);
            d === void 0 && (d = /* @__PURE__ */ new Map(), p.set(u, d));
            var w = d.get(t);
            w === void 0 ? (u.addEventListener(t, $, { passive: f }), d.set(t, 1)) : d.set(t, w + 1);
          }
        }
      }
    };
    return l(T(H)), E.add(l), () => {
      for (var i of m)
        for (const f of [r, document]) {
          var o = (
            /** @type {Map<string, number>} */
            p.get(f)
          ), t = (
            /** @type {number} */
            o.get(i)
          );
          --t == 0 ? (f.removeEventListener(i, $), o.delete(i), o.size === 0 && p.delete(f)) : o.set(i, t);
        }
      E.delete(l), a !== n && a.parentNode?.removeChild(a);
    };
  });
  return v.set(s, b), s;
}
let v = /* @__PURE__ */ new WeakMap();
function Q(e, r) {
  const n = v.get(e);
  return n ? (v.delete(e), n(r)) : Promise.resolve();
}
export {
  O as mount,
  J as set_should_intro,
  K as set_text,
  _ as should_intro,
  Q as unmount
};
