import { CLASS_CACHE as d, ATTRIBUTES_CACHE as a, STYLE_CACHE as x, TEXT_CACHE as m } from "../constants.js";
import { NAMESPACE_HTML as p } from "../../../constants.js";
import { get_descriptor as o, is_extensible as u } from "../../shared/utils.js";
var l, s, _, f;
function v() {
  if (l === void 0) {
    l = window, s = /Firefox/.test(navigator.userAgent);
    var e = Element.prototype, n = Node.prototype, t = Text.prototype;
    _ = o(n, "firstChild").get, f = o(n, "nextSibling").get, u(e) && (e[d] = void 0, e[a] = null, e[x] = void 0, e.__e = void 0), u(t) && (t[m] = void 0);
  }
}
function A(e = "") {
  return document.createTextNode(e);
}
// @__NO_SIDE_EFFECTS__
function i(e) {
  return (
    /** @type {TemplateNode | null} */
    _.call(e)
  );
}
// @__NO_SIDE_EFFECTS__
function c(e) {
  return (
    /** @type {TemplateNode | null} */
    f.call(e)
  );
}
function T(e, n) {
  return /* @__PURE__ */ i(e);
}
function h(e, n = !1) {
  {
    var t = /* @__PURE__ */ i(e);
    return t instanceof Comment && t.data === "" ? /* @__PURE__ */ c(t) : t;
  }
}
function S(e, n = !1) {
  return /* @__PURE__ */ i(e);
}
function y(e, n = 1, t = !1) {
  let r = e;
  for (; n--; )
    r = /** @type {TemplateNode} */
    /* @__PURE__ */ c(r);
  return r;
}
function b(e) {
  e.textContent = "";
}
function w() {
  return !1;
}
function H(e, n, t) {
  return n == null || n === p ? (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    t ? document.createElement(e, { is: t }) : document.createElement(e)
  ) : (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    t ? document.createElementNS(n, e, { is: t }) : document.createElementNS(n, e)
  );
}
export {
  l as $window,
  T as child,
  b as clear_text_content,
  H as create_element,
  A as create_text,
  h as first_child,
  i as get_first_child,
  c as get_next_sibling,
  v as init_operations,
  s as is_firefox,
  S as only_child,
  w as should_defer_append,
  y as sibling
};
