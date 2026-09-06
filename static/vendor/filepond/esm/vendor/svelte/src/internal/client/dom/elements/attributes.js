import { LOADING_ATTR_SYMBOL as B, ATTRIBUTES_CACHE as V, IS_XHTML as I } from "../../constants.js";
import { NAMESPACE_HTML as Y, ATTACHMENT_KEY as D, UNINITIALIZED as z } from "../../../../constants.js";
import { get as K, set_active_reaction as P, set_active_effect as R, active_reaction as X, active_effect as Z } from "../../runtime.js";
import { get_prototype_of as q, get_descriptors as F } from "../../../shared/utils.js";
import { managed as J, destroy_effect as G, branch as Q, effect as W } from "../../reactivity/effects.js";
import { autofocus as x } from "./misc.js";
import { flatten as tt } from "../../reactivity/async.js";
import { delegated as et, delegate as it, create_event as rt } from "./events.js";
import { is_capture_event as st, normalize_attribute as ot, can_delegate_event as ft } from "../../../../utils.js";
import { attach as at } from "./attachments.js";
import { clsx as ut } from "../../../shared/attributes.js";
import { set_class as ct } from "./class.js";
import { set_style as lt } from "./style.js";
import { select_option as U, init_select as nt } from "./bindings/select.js";
const g = /* @__PURE__ */ Symbol("class"), S = /* @__PURE__ */ Symbol("style"), k = /* @__PURE__ */ Symbol("is custom element"), H = /* @__PURE__ */ Symbol("is html"), _t = I ? "input" : "INPUT", vt = I ? "option" : "OPTION", dt = I ? "select" : "SELECT", pt = I ? "progress" : "PROGRESS";
function Pt(t, i) {
  var e = L(t);
  e.value === (e.value = // treat null and undefined the same for the initial value
  i ?? void 0) || // @ts-expect-error
  // `progress` elements always need their value set when it's `0`
  t.value === i && (i !== 0 || t.nodeName !== pt) || (t.value = i ?? "");
}
function Rt(t, i) {
  var e = L(t);
  e.checked !== (e.checked = // treat null and undefined the same for the initial value
  i ?? void 0) && (t.checked = i);
}
function bt(t, i) {
  i ? t.hasAttribute("selected") || t.setAttribute("selected", "") : t.removeAttribute("selected");
}
function m(t, i, e, _) {
  var n = L(t);
  n[i] !== (n[i] = e) && (i === "loading" && (t[B] = e), e == null ? t.removeAttribute(i) : typeof e != "string" && w(t).includes(i) ? t[i] = e : t.setAttribute(i, e));
}
function Gt(t, i, e) {
  var _ = X, n = Z;
  P(null), R(null);
  try {
    // `style` should use `set_attribute` rather than the setter
    i !== "style" && // Don't compute setters for custom elements while they aren't registered yet,
    // because during their upgrade/instantiation they might add more setters.
    // Instead, fall back to a simple "an object, then set as property" heuristic.
    (O.has(t.getAttribute("is") || t.nodeName) || // customElements may not be available in browser extension contexts
    !customElements || customElements.get(t.getAttribute("is") || t.nodeName.toLowerCase()) ? w(t).includes(i) : e && typeof e == "object") ? t[i] = e : m(t, i, e == null ? e : String(e));
  } finally {
    P(_), R(n);
  }
}
function At(t, i, e, _, n = !1, E = !1) {
  var u = L(t), h = u[k], C = !u[H], o = i || {}, v = t.nodeName === vt;
  for (var p in i)
    !(p in e) && p[0] + p[1] !== "$$" && (e[p] = null);
  e.class ? e.class = ut(e.class) : e[g] && (e.class = null), e[S] && (e.style ??= null);
  var N = w(t);
  if (t.nodeName === _t && "type" in e && ("value" in e || "__value" in e)) {
    var b = e.type;
    (b !== o.type || b === void 0 && t.hasAttribute("type")) && (o.type = b, m(t, "type", b));
  }
  for (const r in e) {
    let s = e[r];
    if (v && r === "value" && s == null) {
      t.value = t.__value = "", o[r] = s;
      continue;
    }
    if (r === "class") {
      var d = t.namespaceURI === "http://www.w3.org/1999/xhtml";
      ct(t, d, s, _, i?.[g], e[g]), o[r] = s, o[g] = e[g];
      continue;
    }
    if (r === "style") {
      lt(t, s, i?.[S], e[S]), o[r] = s, o[S] = e[S];
      continue;
    }
    var y = o[r];
    if (!(s === y && !(s === void 0 && t.hasAttribute(r)))) {
      o[r] = s;
      var A = r[0] + r[1];
      if (A !== "$$")
        if (A === "on") {
          const l = {}, T = "$$" + r;
          let a = r.slice(2);
          var c = ft(a);
          if (st(a) && (a = a.slice(0, -7), l.capture = !0), !c && y) {
            if (s != null) continue;
            t.removeEventListener(a, o[T], l), o[T] = null;
          }
          if (c)
            et(a, t, s), it([a]);
          else if (s != null) {
            let $ = function(j) {
              o[r].call(this, j);
            };
            o[T] = rt(a, t, $, l);
          }
        } else if (r === "style")
          m(t, r, s);
        else if (r === "autofocus")
          x(
            /** @type {HTMLElement} */
            t,
            !!s
          );
        else if (!h && (r === "__value" || r === "value" && s != null))
          t.value = t.__value = s;
        else if (r === "selected" && v)
          bt(
            /** @type {HTMLOptionElement} */
            t,
            s
          );
        else {
          var f = r;
          C || (f = ot(f));
          var M = f === "defaultValue" || f === "defaultChecked";
          if (s == null && !h && !M)
            if (u[r] = null, f === "value" || f === "checked") {
              let l = (
                /** @type {HTMLInputElement} */
                t
              );
              const T = i === void 0;
              if (f === "value") {
                let a = l.defaultValue;
                l.removeAttribute(f), l.defaultValue = a, l.value = l.__value = T ? a : null;
              } else {
                let a = l.defaultChecked;
                l.removeAttribute(f), l.defaultChecked = a, l.checked = T ? a : !1;
              }
            } else
              t.removeAttribute(r);
          else M || N.includes(f) && (h || typeof s != "string") ? (t[f] = s, f in u && (u[f] = z)) : typeof s != "function" && m(t, f, s);
        }
    }
  }
  return o;
}
function Ut(t, i, e = [], _ = [], n = [], E, u = !1, h = !1) {
  tt(n, e, _, (C) => {
    var o = void 0, v = {}, p = t.nodeName === dt, N = !1;
    if (J(() => {
      var d = i(...C.map(K)), y = At(
        t,
        o,
        d,
        E,
        u,
        h
      );
      N && p && "value" in d && U(
        /** @type {HTMLSelectElement} */
        t,
        d.value
      );
      for (let c of Object.getOwnPropertySymbols(v))
        d[c] || G(v[c]);
      for (let c of Object.getOwnPropertySymbols(d)) {
        var A = d[c];
        c.description === D && (!o || A !== o[c]) && (v[c] && G(v[c]), v[c] = Q(() => at(t, () => A))), y[c] = A;
      }
      o = y;
    }), p) {
      var b = (
        /** @type {HTMLSelectElement} */
        t
      );
      W(() => {
        U(
          b,
          /** @type {Record<string | symbol, any>} */
          o.value,
          !0
        ), nt(b);
      });
    }
    N = !0;
  });
}
function L(t) {
  return (
    /** @type {Record<string | symbol, unknown>} **/
    /** @type {any} */
    t[V] ??= {
      [k]: t.nodeName.includes("-"),
      [H]: t.namespaceURI === Y
    }
  );
}
var O = /* @__PURE__ */ new Map();
function w(t) {
  var i = t.getAttribute("is") || t.nodeName, e = O.get(i);
  if (e) return e;
  O.set(i, e = []);
  for (var _, n = t, E = Element.prototype; E !== n; ) {
    _ = F(n);
    for (var u in _)
      _[u].set && // better safe than sorry, we don't want spread attributes to mess with HTML content
      u !== "innerHTML" && u !== "textContent" && u !== "innerText" && e.push(u);
    n = q(n);
  }
  return e;
}
export {
  g as CLASS,
  S as STYLE,
  Ut as attribute_effect,
  m as set_attribute,
  Rt as set_checked,
  Gt as set_custom_element_data,
  bt as set_selected,
  Pt as set_value
};
