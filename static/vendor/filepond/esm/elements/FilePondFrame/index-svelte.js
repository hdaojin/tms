/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as R } from "../../vendor/svelte/src/index-client.js";
import { user_effect as r } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as b, pop as k } from "../../vendor/svelte/src/internal/client/context.js";
import { get as c } from "../../vendor/svelte/src/internal/client/runtime.js";
import { child as _ } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as w, set as A } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { from_html as C, append as D } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { user_derived as F } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { if_block as M } from "../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { attach as O } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { prop as P } from "../../vendor/svelte/src/internal/client/reactivity/props.js";
import { Spring as x } from "../../vendor/svelte/src/motion/spring.js";
import { measurable as y } from "../attachments/measurable.js";
import { createAnimationModeObserver as S } from "../common/animationPreference-svelte.js";
import { rectFromBounds as j } from "../../utils/rect.js";
import "../components/ElementPane/index.js";
import B from "../components/ElementPane/index-svelte.js";
var E = C('<div class="root"><!></div>');
function $(s, o) {
  b(o, !0);
  let p = P(o, "animations", 3, "auto");
  const i = { updateRect: (t) => {
  }, computeRect: (t) => {
  } };
  function u(t) {
    i.updateRect = t;
  }
  function f(t) {
    i.computeRect = t;
  }
  let n = w(void 0);
  const m = S(), d = F(() => m.current);
  r(() => {
    m.setPreference(p());
  });
  const e = new x(void 0, { precision: 1 });
  r(() => {
    o.springDefaults && Object.assign(e, o.springDefaults);
  }), r(() => {
    e.set(c(n), { instant: !c(d) });
  });
  function l(t) {
    A(n, j(t));
  }
  r(() => {
    i.computeRect(c(n));
  }), r(() => {
    i.updateRect(e.current);
  }), R(() => {
    m.destroy();
  });
  var v = { setUpdateRectCallback: u, setComputeRectCallback: f }, a = E(), h = _(a);
  {
    var g = (t) => {
      B(t, {
        get width() {
          return e.current.width;
        },
        get height() {
          return e.current.height;
        }
      });
    };
    M(h, (t) => {
      e.current && t(g);
    });
  }
  return O(a, () => y({ onmeasure: l })), D(s, a), k(v);
}
export {
  $ as default
};
