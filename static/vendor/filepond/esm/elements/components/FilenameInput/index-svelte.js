/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as e } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as L, push as N } from "../../../vendor/svelte/src/internal/client/context.js";
import { child as E, sibling as h, only_child as _ } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as s, set as r } from "../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_effect as Q, template_effect as I } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as o } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as x } from "../../../vendor/svelte/src/internal/client/render.js";
import { from_html as U, append as X } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { attach as g } from "../../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_custom_element_data as Y } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_style as Z } from "../../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { prop as ee, spread_props as te, rest_props as re } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import "../TextInput/index.js";
import { resizable as w } from "../../attachments/resizable.js";
import { isNumber as d } from "../../../utils/test.js";
import { getExtensionFromFilename as ie, getFilenameWithoutExtension as ne } from "../../../utils/file.js";
import oe from "../TextInput/index-svelte.js";
var ae = /* @__PURE__ */ new Set([
  "$$slots",
  "$$events",
  "$$legacy",
  "value",
  "onblur",
  "onconfirm"
]), ue = U('<filename-input><!><span> </span> <div class="measure-island"><div class="measure" aria-hidden="true"> </div> <div class="measure" aria-hidden="true"> </div></div></filename-input>', 2);
function be(R, a) {
  N(a, !0);
  let m = ee(a, "value", 3, ""), C = re(a, ae);
  const u = o(() => ie(m()));
  let i = s(void 0), f = s(void 0), p = s(void 0), l = o(() => ({ current: m() })), c = !1;
  function z() {
    r(l, { current: m() });
  }
  function O(t) {
    if (t.trim().length <= 0) {
      z();
      return;
    }
    c = !0, a.onconfirm?.(`${t}${e(u)}`);
  }
  function V() {
    c = !1;
  }
  function q() {
    c || z();
  }
  function A(t) {
    r(l, { current: t + e(u) });
  }
  function B(t) {
    r(i, t.width, !0);
  }
  function M(t) {
    r(f, t.width, !0);
  }
  function P(t) {
    r(p, t.width, !0);
  }
  const S = o(() => d(e(i)) ? `${e(i)}px` : void 0), T = 1;
  let F = s("");
  Q(() => {
    d(e(i)) && d(e(f)) && j(e(i), e(f));
  });
  function j(t, K) {
    requestAnimationFrame(() => {
      r(F, t > K + T ? "" : void 0, !0);
    });
  }
  const k = o(() => d(e(p)) ? `${e(p)}px` : void 0);
  var n = ue();
  I(() => Y(n, "data-overflow", e(F)));
  let W;
  var y = E(n);
  {
    let t = o(() => ne(e(l).current));
    oe(y, te(
      {
        get value() {
          return e(t);
        }
      },
      () => C,
      {
        oninput: A,
        onfocus: V,
        onblur: q,
        onconfirm: O
      }
    ));
  }
  var b = h(y), D = _(b, !0), G = h(b, 2), v = E(G), H = _(v, !0);
  g(v, () => w({ onresize: B }));
  var $ = h(v, 2), J = _($, !0);
  g($, () => w({ onresize: P })), g(n, () => w({ onresize: M })), I(() => {
    W = Z(n, "", W, {
      "--value-width": e(S),
      "--extension-width": e(k)
    }), x(D, e(u)), x(H, e(l).current), x(J, e(u));
  }), X(R, n), L();
}
export {
  be as default
};
