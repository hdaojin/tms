import { teardown as c } from "../../../reactivity/effects.js";
import { is_array as s } from "../../../../shared/utils.js";
import { select_multiple_invalid_value as m } from "../../../warnings.js";
import { is as v } from "../../../proxy.js";
function b(e, t) {
  t ? e.hasAttribute("selected") || e.setAttribute("selected", "") : e.removeAttribute("selected");
}
function E(e, t) {
  var r = !("__defaultValue" in e);
  !r && e.__defaultValue === t || (e.__defaultValue = t, o(e, !r || "__value" in e));
}
function o(e, t) {
  var r = e.__defaultValue, u = e.multiple, n = u ? r ?? [] : null;
  if (!(u && !s(n))) {
    var f = e.selectedIndex, a = t && u ? new Set(e.selectedOptions) : null;
    for (var i of e.options) {
      var d = l(i);
      b(
        i,
        u ? (
          /** @type {any[]} */
          n.includes(d)
        ) : v(d, r)
      );
    }
    if (t)
      if (a !== null)
        for (i of e.options) {
          var _ = a.has(i);
          i.selected !== _ && (i.selected = _);
        }
      else e.selectedIndex !== f && (e.selectedIndex = f);
  }
}
function x(e, t, r = !1) {
  if (e.multiple) {
    if (t == null)
      return;
    if (!s(t))
      return m();
    for (var u of e.options)
      u.selected = t.includes(l(u));
    return;
  }
  for (u of e.options) {
    var n = l(u);
    if (v(n, t)) {
      u.selected = !0;
      return;
    }
  }
  (!r || t !== void 0) && (e.selectedIndex = -1);
}
function I(e) {
  var t = new MutationObserver((r) => {
    r.every(h) || ("__defaultValue" in e && o(e, !1), "__value" in e && x(e, e.__value));
  });
  t.observe(e, {
    // Listen to option element changes
    childList: !0,
    subtree: !0,
    // because of <optgroup>
    // Listen to option element value attribute changes
    // (doesn't get notified of select value changes,
    // because that property is not reflected as an attribute)
    attributes: !0,
    attributeFilter: ["value"]
  }), c(() => {
    t.disconnect();
  });
}
function l(e) {
  return "__value" in e ? e.__value : e.value;
}
function h(e) {
  if (
    /** @type {Element} */
    e.target.closest("selectedcontent") !== null
  )
    return !0;
  if (e.type === "childList") {
    var t = [...e.addedNodes, ...e.removedNodes];
    return t.length > 0 && t.every((r) => r.nodeName === "SELECTEDCONTENT");
  }
  return !1;
}
export {
  I as init_select,
  x as select_option,
  E as set_default_select_value,
  b as set_selected
};
