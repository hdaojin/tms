/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { flattenTree as a } from "./tree.js";
import { isFileEntry as l, isFile as p, isBrowser as f, isString as d, isNumber as c, isBoolean as b } from "./test.js";
import { arrayRemoveFalsy as y, arrayItemsEqual as A } from "./array.js";
import "../common/ssr.js";
import "../elements/FilePondSourceList/index-svelte.js";
function B(t, e, r) {
  t.dispatchEvent(new CustomEvent(e, r));
}
function D(t, e, r, i) {
  return t.addEventListener(e, r, i), () => g(t, e, r, i);
}
function g(t, e, r, i) {
  t.removeEventListener(e, r, i);
}
function L(t) {
  t.stopPropagation();
}
const R = {
  ENTER: "Enter"
};
function $(t, e) {
  const r = e[t.key];
  r && r(t);
}
function z(t) {
  return typeof t == "string" ? document.querySelector(t) ?? void 0 : t;
}
function E(t, e) {
  e.split(";").forEach((r) => {
    const [i, n] = r.split(":");
    if (!i.length || !n)
      return;
    const [o, u] = n.split("!important");
    t.style.setProperty(
      i,
      o,
      typeof u == "string" ? "important" : void 0
    );
  });
}
function H(t, e = {}, r = []) {
  const i = document.createElement(t), n = Object.getOwnPropertyDescriptors(i.__proto__);
  for (const [o, u] of Object.entries(e))
    u !== void 0 && (o === "style" && typeof u == "string" ? E(i, u) : n[o]?.set || o === "textContent" || o === "innerHTML" || typeof u == "function" ? i[o] = u : i.setAttribute(o, `${u}`));
  return i.append(...y(r)), i;
}
function _(t, e) {
  if (!e || !e.length)
    return t.value = "", !1;
  const r = h(e);
  return A([...r], [...t.files ?? []]) ? !1 : (t.files = r, !0);
}
function h(t) {
  const e = new DataTransfer();
  return a(t).filter((r) => l(r) && p(r.file)).forEach((r) => {
    e.items.add(r.file);
  }), e.files;
}
function k(t, e) {
  const { attempts: r = 5, interval: i = 16 } = {};
  return new Promise((n) => {
    if (t.audioTracks && t.audioTracks.length || t.mozHasAudio && t.mozHasAudio === !0)
      return n(!0);
    if (c(t.webkitAudioDecodedByteCount)) {
      let o = function() {
        if (u++, t.webkitAudioDecodedByteCount > 0)
          return n(!0);
        if (u >= r)
          return n(!1);
        setTimeout(o, i);
      }, u = 0;
      o();
      return;
    }
    n(!1);
  });
}
function q(t, e) {
  e && Object.entries(e).forEach(([r, i]) => {
    if (i === void 0) {
      delete t.dataset[r];
      return;
    }
    const n = `${i}`;
    t.dataset[r] !== n && (t.dataset[r] = n);
  });
}
function x(t, e) {
  e && Object.entries(e).forEach(([r, i]) => {
    if (i === void 0) {
      t.style.removeProperty(r);
      return;
    }
    t.style.setProperty(r, `${i}`);
  });
}
function S(t, e) {
  if (t)
    return t.getPropertyValue(e);
}
function I(t, e) {
  if (!t)
    return;
  const r = S(t, e);
  return r !== void 0 ? parseFloat(r) : void 0;
}
function K(t, e) {
  e.forEach((r) => {
    t.removeAttribute(r);
  });
}
function N(t, e) {
  Object.entries(e).forEach(([r, i]) => {
    if (typeof i == "string") {
      t.setAttribute(r, i);
      return;
    }
    t[r] = i;
  });
}
function M(t, e, r) {
  d(r) || c(r) || b(r) ? t.setAttribute(e, `${r}`) : t.removeAttribute(e);
}
function G(t, e, r) {
  r ? t.hasAttribute(e) || t.setAttribute(e, "") : t.hasAttribute(e) && t.removeAttribute(e);
}
function m(t, e) {
  if (t.hasAttribute(e)) {
    const r = t.getAttribute(e);
    return r === "" ? !0 : r;
  }
}
function J(t, ...e) {
  for (const r of e)
    if (r.hasAttribute(t))
      return m(r, t);
}
function Q(t) {
  return t ? "" : void 0;
}
function U(t, e) {
  if (!t.hasAttribute(e))
    return;
  const r = t.getAttribute(e);
  return /[a-z]$/i.test(r) ? r : parseFloat(r);
}
function W(t) {
  const e = new CSSStyleSheet();
  return e.replaceSync(t), v(e), e;
}
const s = /* @__PURE__ */ new Set();
function P({ name: t, syntax: e, inherits: r, initialValue: i }) {
  s.has(t) || (CSS.registerProperty({
    name: t,
    syntax: e,
    inherits: r,
    initialValue: i ?? void 0
  }), s.add(t));
}
function v(t) {
  for (const e of t.cssRules)
    e instanceof CSSPropertyRule && P(e);
}
function C(t) {
  return f() ? !!customElements.get(t) : !1;
}
function F(t, e) {
  f() && (C(t) || customElements.define(t, e));
}
function X(t = {}) {
  for (const [e, r] of Object.entries(t))
    F(e, r);
}
export {
  R as Key,
  D as addListener,
  Q as boolToAttributeValue,
  W as createStyleSheet,
  F as defineCustomElement,
  X as defineCustomElements,
  B as dispatchCustomEvent,
  z as getAsElement,
  m as getAttribute,
  J as getAttributeFromElements,
  h as getFileListFromEntries,
  U as getFileSizeAttributeValue,
  S as getStyleProperty,
  I as getStylePropertyAsNumber,
  H as h,
  C as hasDefinedTag,
  K as removeAttributes,
  $ as routeKeyboardEvent,
  N as setAttributes,
  G as setBooleanAttribute,
  _ as setFileInputFilesFromEntries,
  M as setStringAttribute,
  E as setStyles,
  L as stopPropagation,
  g as unlisten,
  q as updateDataset,
  x as updateStyles,
  k as videoHasAudioTrack
};
