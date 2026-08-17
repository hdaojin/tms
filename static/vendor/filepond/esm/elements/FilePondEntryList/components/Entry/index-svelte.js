/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as t } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as L, push as R } from "../../../../vendor/svelte/src/internal/client/context.js";
import { first_child as Y, sibling as m, child as g } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { user_effect as j, template_effect as q } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as e } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as F } from "../../../../vendor/svelte/src/internal/client/render.js";
import { snippet as G } from "../../../../vendor/svelte/src/internal/client/dom/blocks/snippet.js";
import { from_html as H, append as J } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { attribute_effect as K, STYLE as M, set_attribute as N } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { bind_this as O } from "../../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as p, spread_props as u, rest_props as Q } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import "../../../components/ElementPane/index.js";
import { getEntryContext as U } from "../../contexts/entryContext.js";
import { getSpringElementTreeContext as V } from "../../contexts/springElementTreeContext.js";
import { toSpaceSeparatedString as W } from "../../../common/string.js";
import { updateDataset as X } from "../../../../utils/dom.js";
import { propsToAttributes as Z } from "../../../common/dom.js";
import h from "../../../components/ElementPane/index-svelte.js";
var $ = H('<fieldset><legend class="implicit"> </legend> <!></fieldset> <!> <!>', 1);
function xt(_, r) {
  R(r, !0);
  const x = p(r, "part", 3, void 0), S = p(r, "class", 3, void 0), v = p(r, "legendId", 3, void 0), y = Q(r, [
    "$$slots",
    "$$events",
    "$$legacy",
    "children",
    "part",
    "class",
    "legendId",
    "dataset"
  ]);
  let s;
  j(() => {
    X(s, r.dataset);
  });
  const b = e(S), k = e(() => W("entry", t(b))), C = e(() => Z(y)), d = V(), o = e(() => d.currentSize), i = e(() => d.targetSize), z = U(), E = e(() => z.current.name), f = e(() => t(o) && t(i)), I = e(() => t(f) ? t(i).width - t(o).width : 0), T = e(() => t(f) ? t(i).height - t(o).height : 0), w = e(() => `0px ${t(I)}px ${t(T)}px 0px`);
  var c = $(), n = Y(c);
  K(n, () => ({
    class: t(k),
    part: x(),
    ...t(C),
    [M]: { "--mask": t(w) }
  }));
  var a = g(n), P = g(a), A = m(a, 2);
  G(A, () => r.children), O(n, (D) => s = D, () => s);
  var l = m(n, 2);
  h(l, u({ class: "entry-back" }, () => t(o)));
  var B = m(l, 2);
  h(B, u({ class: "entry-front" }, () => t(o))), q(() => {
    N(a, "id", v()), F(P, t(E));
  }), J(_, c), L();
}
export {
  xt as default
};
