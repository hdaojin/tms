/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as e } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as K, push as L } from "../../../vendor/svelte/src/internal/client/context.js";
import { child as o, sibling as x } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as m, set as i } from "../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_effect as N, template_effect as E } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as a } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as _ } from "../../../vendor/svelte/src/internal/client/render.js";
import { from_html as Q, append as U } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { attach as g } from "../../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_custom_element_data as X } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_style as Y } from "../../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { prop as Z, spread_props as ee, rest_props as te } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import "../TextInput/index.js";
import { resizable as w } from "../../attachments/resizable.js";
import { isNumber as d } from "../../../utils/test.js";
import { getExtensionFromFilename as ie, getFilenameWithoutExtension as ne } from "../../../utils/file.js";
import re from "../TextInput/index-svelte.js";
var oe = /* @__PURE__ */ new Set([
  "$$slots",
  "$$events",
  "$$legacy",
  "value",
  "onblur",
  "onconfirm"
]), ae = Q('<filename-input><!><span> </span> <div class="measure-island"><div class="measure" aria-hidden="true"> </div> <div class="measure" aria-hidden="true"> </div></div></filename-input>', 2);
function be(I, s) {
  L(s, !0);
  let f = Z(s, "value", 3, ""), R = te(s, oe);
  const u = a(() => ie(f()));
  let n = m(void 0), p = m(void 0), c = m(void 0), l = a(() => ({ current: f() })), v = !1;
  function z() {
    i(l, { current: f() });
  }
  function C(t) {
    if (t.trim().length <= 0) {
      z();
      return;
    }
    v = !0, s.onconfirm?.(`${t}${e(u)}`);
  }
  function O() {
    v = !1;
  }
  function V() {
    v || z();
  }
  function q(t) {
    i(l, { current: t + e(u) });
  }
  function A(t) {
    i(n, t.width, !0);
  }
  function B(t) {
    i(p, t.width, !0);
  }
  function M(t) {
    i(c, t.width, !0);
  }
  const P = a(() => d(e(n)) ? `${e(n)}px` : void 0), S = 1;
  let F = m("");
  N(() => {
    d(e(n)) && d(e(p)) && T(e(n), e(p));
  });
  function T(t, J) {
    requestAnimationFrame(() => {
      i(F, t > J + S ? "" : void 0, !0);
    });
  }
  const j = a(() => d(e(c)) ? `${e(c)}px` : void 0);
  var r = ae();
  E(() => X(r, "data-overflow", e(F)));
  let W;
  var b = o(r);
  {
    let t = a(() => ne(e(l).current));
    re(b, ee(
      {
        get value() {
          return e(t);
        }
      },
      () => R,
      {
        oninput: q,
        onfocus: O,
        onblur: V,
        onconfirm: C
      }
    ));
  }
  var y = x(b), k = o(y), D = x(y, 2), h = o(D), G = o(h);
  g(h, () => w({ onresize: A }));
  var $ = x(h, 2), H = o($);
  g($, () => w({ onresize: M })), g(r, () => w({ onresize: B })), E(() => {
    W = Y(r, "", W, {
      "--value-width": e(P),
      "--extension-width": e(j)
    }), _(k, e(u)), _(G, e(l).current), _(H, e(u));
  }), U(I, r), K();
}
export {
  be as default
};
