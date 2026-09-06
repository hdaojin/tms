/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { template_effect as p } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { sibling as v, child as m } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { set_text as o } from "../../../../vendor/svelte/src/internal/client/render.js";
import { from_html as I, append as S } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { set_attribute as d } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { prop as i } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
var x = I("<media-time-indicator><time> </time> / <time> </time></media-time-indicator>", 2);
function T(n, t) {
  let f = i(t, "timeISO", 3, "0:00"), l = i(t, "timeLabel", 3, "0:00"), _ = i(t, "durationISO", 3, "0S"), c = i(t, "durationLabel", 3, "0:00");
  var a = x(), e = m(a), u = m(e), r = v(e, 2), b = m(r);
  p(() => {
    d(e, "datetime", f()), o(u, l()), d(r, "datetime", _()), o(b, c());
  }), S(n, a);
}
export {
  T as default
};
