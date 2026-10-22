/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as d } from "../../../../vendor/svelte/src/index-client.js";
import { pop as u, push as l } from "../../../../vendor/svelte/src/internal/client/context.js";
import { first_child as c } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { comment as s, append as h } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { element as p } from "../../../../vendor/svelte/src/internal/client/dom/blocks/svelte-element.js";
import { attach as g } from "../../../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { attribute_effect as x } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { prop as o } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { measurable as b } from "../../../attachments/measurable.js";
import { rectFromBounds as v } from "../../../../utils/rect.js";
import { noop as y } from "../../../../utils/placeholder.js";
function w(a, t) {
  l(t, !0);
  let i = o(t, "tag", 3, "li"), r = o(t, "onmeasureitem", 3, y);
  function n(e) {
    r()(t.id, t.index, v(e));
  }
  d(() => {
    r()(t.id, t.index, void 0);
  });
  var m = s(), f = c(m);
  p(f, i, !1, (e, E) => {
    g(e, () => b({ onmeasure: n })), x(e, () => ({ class: t.class, part: t.part }));
  }), h(a, m), u();
}
export {
  w as default
};
