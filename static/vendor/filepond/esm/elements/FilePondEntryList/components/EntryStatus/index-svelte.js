/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as t } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as tt, push as rt } from "../../../../vendor/svelte/src/internal/client/context.js";
import { first_child as P, sibling as C, only_child as et, child as ot } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { template_effect as f } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as r } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as st } from "../../../../vendor/svelte/src/internal/client/render.js";
import { comment as nt, append as l, from_html as _ } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as v } from "../../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { each as at, index as it } from "../../../../vendor/svelte/src/internal/client/dom/blocks/each.js";
import { attach as mt } from "../../../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_custom_element_data as O } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_class as pt } from "../../../../vendor/svelte/src/internal/client/dom/elements/class.js";
import { clsx as ut } from "../../../../vendor/svelte/src/internal/shared/attributes.js";
import { prop as h } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { getExtensionStatusItems as ct } from "../../../../common/entry.js";
import { statusToLabel as ft, statusToIcon as lt } from "../../../common/string.js";
import { arrayRemoveFalsy as R } from "../../../../utils/array.js";
import { getAppContext as dt } from "../../contexts/appContext.js";
import { getEntryContext as gt } from "../../contexts/entryContext.js";
import vt from "../../../components/SpringElement/index-svelte.js";
import "../../../components/ElementPane/index.js";
import { svgElement as ht } from "../../../attachments/svg-element.js";
import { passthrough as _t } from "../../../../utils/placeholder.js";
import xt from "../../../components/ElementPane/index-svelte.js";
var yt = _('<span class="icon"></span>'), bt = _("<!> <span> </span> <!>", 1), wt = _("<entry-status><ul></ul></entry-status>", 2);
function Qt(k, i) {
  rt(i, !0);
  let M = h(i, "class", 3, void 0), I = h(i, "part", 3, void 0), T = h(i, "id", 3, void 0);
  const j = r(T), A = r(M), F = r(I), m = r(dt), L = r(() => t(m).assets), W = r(() => t(m).locale), q = r(() => t(m).reduceMotion), z = r(() => t(m).springOptions), B = gt(), D = r(() => Object.values(B.current.extensionState)), G = { error: 5, warning: 4, success: 3, info: 2, system: 1 };
  function H({ code: e, subcode: o, type: a, values: d }, n, p) {
    const u = ft({ code: e, subcode: o, values: d }, n), c = lt({ type: a }, n, p);
    if (!(!u || !c))
      return { weight: G[a], code: e, type: a, icon: c, text: u };
  }
  const x = r(() => R(R(ct(t(D))).map((e) => H(e, t(W), t(L)))).sort((e, o) => e.weight < o.weight ? 1 : -1));
  var y = nt(), J = P(y);
  {
    var K = (e) => {
      var o = wt();
      f(() => O(o, "part", t(F))), f(() => O(o, "id", t(j)));
      var a = ot(o);
      at(a, 21, () => t(x), it, (d, n) => {
        let p = () => t(n).icon, u = () => t(n).text, c = () => t(n).type;
        {
          const N = (U, V) => {
            let g = () => (V?.()).visualRect;
            var b = bt(), w = P(b);
            {
              var X = (s) => {
                var S = yt();
                mt(S, () => ht({ svg: p() })), l(s, S);
              };
              v(w, (s) => {
                p() && s(X);
              });
            }
            var E = C(w, 2), Y = et(E, !0), Z = C(E, 2);
            {
              var $ = (s) => {
                xt(s, {
                  get width() {
                    return g().width;
                  },
                  get height() {
                    return g().height;
                  }
                });
              };
              v(Z, (s) => {
                g() && s($);
              });
            }
            f(() => st(Y, u())), l(U, b);
          };
          let Q = r(() => ({ type: c() }));
          vt(d, {
            tag: "li",
            class: "entry-status-message",
            subclass: "entry-status-message-content",
            get dataset() {
              return t(Q);
            },
            get beforeRenderChildren() {
              return _t;
            },
            get reduceMotion() {
              return t(q);
            },
            get springOptions() {
              return t(z);
            },
            children: N,
            $$slots: { default: !0 }
          });
        }
      }), f(() => pt(o, 1, ut(t(A)))), l(e, o);
    };
    v(J, (e) => {
      t(x).length && e(K);
    });
  }
  l(k, y), tt();
}
export {
  Qt as default
};
