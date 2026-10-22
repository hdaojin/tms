/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as c } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as O, push as U } from "../../../vendor/svelte/src/internal/client/context.js";
import { sibling as u, child as W, only_child as j } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { user_effect as w, template_effect as p } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as s } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as z } from "../../../vendor/svelte/src/internal/client/render.js";
import { from_html as v, append as h } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as A } from "../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { html as E } from "../../../vendor/svelte/src/internal/client/dom/blocks/html.js";
import { set_custom_element_data as F, set_attribute as n, set_checked as G } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_class as _ } from "../../../vendor/svelte/src/internal/client/dom/elements/class.js";
import { delegate as H, delegated as g } from "../../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { clsx as b } from "../../../vendor/svelte/src/internal/shared/attributes.js";
import { bind_this as J } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as a } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { createDefaultIcon as K } from "../../common/html.js";
import { updateDataset as L, stopPropagation as M } from "../../../utils/dom.js";
import { getUniqueId as N } from "../../../utils/string.js";
import { toSpaceSeparatedString as Q } from "../../common/string.js";
var R = v('<span class="icon"></span>'), T = v("<boolean-input><label> </label> <input/> <!></boolean-input>", 2);
function st(k, t) {
  U(t, !0);
  const x = a(t, "class", 3, void 0), y = a(t, "part", 3, void 0), I = a(t, "dataset", 3, void 0), l = a(t, "id", 19, () => `bool-${N()}`), S = a(t, "type", 3, "checkbox");
  let m;
  const d = s(() => t.icon ? t.icon.startsWith("<svg") ? t.icon : K(t.icon) : void 0);
  w(() => {
    L(m, I());
  });
  function D(e) {
    t.onchange?.(e.target.checked);
  }
  const P = s(() => Q(y(), t.checked ? "checked" : void 0));
  var o = T();
  p(() => F(o, "part", c(P)));
  var r = W(o), q = j(r, !0), i = u(r, 2), B = u(i, 2);
  {
    var C = (e) => {
      var f = R();
      E(f, () => c(d), !0), h(e, f);
    };
    A(B, (e) => {
      c(d) && e(C);
    });
  }
  J(o, (e) => m = e, () => m), p(() => {
    _(o, 1, b(x())), n(r, "for", l()), _(r, 1, b(t.labelIsImplicit ? "implicit" : void 0)), z(q, t.label), n(i, "type", S()), n(i, "id", l()), n(i, "name", t.name), G(i, t.checked), n(i, "title", t.title?.length ? t.title : void 0);
  }), g("change", i, D), g("input", i, function(...e) {
    M?.apply(this, e);
  }), h(k, o), O();
}
H(["change", "input"]);
export {
  st as default
};
