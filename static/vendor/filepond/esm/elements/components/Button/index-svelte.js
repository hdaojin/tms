/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as f } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as L, push as M } from "../../../vendor/svelte/src/internal/client/context.js";
import { child as h, sibling as N } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { user_effect as l, template_effect as x } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as s } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as O } from "../../../vendor/svelte/src/internal/client/render.js";
import { from_html as u, append as c } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as k } from "../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { html as P } from "../../../vendor/svelte/src/internal/client/dom/blocks/html.js";
import { set_attribute as a } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_class as Q } from "../../../vendor/svelte/src/internal/client/dom/elements/class.js";
import { delegate as R, delegated as T } from "../../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { clsx as U } from "../../../vendor/svelte/src/internal/shared/attributes.js";
import { bind_this as V } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as e } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { createDefaultIcon as X } from "../../common/html.js";
import { toSpaceSeparatedString as Y } from "../../common/string.js";
import { updateDataset as Z, updateStyles as $ } from "../../../utils/dom.js";
import { noop as tt } from "../../../utils/placeholder.js";
import { isElement as et, isString as nt } from "../../../utils/test.js";
var it = u('<span class="icon"></span>'), at = u('<span class="label"> </span>'), ot = u("<button><!> <!></button>");
function Et(S, t) {
  M(t, !0);
  let D = e(t, "class", 3, void 0), C = e(t, "type", 3, "button"), E = e(t, "onclick", 3, tt), B = e(t, "part", 3, void 0), d = e(t, "icon", 3, void 0), b = e(t, "label", 3, void 0), p = e(t, "title", 3, void 0), F = e(t, "disabled", 3, !1), v = e(t, "inert", 3, !1), I = e(t, "dataset", 3, void 0), W = e(t, "styles", 3, void 0), j = e(t, "ariaDescribedby", 3, void 0), q = e(t, "command", 3, void 0), m = e(t, "commandfor", 3, void 0), w = e(t, "tabindex", 3, void 0), _ = e(t, "autofocus", 7, !1);
  const g = s(() => d() ? d().startsWith("<svg") ? d() : X(d()) : void 0);
  let o;
  l(() => {
    Z(o, I());
  }), l(() => {
    $(o, W());
  }), l(() => {
    o.commandForElement = et(m()) ? m() : null;
  }), l(() => {
    _() && !v() && (o.focus({ preventScroll: !0 }), _(!1));
  });
  const z = s(D), A = s(() => Y("button", f(z)));
  var n = ot(), y = h(n);
  {
    var G = (i) => {
      var r = it();
      P(r, () => f(g), !0), c(i, r);
    };
    k(y, (i) => {
      f(g) && i(G);
    });
  }
  var H = N(y, 2);
  {
    var J = (i) => {
      var r = at(), K = h(r);
      x(() => O(K, b())), c(i, r);
    };
    k(H, (i) => {
      b()?.length && i(J);
    });
  }
  V(n, (i) => o = i, () => o), x(
    (i) => {
      a(n, "type", C()), Q(n, 1, U(f(A))), a(n, "part", B()), n.disabled = F(), n.inert = v(), a(n, "tabindex", w()), a(n, "command", q()), a(n, "commandfor", i), a(n, "aria-describedby", j()), a(n, "title", p()?.length ? p() : void 0);
    },
    [() => nt(m()) ? m() : void 0]
  ), T("click", n, function(...i) {
    E()?.apply(this, i);
  }), c(S, n), L();
}
R(["click"]);
export {
  Et as default
};
