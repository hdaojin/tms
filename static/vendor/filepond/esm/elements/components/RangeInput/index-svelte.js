/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as t } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { push as Rt, pop as Ct } from "../../../vendor/svelte/src/internal/client/context.js";
import { child as g, sibling as h } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as s, set as a } from "../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_effect as K, template_effect as Q } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as i } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { delegate as Mt, delegated as R, event as Ot } from "../../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { from_html as Ht, append as Ft } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { snippet as St } from "../../../vendor/svelte/src/internal/client/dom/blocks/snippet.js";
import { attach as C } from "../../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_custom_element_data as It, set_attribute as S, set_value as Tt } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_class as Wt } from "../../../vendor/svelte/src/internal/client/dom/elements/class.js";
import { set_style as I } from "../../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { bind_this as Y } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as o } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { clsx as Xt } from "../../../vendor/svelte/src/internal/shared/attributes.js";
import { Spring as At } from "../../../vendor/svelte/src/motion/spring.js";
import { resizable as M } from "../../attachments/resizable.js";
import { getStylePropertyAsNumber as Bt } from "../../../utils/dom.js";
import { clamp as Z } from "../../../utils/math.js";
import { noop as $ } from "../../../utils/placeholder.js";
import { isNumber as Dt } from "../../../utils/test.js";
import "../ElementPane/index.js";
import T from "../ElementPane/index-svelte.js";
var Lt = Ht('<range-input><input type="range"/> <div class="range-input-bar range-input-track"><!></div> <div class="range-input-bar range-input-hover"><!></div> <div class="range-input-bar range-input-progress"><!></div> <div class="range-input-knob"></div> <span class="range-input-title"><!></span></range-input>', 2);
function de(tt, r) {
  Rt(r, !0);
  let et = o(r, "class", 3, void 0), rt = o(r, "part", 3, void 0), m = o(r, "min", 3, 0), _ = o(r, "max", 3, 1), W = o(r, "value", 3, 0), nt = o(r, "step", 3, 0.1), X = o(r, "oninput", 3, $), it = o(r, "onhover", 3, $), A = o(r, "precision", 3, 2), ot = o(r, "reduceMotion", 3, !0);
  const b = new At(void 0);
  K(() => {
    r.springOptions && Object.assign(b, r.springOptions);
  });
  let c = s(void 0), k = s(void 0);
  const B = i(() => t(k) && getComputedStyle(t(k))), at = i(() => t(B) && Bt(t(B), "border-radius") || 0);
  let P = s(null), d = s(null), l = s(null), p = s(void 0);
  const st = i(() => Dt(b.current) ? b.current : null), O = i(() => Math.min(t(at), t(p) * 0.5)), w = i(() => Math.max(0, t(st) - t(O) * 2));
  function lt(e) {
    a(d, e.width), b.set(t(d), { instant: ot() });
  }
  function ut(e) {
    a(P, e.width);
  }
  function mt(e) {
    a(p, e.height);
  }
  let x = !1;
  function dt() {
    x = !0;
  }
  function pt() {
    x = !1;
  }
  function ft(e) {
    a(l, e.offsetX), x && (t(c).value = `${m() + t(l) / t(P) * (_() - m())}`, X()(parseFloat(t(c).value)));
  }
  function ct() {
    a(l, null), x = !1;
  }
  const vt = i(() => t(l) !== null);
  let D = s(0);
  function gt(e) {
    a(D, e);
  }
  function ht(e, u, z, G) {
    const J = u - z;
    return Z((e - J / 2 - G) / (u - J - G * 2));
  }
  const v = i(() => t(vt) && t(P) && t(d) && t(l) !== null ? ht(t(l), t(P), t(d), t(O)) : t(D));
  K(() => {
    gt(t(v)), it()?.(t(v));
  });
  let H = s(void 0);
  function _t(e) {
    a(H, e.width);
  }
  function bt(e, u, z) {
    return Z(e * u - z * 0.5, 0, u - z);
  }
  const kt = i(() => t(d) && t(H) ? bt(t(v), t(d), t(H)) : 0), L = i(() => W() / (_() - m()));
  function Pt() {
    X()(parseFloat(t(c).value));
  }
  var f = Lt();
  Q(() => It(f, "part", rt()));
  let N;
  var n = g(f);
  Y(n, (e) => a(c, e), () => t(c)), C(n, () => M({ onresize: ut }));
  var y = h(n, 2), wt = g(y);
  T(wt, {
    get width() {
      return t(w);
    },
    get height() {
      return t(p);
    }
  }), Y(y, (e) => a(k, e), () => t(k)), C(y, () => M({ onresize: mt }));
  var j = h(y, 2), xt = g(j);
  {
    let e = i(() => t(w) * t(v));
    T(xt, {
      get width() {
        return t(e);
      },
      get height() {
        return t(p);
      }
    });
  }
  var E = h(j, 2), yt = g(E);
  {
    let e = i(() => Math.max(t(w) * t(L), t(p)));
    T(yt, {
      get width() {
        return t(e);
      },
      get height() {
        return t(p);
      }
    });
  }
  var U = h(E, 2);
  let V;
  var F = h(U, 2);
  let q;
  var zt = g(F);
  St(zt, () => r.children, () => ({ hoverValue: m() + t(v) * (_() - m()) })), C(F, () => M({ onresize: _t })), C(f, () => M({ onresize: lt })), Q(
    (e, u) => {
      Wt(f, 1, Xt(et())), N = I(f, "", N, { "--track-border-radius": t(O) }), S(n, "min", m()), S(n, "max", _()), Tt(n, W()), S(n, "step", e), V = I(U, "", V, { "--offset": u }), q = I(F, "", q, {
        "--title-x": `${t(kt)}px`,
        "--title-reveal": t(l) !== null ? 1 : 0
      });
    },
    [
      () => nt().toFixed(A()),
      () => (t(w) * t(L)).toFixed(A())
    ]
  ), R("input", n, Pt), R("pointerdown", n, dt), R("pointerup", n, pt), R("pointermove", n, ft), Ot("pointerleave", n, ct), Ft(tt, f), Ct();
}
Mt(["input", "pointerdown", "pointerup", "pointermove"]);
export {
  de as default
};
