/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as t } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { push as rt, pop as ot } from "../../../../vendor/svelte/src/internal/client/context.js";
import { child as dt } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { set as C, state as P } from "../../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_effect as R, template_effect as mt } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as i } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as ct, append as lt } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { snippet as st } from "../../../../vendor/svelte/src/internal/client/dom/blocks/snippet.js";
import { attach as ut } from "../../../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_style as ft } from "../../../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { bind_window_size as G } from "../../../../vendor/svelte/src/internal/client/dom/elements/bindings/window.js";
import { prop as r } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { rectFromBounds as ht, rectScale as pt, rectCreate as gt } from "../../../../utils/rect.js";
import { Spring as k } from "../../../../vendor/svelte/src/motion/spring.js";
import { measurable as wt } from "../../../attachments/measurable.js";
import { getAppContext as xt } from "../../contexts/appContext.js";
import { getSpringElementTreeContext as _t } from "../../contexts/springElementTreeContext.js";
var Mt = ct("<media-pane><!></media-pane>", 2);
function Bt(J, a) {
  rt(a, !0);
  let m = r(a, "mediaWidth", 7, void 0), c = r(a, "mediaHeight", 7, void 0), w = r(a, "mediaVisible", 7, void 0), x = r(a, "mediaLoading", 7, !0), _ = r(a, "mediaObjectFit", 3, "cover"), I = r(a, "mediaInitialScalar", 3, 1), A = r(a, "mediaInitialOpacity", 3, 1), M = r(a, "mediaAnimateIn", 7, !0), v = r(a, "overflowAmount", 3, 10), F = r(a, "enableParallax", 3, !0);
  const H = { stiffness: 0.1, damping: 0.8, precision: 0.01 }, T = new k(A(), H), W = new k(I(), H), j = i(xt), L = i(() => t(j).springOptions), K = i(() => t(j).reduceMotion), N = _t(), y = i(() => N.currentScale);
  let h = P(null);
  const n = new k(void 0);
  R(() => {
    t(L) && Object.assign(n, t(L));
  });
  const O = i(() => ({ instant: t(K) }));
  let B = P(void 0), V = P(void 0);
  const d = i(() => !x() && !!(m() && c())), b = i(() => t(d) ? m() / c() : null), l = i(() => n.current ? n.current.width : null), s = i(() => n.current ? n.current.height : null), Q = i(() => t(d) ? t(l) * 0.5 - m() * 0.5 : 0), Z = i(() => t(d) ? t(s) * 0.5 - c() * 0.5 : 0);
  function X(e) {
    return Math[e === "cover" ? "max" : "min"];
  }
  const Y = i(() => t(d) ? X(_())(t(l) / m(), t(s) / c()) : null), $ = i(() => t(d) ? X(_())((t(l) + v() * 2) / m(), (t(s) + v() * 2) / c()) - t(Y) : null), D = i(() => t(d) && F() && n.current ? (n.current.x + n.current.width) / (t(B) + n.current.width) : null), E = i(() => t(d) && F() && n.current ? (n.current.y + n.current.height) / (t(V) + n.current.height) : null);
  R(() => {
    T.set(w() ? 1 : A(), {
      instant: M() ? t(O).instant : !0
    });
  }), R(() => {
    W.set(w() ? 1 : I(), {
      instant: M() ? t(O).instant : !0
    });
  });
  function tt(e, o, z) {
    let S = e, f = e / z;
    return f > o && (f = o, S = f * z), {
      x: (e - S) / 2,
      y: (o - f) / 2,
      width: S,
      height: f
    };
  }
  const U = i(() => t(h) && n.current ? {
    width: t(h)?.width - n.current?.width * t(y),
    height: t(h)?.height - n.current?.height * t(y)
  } : { width: 0, height: 0 }), u = i(() => t(d) ? _() === "contain" ? tt(t(l), t(s), t(b)) : gt(0, 0, t(l), t(s)) : null), p = i(() => t(u) ? {
    t: t(u).y,
    r: t(u).x + t(U).width,
    b: t(u).y + t(U).height,
    l: t(u).x
  } : null), et = i(() => t(b) ? t(b).toFixed(3) : "auto");
  function it(e) {
    const o = ht(e);
    !o.width || !o.height || nt(o);
  }
  function nt(e) {
    C(h, { ...e }), n.set(pt(e, 1 / t(y)), t(O));
  }
  var g = Mt();
  let q;
  var at = dt(g);
  st(at, () => a.children, () => ({
    onInitMedia: () => {
      x(!0);
    },
    onLoadMedia: (e) => {
      m(e.width), c(e.height), x(!1);
    },
    onRenderMedia: (e) => {
      const { instant: o = !1 } = e || {};
      M(!o), w(!0);
    }
  })), ut(g, () => wt({ onmeasure: it })), mt(() => q = ft(g, "", q, {
    "--_aspect-ratio": t(et),
    "--_x": `${t(Q)}px`,
    "--_y": `${t(Z)}px`,
    "--_scale": t(Y),
    "--_opacity": T.current,
    "--_scalar": W.current,
    "--_pan-x": t(D) === null ? 0 : -1 + t(D) * 2,
    "--_pan-y": t(E) === null ? 0 : -1 + t(E) * 2,
    "--_overflow-amount": `${v()}px`,
    "--_overflow-scale": t($),
    "--_mask-top": `${t(p)?.t ?? 0}px`,
    "--_mask-right": `${t(p)?.r ?? 0}px`,
    "--_mask-bottom": `${t(p)?.b ?? 0}px`,
    "--_mask-left": `${t(p)?.l ?? 0}px`
  })), G("innerWidth", (e) => C(B, e)), G("innerHeight", (e) => C(V, e)), lt(J, g), ot();
}
export {
  Bt as default
};
