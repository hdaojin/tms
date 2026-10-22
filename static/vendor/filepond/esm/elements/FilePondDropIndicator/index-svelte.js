/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as J } from "../../vendor/svelte/src/index-client.js";
import { user_effect as s, template_effect as K } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as L, pop as Q } from "../../vendor/svelte/src/internal/client/context.js";
import { get as t } from "../../vendor/svelte/src/internal/client/runtime.js";
import { child as x } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as g, set as l } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_derived as e } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as E, append as I } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as U } from "../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { attach as C } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_style as W } from "../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { bind_this as Z } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { spread_props as $ } from "../../vendor/svelte/src/internal/client/reactivity/props.js";
import { Spring as O } from "../../vendor/svelte/src/motion/spring.js";
import { rectPad as tt, rectContainsPoint as rt, rectFromBounds as et, rectCenter as ot } from "../../utils/rect.js";
import { vectorFromRect as nt, vectorElastify as it, vectorSubtract as M } from "../../utils/vector.js";
import { dropArea as st } from "../attachments/drop-area.js";
import { measurable as at } from "../attachments/measurable.js";
import { sizeFromRect as ct } from "../../utils/size.js";
import "../components/ElementPane/index.js";
import { dispatchCustomEvent as w } from "../../utils/dom.js";
import { createMotionStateObserver as dt, shouldReduceMotion as mt } from "../common/motionState-svelte.js";
import ft from "../components/ElementPane/index-svelte.js";
var ut = E("<div><!></div>"), pt = E('<div class="root"><!></div>');
function At(F, o) {
  L(o, !0);
  let v = g(void 0);
  function j(r) {
    if (!r) {
      l(m, void 0);
      return;
    }
    const p = nt(r), h = tt(t(d), Math.min(r.width, r.height));
    rt(h, p) && l(m, { ...r });
  }
  const _ = { width: 64, height: 64 }, z = 4, b = dt(), c = e(() => mt(b.current, o.reducedMotionPreference));
  let d = g(void 0), R = g(void 0), m = g(void 0);
  const f = e(() => !!(t(d) && t(m) && t(R))), D = e(() => t(f) ? M(t(R), t(d)) : void 0), S = e(() => t(f) ? M(ot(t(m)), t(d)) : void 0), P = e(() => {
    if (t(f))
      return t(c) ? t(S) : it(t(S), t(D), z);
  }), n = new O(void 0);
  s(() => {
    o.springOptions && Object.assign(n, o.springOptions);
  });
  let y = !1;
  s(() => {
    if (!t(P)) {
      y = !0;
      return;
    }
    n.set(t(P), { instant: t(c) || y }), y = !1;
  });
  const i = new O(1);
  s(() => {
    o.springOptions && Object.assign(i, o.springOptions);
  }), s(() => {
    if (!t(f)) {
      i.set(0, { instant: t(c) });
      return;
    }
    i.set(1);
  });
  const a = new O(_);
  s(() => {
    o.springOptions && Object.assign(a, o.springOptions);
  }), s(() => {
    if (i.current <= 0) {
      a.set(_, { instant: t(c) });
      return;
    }
    t(f) && a.set(ct(t(m)), { instant: t(c) });
  });
  const T = e(() => !!n.current && i.current > 0), k = e(() => !!n.current && i.current > 0.5);
  s(() => {
    t(k) ? w(t(v), "indicatorenter") : w(t(v), "indicatorleave");
  });
  function A(r) {
    l(d, et(r));
  }
  function B({ viewPosition: r }) {
    l(R, { x: r.x, y: r.y });
  }
  const H = e(() => n.current ? n.current.x - a.current.width * 0.5 : 0), N = e(() => n.current ? n.current.y - a.current.height * 0.5 : 0), V = e(() => `translate(${t(H)}px,${t(N)}px)`);
  J(() => {
    b.destroy();
  });
  var X = { setIndicatorRect: j }, u = pt(), Y = x(u);
  {
    var q = (r) => {
      var p = ut();
      let h;
      var G = x(p);
      ft(G, $(() => a.current)), K(() => h = W(p, "", h, {
        transform: t(V),
        opacity: i.current
      })), I(r, p);
    };
    U(Y, (r) => {
      t(T) && r(q);
    });
  }
  return Z(u, (r) => l(v, r), () => t(v)), C(u, () => at({ onmeasure: A })), C(u, () => st({ onitemdrag: B })), I(F, u), Q(X);
}
export {
  At as default
};
