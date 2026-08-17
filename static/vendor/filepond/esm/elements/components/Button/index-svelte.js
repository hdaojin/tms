/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as f } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as K, push as L } from "../../../vendor/svelte/src/internal/client/context.js";
import { child as h, sibling as M } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { user_effect as l, template_effect as k } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as s } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as N } from "../../../vendor/svelte/src/internal/client/render.js";
import { from_html as u, append as c } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as S } from "../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { html as O } from "../../../vendor/svelte/src/internal/client/dom/blocks/html.js";
import { set_attribute as a } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_class as P } from "../../../vendor/svelte/src/internal/client/dom/elements/class.js";
import { delegate as Q, delegated as R } from "../../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { clsx as T } from "../../../vendor/svelte/src/internal/shared/attributes.js";
import { bind_this as U } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as e } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { createDefaultIcon as V } from "../../common/html.js";
import { toSpaceSeparatedString as X } from "../../common/string.js";
import { updateDataset as Y, updateStyles as Z } from "../../../utils/dom.js";
import { noop as $ } from "../../../utils/placeholder.js";
import { isElement as tt, isString as et } from "../../../utils/test.js";
var ot = u('<span class="icon"></span>'), nt = u('<span class="label"> </span>'), rt = u("<button><!> <!></button>");
function Ct(x, t) {
  L(t, !0);
  let D = e(t, "class", 3, void 0), C = e(t, "type", 3, "button"), E = e(t, "onclick", 3, $), B = e(t, "part", 3, void 0), m = e(t, "icon", 3, void 0), b = e(t, "label", 3, void 0), p = e(t, "title", 3, void 0), F = e(t, "disabled", 3, !1), v = e(t, "inert", 3, !1), I = e(t, "dataset", 3, void 0), W = e(t, "styles", 3, void 0), j = e(t, "ariaDescribedby", 3, void 0), q = e(t, "command", 3, void 0), d = e(t, "commandfor", 3, void 0), _ = e(t, "autofocus", 7, !1);
  const g = s(() => m() ? m().startsWith("<svg") ? m() : V(m()) : void 0);
  let r;
  l(() => {
    Y(r, I());
  }), l(() => {
    Z(r, W());
  }), l(() => {
    r.commandForElement = tt(d()) ? d() : null;
  }), l(() => {
    _() && !v() && (r.focus({ preventScroll: !0 }), _(!1));
  });
  const w = s(D), z = s(() => X("button", f(w)));
  var o = rt(), y = h(o);
  {
    var A = (n) => {
      var i = ot();
      O(i, () => f(g), !0), c(n, i);
    };
    S(y, (n) => {
      f(g) && n(A);
    });
  }
  var G = M(y, 2);
  {
    var H = (n) => {
      var i = nt(), J = h(i);
      k(() => N(J, b())), c(n, i);
    };
    S(G, (n) => {
      b()?.length && n(H);
    });
  }
  U(o, (n) => r = n, () => r), k(
    (n) => {
      a(o, "type", C()), P(o, 1, T(f(z))), a(o, "part", B()), o.disabled = F(), o.inert = v(), a(o, "command", q()), a(o, "commandfor", n), a(o, "aria-describedby", j()), a(o, "title", p()?.length ? p() : void 0);
    },
    [() => et(d()) ? d() : void 0]
  ), R("click", o, function(...n) {
    E()?.apply(this, n);
  }), c(x, o), K();
}
Q(["click"]);
export {
  Ct as default
};
