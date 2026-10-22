/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as g } from "../../vendor/svelte/src/index-client.js";
import { user_effect as n } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as b, pop as M } from "../../vendor/svelte/src/internal/client/context.js";
import { get as u } from "../../vendor/svelte/src/internal/client/runtime.js";
import { child as O } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as k, set as S } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_derived as _ } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as w, append as C } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as F } from "../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { attach as P } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { Spring as x } from "../../vendor/svelte/src/motion/spring.js";
import { measurable as y } from "../attachments/measurable.js";
import { rectFromBounds as j } from "../../utils/rect.js";
import "../components/ElementPane/index.js";
import { createMotionStateObserver as B, shouldReduceMotion as D } from "../common/motionState-svelte.js";
import E from "../components/ElementPane/index-svelte.js";
var U = w('<div class="root"><!></div>');
function Z(p, r) {
  b(r, !0);
  const o = { updateRect: (t) => {
  }, computeRect: (t) => {
  } };
  function s(t) {
    o.updateRect = t;
  }
  function f(t) {
    o.computeRect = t;
  }
  let c = k(void 0);
  const m = B(), d = _(() => D(m.current, r.reducedMotionPreference)), e = new x(void 0, { precision: 1 });
  n(() => {
    r.springOptions && Object.assign(e, r.springOptions);
  }), n(() => {
    e.set(u(c), { instant: u(d) });
  });
  function l(t) {
    const a = j(t);
    o.computeRect(a), S(c, a);
  }
  n(() => {
    o.updateRect(e.current);
  }), g(() => {
    m.destroy();
  });
  var h = { setUpdateRectCallback: s, setComputeRectCallback: f }, i = U(), v = O(i);
  {
    var R = (t) => {
      E(t, {
        get width() {
          return e.current.width;
        },
        get height() {
          return e.current.height;
        }
      });
    };
    F(v, (t) => {
      e.current && t(R);
    });
  }
  return P(i, () => y({ onmeasure: l })), C(p, i), M(h);
}
export {
  Z as default
};
