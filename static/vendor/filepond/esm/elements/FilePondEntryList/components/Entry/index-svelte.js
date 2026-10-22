/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as t } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as R, push as Y } from "../../../../vendor/svelte/src/internal/client/context.js";
import { first_child as j, sibling as m, child as q, only_child as F } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { user_effect as G, template_effect as H } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as e } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as J } from "../../../../vendor/svelte/src/internal/client/render.js";
import { snippet as K } from "../../../../vendor/svelte/src/internal/client/dom/blocks/snippet.js";
import { from_html as M, append as N } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { attribute_effect as O, STYLE as Q, set_attribute as U } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { bind_this as V } from "../../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as p, spread_props as g, rest_props as W } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import "../../../components/ElementPane/index.js";
import { getEntryContext as X } from "../../contexts/entryContext.js";
import { getSpringElementTreeContext as Z } from "../../contexts/springElementTreeContext.js";
import { toSpaceSeparatedString as $ } from "../../../common/string.js";
import { updateDataset as tt } from "../../../../utils/dom.js";
import { propsToAttributes as et } from "../../../common/dom.js";
import u from "../../../components/ElementPane/index-svelte.js";
var rt = /* @__PURE__ */ new Set([
  "$$slots",
  "$$events",
  "$$legacy",
  "children",
  "part",
  "class",
  "legendId",
  "dataset"
]), ot = M('<fieldset><legend class="implicit"> </legend> <!></fieldset> <!> <!>', 1);
function bt(h, r) {
  Y(r, !0);
  let _ = p(r, "part", 3, void 0), x = p(r, "class", 3, void 0), S = p(r, "legendId", 3, void 0), v = W(r, rt), s;
  const y = e(x), b = e(_);
  G(() => {
    tt(s, r.dataset);
  });
  const k = e(() => t(y)), C = e(() => $("entry", t(k))), z = e(() => et(v)), d = Z(), o = e(() => d.currentSize), i = e(() => d.targetSize), E = X(), P = e(() => E.current.name), l = e(() => t(o) && t(i)), w = e(() => t(l) ? t(i).width - t(o).width : 0), I = e(() => t(l) ? t(i).height - t(o).height : 0), T = e(() => `0px ${t(w)}px ${t(I)}px 0px`);
  var c = ot(), n = j(c);
  O(n, () => ({
    class: t(C),
    part: t(b),
    ...t(z),
    [Q]: { "--mask": t(T) }
  }));
  var a = q(n), A = F(a, !0), B = m(a, 2);
  K(B, () => r.children), V(n, (L) => s = L, () => s);
  var f = m(n, 2);
  u(f, g({ class: "entry-back" }, () => t(o)));
  var D = m(f, 2);
  u(D, g({ class: "entry-front" }, () => t(o))), H(() => {
    U(a, "id", S()), J(A, t(P));
  }), N(h, c), R();
}
export {
  bt as default
};
