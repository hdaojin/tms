import { DESTROYING as w, STATE_SYMBOL as u } from "../../../constants.js";
import { mark_as_component as e, component_context as h } from "../../../context.js";
import { effect as S, render_effect as T } from "../../../reactivity/effects.js";
import { untrack as k, active_effect as l } from "../../../runtime.js";
function o(r, i) {
  return r === i || r?.[u] === i;
}
function Y(r = e(), i, a, m) {
  var c = (
    /** @type {ComponentContext} */
    h.r
  ), p = (
    /** @type {Effect} */
    l
  );
  return S(() => {
    var n, t;
    return T(() => {
      n = t, t = [], k(() => {
        o(a(...t), r) || (i(r, ...t), n && o(a(...n), r) && i(null, ...n));
      });
    }), () => {
      let f = p;
      for (; f !== c && f.parent !== null && f.parent.f & w; )
        f = f.parent;
      const s = () => {
        t && o(a(...t), r) && i(null, ...t);
      }, d = f.teardown;
      f.teardown = () => {
        s(), d?.();
      };
    };
  }), r;
}
export {
  Y as bind_this
};
