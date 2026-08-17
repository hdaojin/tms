/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as t } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as tt, push as et } from "../../../../vendor/svelte/src/internal/client/context.js";
import { first_child as v, sibling as A, child as C } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { template_effect as p } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as s } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as rt } from "../../../../vendor/svelte/src/internal/client/render.js";
import { comment as D, append as c, from_html as I } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as _ } from "../../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { each as st, index as ot } from "../../../../vendor/svelte/src/internal/client/dom/blocks/each.js";
import { html as nt } from "../../../../vendor/svelte/src/internal/client/dom/blocks/html.js";
import { set_custom_element_data as R } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_class as at } from "../../../../vendor/svelte/src/internal/client/dom/elements/class.js";
import { clsx as it } from "../../../../vendor/svelte/src/internal/shared/attributes.js";
import { prop as h } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { getExtensionStatusItems as mt } from "../../../../common/entry.js";
import { statusToLabel as ft, statusToIcon as lt } from "../../../common/string.js";
import { arrayRemoveFalsy as k } from "../../../../utils/array.js";
import { getAppContext as ut } from "../../contexts/appContext.js";
import { getEntryContext as pt } from "../../contexts/entryContext.js";
import ct from "../../../components/SpringElement/index-svelte.js";
import "../../../components/ElementPane/index.js";
import gt from "../../../components/ElementPane/index-svelte.js";
var dt = I("<!> <span> </span> <!>", 1), vt = I("<entry-status><ul></ul></entry-status>", 2);
function zt(P, i) {
  et(i, !0);
  let T = h(i, "class", 3, void 0), j = h(i, "part", 3, void 0), F = h(i, "id", 3, void 0);
  const m = s(ut), L = s(() => t(m).assets), O = s(() => t(m).locale), W = s(() => t(m).enableAnimations), q = s(() => t(m).springDefaults), z = pt(), B = s(() => Object.values(z.current.extensionState)), G = { error: 5, warning: 4, success: 3, info: 2, system: 1 };
  function H({ code: e, subcode: r, type: a, values: g }, n, f) {
    const l = ft({ code: e, subcode: r, values: g }, n), u = lt({ type: a }, n, f);
    if (!(!l || !u))
      return { weight: G[a], code: e, type: a, icon: u, text: l };
  }
  const x = s(() => k(k(mt(t(B))).map((e) => H(e, t(O), t(L)))).sort((e, r) => e.weight < r.weight ? 1 : -1));
  var y = D(), J = v(y);
  {
    var K = (e) => {
      var r = vt();
      p(() => R(r, "part", j())), p(() => R(r, "id", F()));
      var a = C(r);
      st(a, 21, () => t(x), ot, (g, n) => {
        let f = () => t(n).icon, l = () => t(n).text, u = () => t(n).type;
        {
          const M = (Q, U) => {
            let d = () => U?.().visualRect;
            var b = dt(), w = v(b);
            {
              var V = (o) => {
                var E = D(), $ = v(E);
                nt($, f), c(o, E);
              };
              _(w, (o) => {
                f() && o(V);
              });
            }
            var S = A(w, 2), X = C(S), Y = A(S, 2);
            {
              var Z = (o) => {
                gt(o, {
                  get width() {
                    return d().width;
                  },
                  get height() {
                    return d().height;
                  }
                });
              };
              _(Y, (o) => {
                d() && o(Z);
              });
            }
            p(() => rt(X, l())), c(Q, b);
          };
          let N = s(() => ({ type: u() }));
          ct(g, {
            tag: "li",
            class: "entry-status-message",
            subclass: "entry-status-message-content",
            get dataset() {
              return t(N);
            },
            get enableAnimations() {
              return t(W);
            },
            get springDefaults() {
              return t(q);
            },
            children: M,
            $$slots: { default: !0 }
          });
        }
      }), p(() => at(r, 1, it(T()))), c(e, r);
    };
    _(J, (e) => {
      t(x).length && e(K);
    });
  }
  c(P, y), tt();
}
export {
  zt as default
};
