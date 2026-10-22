/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { hasOwnProp as f } from "./object.js";
function e(t, n = !0) {
  let r = null;
  return () => n && !y() ? !1 : (r === null && (r = t()), r);
}
function g(t) {
  return t === void 0;
}
function b(t) {
  return t == null;
}
function o(t) {
  return typeof t == "string";
}
function m(t) {
  return typeof t == "number";
}
function O(t) {
  return typeof t == "boolean";
}
function F(t) {
  return typeof t == "function";
}
function j(t) {
  return t instanceof HTMLElement;
}
function A(t) {
  let n;
  try {
    n = new URL(t);
  } catch {
    return !1;
  }
  return n.protocol === "http:" || n.protocol === "https:";
}
function E(t) {
  return t instanceof RegExp;
}
function s(t) {
  return Object.getPrototypeOf(t) === Object.prototype;
}
function h(t) {
  return t && typeof t == "object" && !Array.isArray(t);
}
function D(t) {
  if (t === null || typeof t != "object") return !1;
  const n = Object.getPrototypeOf(t);
  return n === Object.prototype || n === null;
}
function w(t) {
  return t && typeof t == "object";
}
function u(t) {
  return Array.isArray(t);
}
function L(t) {
  return o(t) && /data:/.test(t);
}
function P(t) {
  return t instanceof HTMLCanvasElement;
}
function c(t) {
  return t instanceof Blob;
}
function T(t) {
  return t instanceof Blob && !a(t);
}
function a(t) {
  return t instanceof File;
}
function l(t) {
  return t instanceof DataTransfer;
}
function B(t) {
  return !!(c(t) && /video/i.test(t.type));
}
function x(t) {
  return !!(c(t) && /image/i.test(t.type));
}
function R(t) {
  return l(t.src);
}
function U(t) {
  return o(t) && t.startsWith("unit");
}
function S(t) {
  return f(t, "template");
}
function M(t) {
  return !!(t && s(t) && !u(t.entries));
}
function C(t) {
  return !!(t && s(t) && u(t.entries));
}
function H(t) {
  return t?.isDirectory;
}
function I(t) {
  return t?.isFile;
}
function y() {
  return i === null && (i = typeof window < "u" && typeof window.document < "u"), i;
}
let i = null;
const N = e(() => /^((?!chrome|android).)*(safari|iphone|ipad)/i.test(navigator.userAgent)), K = e(() => /Firefox/.test(navigator.userAgent)), V = e(() => /iPhone|iPad|iPod/.test(navigator.userAgent) || p() && navigator.maxTouchPoints >= 1), p = e(() => {
  const { platform: t } = "userAgentData" in navigator ? navigator.userAgentData : navigator;
  return /^mac/i.test(t);
});
export {
  e as createTest,
  u as isArray,
  T as isBlob,
  c as isBlobOrFile,
  O as isBoolean,
  y as isBrowser,
  P as isCanvas,
  l as isDataTransfer,
  R as isDataTransferEntry,
  L as isDataURL,
  C as isDirectoryEntry,
  j as isElement,
  a as isFile,
  M as isFileEntry,
  H as isFileSystemDirectoryEntry,
  I as isFileSystemFileEntry,
  K as isFirefox,
  F as isFunction,
  V as isIOS,
  x as isImageFile,
  S as isLocaleTemplate,
  U as isLocaleUnitKey,
  p as isMac,
  b as isNullOrUndefined,
  m as isNumber,
  h as isObject,
  s as isObjectLiteral,
  w as isObjectOrArray,
  D as isPlainObject,
  E as isRegExp,
  N as isSafari,
  o as isString,
  A as isURL,
  g as isUndefined,
  B as isVideoFile
};
