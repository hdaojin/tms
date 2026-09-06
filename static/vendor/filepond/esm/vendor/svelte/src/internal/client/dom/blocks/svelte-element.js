import { NAMESPACE_SVG as c } from "../../../../constants.js";
import { EFFECT_TRANSPARENT as p } from "../../constants.js";
import { create_element as v, create_text as _ } from "../operations.js";
import { block as d, teardown as g } from "../../reactivity/effects.js";
import { set_should_intro as n } from "../../render.js";
import { active_effect as h } from "../../runtime.js";
import { assign_nodes as E } from "../template.js";
import { BranchManager as A } from "./branches.js";
function k(a, l, b, t, x, C) {
  var e = null, m = (
    /** @type {TemplateNode} */
    a
  ), o = new A(m, !1);
  d(() => {
    const r = l() || null;
    var i = r === "svg" ? c : void 0;
    if (r === null) {
      o.ensure(null, null), n(!0);
      return;
    }
    return o.ensure(r, (f) => {
      if (r) {
        if (e = v(r, i), E(e, e), t) {
          var s = null, u = e.appendChild(_());
          t(e, u), s?.remove();
        }
        h.nodes.end = e, f.before(e);
      }
    }), n(!0), () => {
      r && n(!1);
    };
  }, p), g(() => {
    n(!0);
  });
}
export {
  k as element
};
