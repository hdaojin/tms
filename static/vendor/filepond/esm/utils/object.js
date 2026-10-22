/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { isFunction as o, isPlainObject as u, isObject as j, isArray as f, isObjectOrArray as O } from "./test.js";
const b = Object.freeze({});
function d(r, e) {
  for (const [t, n] of Object.entries(r)) {
    if (o(n) && o(e[t])) {
      if (n.toString() !== e[t].toString())
        return !1;
      continue;
    }
    if (n !== e[t])
      return !1;
  }
  return !0;
}
function v(r, e) {
  const t = { ...r };
  for (const n of Object.keys(e)) {
    const i = e[n], s = Object.hasOwn(r, n) ? r[n] : void 0;
    t[n] = u(i) ? v(u(s) ? s : {}, i) : i;
  }
  return t;
}
function l(r, e) {
  for (const [t, n] of Object.entries(r))
    if (j(n)) {
      if (!l(n, e[t]))
        return !1;
    } else if (f(n)) {
      if (!y(n, e[t]))
        return !1;
    } else if (n !== e[t])
      return !1;
  return !0;
}
function y(r, e) {
  if (!f(r) || !f(e))
    return !1;
  for (let t = 0; t < r.length; t++) {
    if (O(r[t]) && O(e[t]))
      return l(r, e);
    if (r[t] !== e[t])
      return !1;
  }
  return !0;
}
function h(r = {}, e) {
  return r.hasOwnProperty(e);
}
function w(r, e) {
  const t = Object.getOwnPropertyDescriptors(r), n = Object.getOwnPropertyDescriptors(e);
  return Object.entries(t).forEach(([i, { get: s, set: c, value: p }]) => {
    n[i] || (s || c ? Object.defineProperty(e, i, {
      set: c ? (a) => r[i] = a : void 0,
      get: s ? () => r[i] : void 0
    }) : o(p) && (e[i] = r[i]));
  }), e;
}
export {
  b as EMPTY_OBJECT,
  y as arrayItemsOverlap,
  w as copyDescriptors,
  v as deepMerge,
  l as deepOverlap,
  h as hasOwnProp,
  d as isObjectValuesEqual
};
