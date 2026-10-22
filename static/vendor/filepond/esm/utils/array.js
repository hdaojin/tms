/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
const f = Object.freeze([]);
function o(t) {
  return Array.isArray(t) ? t : [t];
}
function s(t, e, r = (n) => n !== e) {
  return [...t.filter(r), e];
}
function c(t, e, r = 0) {
  const n = r === 0 ? 1 : -1;
  t.sort((i, u) => i[e] < u[e] ? -1 * n : i[e] > u[e] ? 1 * n : 0);
}
function l(t, e) {
  return t.filter((r) => !e(r));
}
function a(t, e) {
  let r = [];
  return t.filter(e).forEach((i) => {
    const u = t.indexOf(i);
    r.push(...t.splice(u, 1));
  }), r;
}
function y(t) {
  return t.filter(Boolean);
}
function h(t, e, ...r) {
  return [...t.slice(0, e), ...r, ...t.slice(e)];
}
function A(t, e, r) {
  const n = t[e];
  return t.splice(e, 1), t.splice(r, 0, n), t;
}
function R(t, e) {
  if (t === e)
    return !0;
  if (t.length !== e.length)
    return !1;
  for (let r = 0; r < t.length; r++)
    if (t[r] !== e[r])
      return !1;
  return !0;
}
export {
  f as EMPTY_ARRAY,
  s as arrayAddUnique,
  h as arrayInsertAtIndex,
  R as arrayItemsEqual,
  A as arrayMove,
  l as arrayRemove,
  y as arrayRemoveFalsy,
  a as arrayRemoveInPlace,
  c as arraySortByItemProp,
  o as arrayWrap
};
