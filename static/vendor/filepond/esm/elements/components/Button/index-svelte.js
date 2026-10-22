/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as f } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as J, push as K } from "../../../vendor/svelte/src/internal/client/context.js";
import { child as L, sibling as M, only_child as N } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { user_effect as l, template_effect as h } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as c } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as O } from "../../../vendor/svelte/src/internal/client/render.js";
import { from_html as u, append as s } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as x } from "../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { attach as P } from "../../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_attribute as o } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_class as Q } from "../../../vendor/svelte/src/internal/client/dom/elements/class.js";
import { delegate as R, delegated as T } from "../../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { clsx as U } from "../../../vendor/svelte/src/internal/shared/attributes.js";
import { bind_this as X } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as e } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { createDefaultIcon as Y } from "../../common/html.js";
import { toSpaceSeparatedString as Z } from "../../common/string.js";
import { updateDataset as $, updateStyles as tt } from "../../../utils/dom.js";
import { noop as et } from "../../../utils/placeholder.js";
import { isElement as nt, isString as it } from "../../../utils/test.js";
import { svgElement as ot } from "../../attachments/svg-element.js";
var at = u('<span class="icon"></span>'), rt = u('<span class="label"> </span>'), dt = u("<button><!> <!></button>");
function Gt(S, t) {
  K(t, !0);
  let k = e(t, "class", 3, void 0), D = e(t, "type", 3, "button"), E = e(t, "onclick", 3, et), C = e(t, "part", 3, void 0), d = e(t, "icon", 3, void 0), b = e(t, "label", 3, void 0), p = e(t, "title", 3, void 0), B = e(t, "disabled", 3, !1), v = e(t, "inert", 3, !1), F = e(t, "dataset", 3, void 0), G = e(t, "styles", 3, void 0), I = e(t, "ariaDescribedby", 3, void 0), V = e(t, "command", 3, void 0), m = e(t, "commandfor", 3, void 0), W = e(t, "tabindex", 3, void 0), _ = e(t, "autofocus", 7, !1);
  const g = c(() => d() ? d().startsWith("<svg") ? d() : Y(d()) : void 0);
  let a;
  l(() => {
    $(a, F());
  }), l(() => {
    tt(a, G());
  }), l(() => {
    a.commandForElement = nt(m()) ? m() : null;
  }), l(() => {
    _() && !v() && (a.focus({ preventScroll: !0 }), _(!1));
  });
  const j = c(k), q = c(() => Z("button", f(j)));
  var n = dt(), y = L(n);
  {
    var w = (i) => {
      var r = at();
      P(r, () => ot({ svg: f(g) })), s(i, r);
    };
    x(y, (i) => {
      f(g) && i(w);
    });
  }
  var z = M(y, 2);
  {
    var A = (i) => {
      var r = rt(), H = N(r, !0);
      h(() => O(H, b())), s(i, r);
    };
    x(z, (i) => {
      b()?.length && i(A);
    });
  }
  X(n, (i) => a = i, () => a), h(
    (i) => {
      o(n, "type", D()), Q(n, 1, U(f(q))), o(n, "part", C()), n.disabled = B(), n.inert = v(), o(n, "tabindex", W()), o(n, "command", V()), o(n, "commandfor", i), o(n, "aria-describedby", I()), o(n, "title", p()?.length ? p() : void 0);
    },
    [() => it(m()) ? m() : void 0]
  ), T("click", n, function(...i) {
    E()?.apply(this, i);
  }), s(S, n), J();
}
R(["click"]);
export {
  Gt as default
};
