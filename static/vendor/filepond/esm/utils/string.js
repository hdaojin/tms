/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
function o(t, e) {
  return e(t.charAt(0)) + t.slice(1);
}
function s(t) {
  return o(t, (e) => e.toUpperCase());
}
function l(t = 11) {
  return Math.random().toString(36).substring(2, 2 + Math.min(t, 11));
}
function u(t) {
  return o(t, (e) => e.toLowerCase());
}
function c(t, e = "-") {
  return u(a(t, e));
}
function a(t, e = "-") {
  return t.replace(new RegExp(`${e}.`, "g"), (n) => n.charAt(1).toUpperCase());
}
function i(t) {
  return t.split(/[\s_\b]|(?=[A-Z])/);
}
function f(t) {
  return i(t).join("-").toLowerCase();
}
let r = null;
function p() {
  return r === null && (r = new Intl.NumberFormat().resolvedOptions().locale), r;
}
function C(t, e) {
  return e.find((n) => n.test(t));
}
export {
  p as getRuntimeDefaultLocale,
  l as getUniqueId,
  u as lowerCaseFirstLetter,
  C as stringMatchesAny,
  c as toCamelCase,
  i as toCamelParts,
  f as toKebabCase,
  a as toPascalCase,
  o as transformFirstLetter,
  s as upperCaseFirstLetter
};
