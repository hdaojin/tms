import { CLASS_CACHE as c, ATTRIBUTES_CACHE as a, STYLE_CACHE as m, TEXT_CACHE as p } from "../constants.js";
import { NAMESPACE_HTML as x } from "../../../constants.js";
import { get_descriptor as i, is_extensible as o } from "../../shared/utils.js";
var u, s, l, _;
function v() {
  if (u === void 0) {
    u = window, s = /Firefox/.test(navigator.userAgent);
    var e = Element.prototype, n = Node.prototype, t = Text.prototype;
    l = i(n, "firstChild").get, _ = i(n, "nextSibling").get, o(e) && (e[c] = void 0, e[a] = null, e[m] = void 0, e.__e = void 0), o(t) && (t[p] = void 0);
  }
}
function A(e = "") {
  return document.createTextNode(e);
}
// @__NO_SIDE_EFFECTS__
function f(e) {
  return (
    /** @type {TemplateNode | null} */
    l.call(e)
  );
}
// @__NO_SIDE_EFFECTS__
function d(e) {
  return (
    /** @type {TemplateNode | null} */
    _.call(e)
  );
}
function T(e, n) {
  return /* @__PURE__ */ f(e);
}
function S(e, n = !1) {
  {
    var t = /* @__PURE__ */ f(e);
    return t instanceof Comment && t.data === "" ? /* @__PURE__ */ d(t) : t;
  }
}
function h(e, n = 1, t = !1) {
  let r = e;
  for (; n--; )
    r = /** @type {TemplateNode} */
    /* @__PURE__ */ d(r);
  return r;
}
function b(e) {
  e.textContent = "";
}
function y() {
  return !1;
}
function w(e, n, t) {
  return n == null || n === x ? (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    t ? document.createElement(e, { is: t }) : document.createElement(e)
  ) : (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    t ? document.createElementNS(n, e, { is: t }) : document.createElementNS(n, e)
  );
}
export {
  u as $window,
  T as child,
  b as clear_text_content,
  w as create_element,
  A as create_text,
  S as first_child,
  f as get_first_child,
  d as get_next_sibling,
  v as init_operations,
  s as is_firefox,
  y as should_defer_append,
  h as sibling
};
