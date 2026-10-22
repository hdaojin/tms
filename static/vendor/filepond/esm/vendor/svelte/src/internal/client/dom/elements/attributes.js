import { LOADING_ATTR_SYMBOL as D, ATTRIBUTES_CACHE as z, IS_XHTML as L } from "../../constants.js";
import { NAMESPACE_HTML as K, ATTACHMENT_KEY as X, UNINITIALIZED as Z } from "../../../../constants.js";
import { get as q, set_active_reaction as R, set_active_effect as V, active_reaction as F, active_effect as J } from "../../runtime.js";
import { get_prototype_of as Q, get_descriptors as W } from "../../../shared/utils.js";
import { managed as x, destroy_effect as G, branch as tt, effect as et } from "../../reactivity/effects.js";
import { autofocus as it } from "./misc.js";
import { flatten as rt } from "../../reactivity/async.js";
import { delegated as st, delegate as ot, create_event as at } from "./events.js";
import { is_capture_event as ft, normalize_attribute as ut, can_delegate_event as ct } from "../../../../utils.js";
import { attach as lt } from "./attachments.js";
import { clsx as nt } from "../../../shared/attributes.js";
import { set_class as _t } from "./class.js";
import { set_style as vt } from "./style.js";
import { set_default_select_value as U, select_option as k, init_select as dt, set_selected as pt } from "./bindings/select.js";
const S = /* @__PURE__ */ Symbol("class"), g = /* @__PURE__ */ Symbol("style"), H = /* @__PURE__ */ Symbol("is custom element"), $ = /* @__PURE__ */ Symbol("is html"), Tt = L ? "input" : "INPUT", bt = L ? "option" : "OPTION", j = L ? "select" : "SELECT", ht = L ? "progress" : "PROGRESS";
function Vt(t, i) {
  var e = C(t);
  e.value === (e.value = // treat null and undefined the same for the initial value
  i ?? void 0) || // @ts-expect-error
  // `progress` elements always need their value set when it's `0`
  t.value === i && (i !== 0 || t.nodeName !== ht) || (t.value = i ?? "");
}
function Gt(t, i) {
  var e = C(t);
  e.checked !== (e.checked = // treat null and undefined the same for the initial value
  i ?? void 0) && (t.checked = i);
}
function I(t, i, e, v) {
  var _ = C(t);
  _[i] !== (_[i] = e) && (i === "loading" && (t[D] = e), e == null ? t.removeAttribute(i) : typeof e != "string" && M(t).has(i) ? t[i] = e : t.setAttribute(i, e));
}
function Ut(t, i, e) {
  var v = F, _ = J;
  R(null), V(null);
  try {
    // `style` should use `set_attribute` rather than the setter
    i !== "style" && // Don't compute setters for custom elements while they aren't registered yet,
    // because during their upgrade/instantiation they might add more setters.
    // Instead, fall back to a simple "an object, then set as property" heuristic.
    (w.has(t.getAttribute("is") || t.nodeName) || // customElements may not be available in browser extension contexts
    !customElements || customElements.get(t.getAttribute("is") || t.nodeName.toLowerCase()) ? M(t).has(i) : e && typeof e == "object") ? t[i] = e : I(t, i, e == null ? e : String(e));
  } finally {
    R(v), V(_);
  }
}
function yt(t, i, e, v, _ = !1, E = !1) {
  var c = C(t), h = c[H], O = !c[$], o = i || {}, d = t.nodeName === bt, N = t.nodeName === j;
  for (var p in i)
    !(p in e) && p[0] + p[1] !== "$$" && (e[p] = null);
  e.class ? e.class = nt(e.class) : e[S] && (e.class = null), e[g] && (e.style ??= null);
  var y = M(t);
  if (t.nodeName === Tt && "type" in e && ("value" in e || "__value" in e)) {
    var a = e.type;
    (a !== o.type || a === void 0 && t.hasAttribute("type")) && (o.type = a, I(t, "type", a));
  }
  for (const r in e) {
    let s = e[r];
    if (d && r === "value" && s == null) {
      t.value = t.__value = "", o[r] = s;
      continue;
    }
    if (r === "class") {
      var m = t.namespaceURI === "http://www.w3.org/1999/xhtml";
      _t(t, m, s, v, i?.[S], e[S]), o[r] = s, o[S] = e[S];
      continue;
    }
    if (r === "style") {
      vt(t, s, i?.[g], e[g]), o[r] = s, o[g] = e[g];
      continue;
    }
    var A = o[r];
    if (!(s === A && !(s === void 0 && t.hasAttribute(r)))) {
      o[r] = s;
      var T = r[0] + r[1];
      if (T !== "$$")
        if (T === "on") {
          const n = {}, b = "$$" + r;
          let u = r.slice(2);
          var l = ct(u);
          if (ft(u) && (u = u.slice(0, -7), n.capture = !0), !l && A) {
            if (s != null) continue;
            t.removeEventListener(u, o[b], n), o[b] = null;
          }
          if (l)
            st(u, t, s), ot([u]);
          else if (s != null) {
            let B = function(Y) {
              o[r].call(this, Y);
            };
            o[b] = at(u, t, B, n);
          }
        } else if (r === "style")
          I(t, r, s);
        else if (r === "autofocus")
          it(
            /** @type {HTMLElement} */
            t,
            !!s
          );
        else if (!h && (r === "__value" || r === "value" && s != null))
          t.value = t.__value = s;
        else if (r === "selected" && d)
          pt(
            /** @type {HTMLOptionElement} */
            t,
            s
          );
        else {
          var f = r;
          O || (f = ut(f));
          var P = f === "defaultValue" || f === "defaultChecked";
          if (N && f === "defaultValue") continue;
          if (s == null && !h && !P)
            if (c[r] = null, f === "value" || f === "checked") {
              let n = (
                /** @type {HTMLInputElement} */
                t
              );
              const b = i === void 0;
              if (f === "value") {
                let u = n.defaultValue;
                n.removeAttribute(f), n.defaultValue = u, n.value = n.__value = b ? u : null;
              } else {
                let u = n.defaultChecked;
                n.removeAttribute(f), n.defaultChecked = u, n.checked = b ? u : !1;
              }
            } else
              t.removeAttribute(r);
          else P || (h || typeof s != "string") && y.has(f) ? (t[f] = s, f in c && (c[f] = Z)) : typeof s != "function" && I(t, f, s);
        }
    }
  }
  return o;
}
function kt(t, i, e = [], v = [], _ = [], E, c = !1, h = !1) {
  rt(_, e, v, (O) => {
    var o = void 0, d = {}, N = t.nodeName === j, p = !1;
    if (x(() => {
      var a = i(...O.map(q)), m = yt(
        t,
        o,
        a,
        E,
        c,
        h
      );
      if (p && N) {
        var A = (
          /** @type {HTMLSelectElement} */
          t
        );
        "defaultValue" in a && U(A, a.defaultValue), "value" in a && k(A, a.value);
      }
      for (let l of Object.getOwnPropertySymbols(d))
        a[l] || G(d[l]);
      for (let l of Object.getOwnPropertySymbols(a)) {
        var T = a[l];
        l.description === X && (!o || T !== o[l]) && (d[l] && G(d[l]), d[l] = tt(() => lt(t, () => T))), m[l] = T;
      }
      o = m;
    }), N) {
      var y = (
        /** @type {HTMLSelectElement} */
        t
      );
      et(() => {
        var a = (
          /** @type {Record<string | symbol, any>} */
          o
        );
        "defaultValue" in a && U(y, a.defaultValue), k(y, a.value, !0), dt(y);
      });
    }
    p = !0;
  });
}
function C(t) {
  return (
    /** @type {Record<string | symbol, unknown>} **/
    /** @type {any} */
    t[z] ??= {
      [H]: t.nodeName.includes("-"),
      [$]: t.namespaceURI === K
    }
  );
}
var w = /* @__PURE__ */ new Map();
function M(t) {
  var i = t.getAttribute("is") || t.nodeName, e = w.get(i);
  if (e) return e;
  w.set(i, e = /* @__PURE__ */ new Set());
  for (var v, _ = t, E = Element.prototype; E !== _; ) {
    v = W(_);
    for (var c in v)
      v[c].set && // better safe than sorry, we don't want spread attributes to mess with HTML content
      c !== "innerHTML" && c !== "textContent" && c !== "innerText" && e.add(c);
    _ = Q(_);
  }
  return e;
}
export {
  S as CLASS,
  g as STYLE,
  kt as attribute_effect,
  I as set_attribute,
  Gt as set_checked,
  Ut as set_custom_element_data,
  Vt as set_value
};
