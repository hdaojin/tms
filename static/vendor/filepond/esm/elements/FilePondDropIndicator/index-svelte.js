/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as K } from "../../vendor/svelte/src/index-client.js";
import { user_effect as i, template_effect as L } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as Q, pop as U } from "../../vendor/svelte/src/internal/client/context.js";
import { get as t } from "../../vendor/svelte/src/internal/client/runtime.js";
import { child as I } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as g, set as p } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { from_html as A, append as S } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { user_derived as e } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { if_block as W } from "../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { attach as C } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_style as Z } from "../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { bind_this as $ } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as tt, spread_props as rt } from "../../vendor/svelte/src/internal/client/reactivity/props.js";
import { Spring as b } from "../../vendor/svelte/src/motion/spring.js";
import { rectPad as et, rectContainsPoint as ot, rectFromBounds as nt, rectCenter as it } from "../../utils/rect.js";
import { vectorFromRect as at, vectorElastify as st, vectorSubtract as O } from "../../utils/vector.js";
import { dropArea as ct } from "../attachments/drop-area.js";
import { measurable as dt } from "../attachments/measurable.js";
import { createAnimationModeObserver as mt } from "../common/animationPreference-svelte.js";
import { sizeFromRect as ft } from "../../utils/size.js";
import "../components/ElementPane/index.js";
import { dispatchCustomEvent as w } from "../../utils/dom.js";
import ut from "../components/ElementPane/index-svelte.js";
var lt = A("<div><!></div>"), pt = A('<div class="root"><!></div>');
function Bt(E, o) {
  Q(o, !0);
  let F = tt(o, "animations", 3, "auto"), v = g(void 0);
  function M(r) {
    if (!r) {
      p(m, void 0);
      return;
    }
    const l = at(r), h = et(t(d), Math.min(r.width, r.height));
    ot(h, l) && p(m, { ...r });
  }
  const D = { width: 64, height: 64 }, j = 4, y = mt(), c = e(() => y.current);
  i(() => {
    y.setPreference(F());
  });
  let d = g(void 0), R = g(void 0), m = g(void 0);
  const f = e(() => !!(t(d) && t(m) && t(R))), z = e(() => t(f) ? O(t(R), t(d)) : void 0), P = e(() => t(f) ? O(it(t(m)), t(d)) : void 0), x = e(() => {
    if (t(f))
      return t(c) ? st(t(P), t(z), j) : t(P);
  }), n = new b(void 0);
  i(() => {
    o.springDefaults && Object.assign(n, o.springDefaults);
  });
  let _ = !1;
  i(() => {
    if (!t(x)) {
      _ = !0;
      return;
    }
    n.set(t(x), { instant: !t(c) || _ }), _ = !1;
  });
  const a = new b(1);
  i(() => {
    o.springDefaults && Object.assign(a, o.springDefaults);
  }), i(() => {
    if (!t(f)) {
      a.set(0, { instant: !t(c) });
      return;
    }
    a.set(1);
  });
  const s = new b(D);
  i(() => {
    o.springDefaults && Object.assign(s, o.springDefaults);
  }), i(() => {
    if (a.current <= 0) {
      s.set(D, { instant: !t(c) });
      return;
    }
    t(f) && s.set(ft(t(m)), { instant: !t(c) });
  });
  const T = e(() => !!n.current && a.current > 0), k = e(() => !!n.current && a.current > 0.5);
  i(() => {
    t(k) ? w(t(v), "indicatorenter") : w(t(v), "indicatorleave");
  });
  function B(r) {
    p(d, nt(r));
  }
  function H({ viewPosition: r }) {
    p(R, { x: r.x, y: r.y });
  }
  const N = e(() => n.current ? n.current.x - s.current.width * 0.5 : 0), V = e(() => n.current ? n.current.y - s.current.height * 0.5 : 0), X = e(() => `translate(${t(N)}px,${t(V)}px)`);
  K(() => {
    y.destroy();
  });
  var Y = { setIndicatorRect: M }, u = pt(), q = I(u);
  {
    var G = (r) => {
      var l = lt();
      let h;
      var J = I(l);
      ut(J, rt(() => s.current)), L(() => h = Z(l, "", h, {
        transform: t(X),
        opacity: a.current
      })), S(r, l);
    };
    W(q, (r) => {
      t(T) && r(G);
    });
  }
  return $(u, (r) => p(v, r), () => t(v)), C(u, () => dt({ onmeasure: B })), C(u, () => ct({ onitemdrag: H })), S(E, u), U(Y);
}
export {
  Bt as default
};
