/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { flattenTree as c } from "./tree.js";
import { isFileEntry as l, isFile as p, isBrowser as f, isString as d, isNumber as a, isBoolean as y } from "./test.js";
import { arrayItemsEqual as b, arrayRemoveFalsy as g } from "./array.js";
import "../common/ssr.js";
import "../elements/FilePondSourceList/index-svelte.js";
function B(t, e, r) {
  t.dispatchEvent(new CustomEvent(e, r));
}
function O(t, e, r, i) {
  return t.addEventListener(e, r, i), () => A(t, e, r, i);
}
function A(t, e, r, i) {
  t.removeEventListener(e, r, i);
}
function j(t) {
  t.stopPropagation();
}
const R = {
  ENTER: "Enter"
};
function $(t, e) {
  const r = e[t.key];
  r && r(t);
}
function k(t) {
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
function z(t, e = {}, r = []) {
  const i = document.createElement(t), n = Object.getOwnPropertyDescriptors(i.__proto__);
  for (const [o, u] of Object.entries(e))
    u !== void 0 && (o === "style" && typeof u == "string" ? E(i, u) : n[o]?.set || o === "textContent" || o === "innerHTML" || typeof u == "function" ? i[o] = u : i.setAttribute(o, `${u}`));
  return i.append(...g(r)), i;
}
function H(t) {
  t.files = new DataTransfer().files;
}
function _(t) {
  const e = new DataTransfer();
  return t.forEach((r) => {
    e.items.add(r);
  }), e.files;
}
function I(t, e) {
  if (!e || !e.length)
    return t.value = "", !1;
  const r = h(e);
  return b([...r], [...t.files ?? []]) ? !1 : (t.files = r, !0);
}
function h(t) {
  const e = new DataTransfer();
  return c(t).filter((r) => l(r) && p(r.file)).forEach((r) => {
    e.items.add(r.file);
  }), e.files;
}
function q(t, e) {
  const { attempts: r = 5, interval: i = 16 } = {};
  return new Promise((n) => {
    if (t.audioTracks && t.audioTracks.length || t.mozHasAudio && t.mozHasAudio === !0)
      return n(!0);
    if (a(t.webkitAudioDecodedByteCount)) {
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
function x(t, e) {
  e && Object.entries(e).forEach(([r, i]) => {
    if (i === void 0) {
      delete t.dataset[r];
      return;
    }
    const n = `${i}`;
    t.dataset[r] !== n && (t.dataset[r] = n);
  });
}
function K(t, e) {
  e && Object.entries(e).forEach(([r, i]) => {
    if (i === void 0) {
      t.style.removeProperty(r);
      return;
    }
    t.style.setProperty(r, `${i}`);
  });
}
function m(t, e) {
  if (t)
    return t.getPropertyValue(e);
}
function N(t, e) {
  if (!t)
    return;
  const r = m(t, e);
  return r !== void 0 ? parseFloat(r) : void 0;
}
function M(t, e) {
  e.forEach((r) => {
    t.removeAttribute(r);
  });
}
function G(t, e, r) {
  d(r) || a(r) || y(r) ? t.setAttribute(e, `${r}`) : t.removeAttribute(e);
}
function J(t, e, r) {
  r ? t.hasAttribute(e) || t.setAttribute(e, "") : t.hasAttribute(e) && t.removeAttribute(e);
}
function S(t, e) {
  if (t.hasAttribute(e)) {
    const r = t.getAttribute(e);
    return r === "" ? !0 : r;
  }
}
function Q(t, ...e) {
  for (const r of e)
    if (r.hasAttribute(t))
      return S(r, t);
}
function U(t) {
  return t ? "" : void 0;
}
function W(t, e) {
  if (!t.hasAttribute(e))
    return;
  const r = t.getAttribute(e);
  return /[a-z]$/i.test(r) ? r : parseFloat(r);
}
function X(t) {
  const e = new CSSStyleSheet();
  return e.replaceSync(t), P(e), e;
}
const s = /* @__PURE__ */ new Set();
function v({ name: t, syntax: e, inherits: r, initialValue: i }) {
  s.has(t) || (CSS.registerProperty({
    name: t,
    syntax: e,
    inherits: r,
    initialValue: i ?? void 0
  }), s.add(t));
}
function P(t) {
  for (const e of t.cssRules)
    e instanceof CSSPropertyRule && v(e);
}
function T(t) {
  return f() ? !!customElements.get(t) : !1;
}
function F(t, e) {
  f() && (T(t) || customElements.define(t, e));
}
function Y(t = {}) {
  for (const [e, r] of Object.entries(t))
    F(e, r);
}
export {
  R as Key,
  O as addListener,
  U as boolToAttributeValue,
  X as createStyleSheet,
  F as defineCustomElement,
  Y as defineCustomElements,
  B as dispatchCustomEvent,
  _ as filesToFileList,
  k as getAsElement,
  S as getAttribute,
  Q as getAttributeFromElements,
  h as getFileListFromEntries,
  W as getFileSizeAttributeValue,
  m as getStyleProperty,
  N as getStylePropertyAsNumber,
  z as h,
  T as hasDefinedTag,
  M as removeAttributes,
  H as resetFileInput,
  $ as routeKeyboardEvent,
  J as setBooleanAttribute,
  I as setFileInputFilesFromEntries,
  G as setStringAttribute,
  E as setStyles,
  j as stopPropagation,
  A as unlisten,
  x as updateDataset,
  K as updateStyles,
  q as videoHasAudioTrack
};
