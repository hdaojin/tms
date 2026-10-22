/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as m, untrack as E } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { push as F, pop as B } from "../../../vendor/svelte/src/internal/client/context.js";
import { first_child as h } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { user_derived as C } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { comment as N, append as y } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { await_block as J } from "../../../vendor/svelte/src/internal/client/dom/blocks/await.js";
import { each as L } from "../../../vendor/svelte/src/internal/client/dom/blocks/each.js";
import { prop as u } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { isSwitchNode as R, isTemplateNode as P } from "../../common/nodeTree.js";
import { isString as a, isFunction as _ } from "../../../utils/test.js";
import { passthrough as W } from "../../../utils/placeholder.js";
import { arrayWrap as f, arrayRemoveFalsy as Y } from "../../../utils/array.js";
import q from "./Node-svelte.js";
import { yieldScheduler as z } from "../../../common/yield.js";
import { EMPTY_OBJECT as A } from "../../../utils/object.js";
function fe(b, o) {
  F(o, !0);
  let d = u(o, "context", 19, () => ({})), s = u(o, "routes", 7), M = u(o, "beforeRenderNode", 3, W), O = u(o, "reduceMotion", 3, !1);
  const S = {
    // svelte-ignore state_referenced_locally
    refs: {},
    get routes() {
      return s();
    }
  };
  function k(t, e, r) {
    return _(t.if.test) && t.if.test(e, r) ? f(t.if.then) : t.elseif && _(t.elseif.test) && t.elseif.test(e, r) ? f(t.elseif.then) : P(t.else) ? f(t.else) : [];
  }
  function p(t, e, r) {
    const n = [];
    for (const i of k(t, e, r))
      R(i) ? n.push(...p(i, e, r)) : n.push(i);
    return n;
  }
  function v(t, e) {
    return a(t) ? e : `${t.key ?? e}`;
  }
  const w = C(() => {
    const t = [];
    for (const e of f(o.nodes))
      e && (R(e) ? t.push(...p(e, o.data || A, d())) : t.push(e));
    return E(() => {
      for (const e of t)
        a(e) || !e.routes || (s() || s({}), Object.assign(s(), Object.entries(e.routes).reduce(
          (r, [n, i]) => {
            const [c, K] = n.split(":"), [l, j] = i.split(".");
            return r[l] = {}, r[c] = {
              [`on${K}`]: (...x) => {
                r[l].getRoot()[j]?.(...x);
              }
            }, r;
          },
          {}
        )));
    }), Y(t).map((e, r) => a(e) ? { key: `${r}`, data: o.data, children: e } : e);
  });
  var g = N(), T = h(g);
  L(T, 19, () => m(w), (t, e) => v(t, e), (t, e, r) => {
    var n = N(), i = h(n);
    J(i, z, null, (c) => {
      q(c, {
        get node() {
          return m(e);
        },
        get index() {
          return m(r);
        },
        get scope() {
          return S;
        },
        get data() {
          return o.data;
        },
        get context() {
          return d();
        },
        get beforeRenderNode() {
          return M();
        },
        get reduceMotion() {
          return O();
        },
        get springOptions() {
          return o.springOptions;
        },
        get propResourceMap() {
          return o.propResourceMap;
        },
        get resources() {
          return o.resources;
        }
      });
    }), y(t, n);
  }), y(b, g), B();
}
export {
  fe as default
};
