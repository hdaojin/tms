/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { template_effect as p } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { sibling as v, child as I, only_child as a } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { set_text as o } from "../../../vendor/svelte/src/internal/client/render.js";
import { from_html as S, append as x } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { set_attribute as d } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { prop as i } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
var L = S("<time-indicator><time> </time> / <time> </time></time-indicator>", 2);
function j(n, t) {
  let l = i(t, "timeISO", 3, "0:00"), f = i(t, "timeLabel", 3, "0:00"), u = i(t, "durationISO", 3, "0S"), c = i(t, "durationLabel", 3, "0:00");
  var m = L(), e = I(m), _ = a(e, !0), r = v(e, 2), b = a(r, !0);
  p(() => {
    d(e, "datetime", l()), o(_, f()), d(r, "datetime", u()), o(b, c());
  }), x(n, m);
}
export {
  j as default
};
