/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as Se } from "../../../vendor/svelte/src/index-client.js";
import { user_effect as s } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { pop as Ce, push as Re } from "../../../vendor/svelte/src/internal/client/context.js";
import { get as t, untrack as bt } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { first_child as W } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as f, set as l } from "../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_derived as i } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { comment as B, append as I } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as ve } from "../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { snippet as xe } from "../../../vendor/svelte/src/internal/client/dom/blocks/snippet.js";
import { element as Ot } from "../../../vendor/svelte/src/internal/client/dom/blocks/svelte-element.js";
import { attach as Et } from "../../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { attribute_effect as wt, STYLE as Ft } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { bind_this as be } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as r } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { vectorCreate as N, vectorEqual as Y, vectorFromRect as Oe, vectorInvert as Ee } from "../../../utils/vector.js";
import { sizeEqual as we, sizeFromRect as rt } from "../../../utils/size.js";
import { rectFromBounds as Pt, rectScale as Tt, rectCreate as _t, rectEqual as Fe, rectCenter as Pe } from "../../../utils/rect.js";
import { isNumber as E, isFunction as Te } from "../../../utils/test.js";
import { Spring as G } from "../../../vendor/svelte/src/motion/spring.js";
import { updateDataset as _e, updateStyles as ze } from "../../../utils/dom.js";
import { measurable as zt } from "../../attachments/measurable.js";
import { hasSpringElementTreeContext as De, setSpringElementTreeContext as Dt, getSpringElementTreeContext as Mt } from "../../FilePondEntryList/contexts/springElementTreeContext.js";
import { noop as it } from "../../../utils/placeholder.js";
import { gate as ot } from "../../common/store-svelte.js";
import { roundPrecision as H } from "../../../utils/math.js";
function sn(At, n) {
  Re(n, !0);
  let st = r(n, "reduceMotion", 3, !0), z = r(n, "springOptions", 3, void 0), jt = r(n, "id", 3, void 0), kt = r(n, "tag", 3, "div"), qt = r(n, "part", 3, void 0), Vt = r(n, "class", 3, void 0), Lt = r(n, "attrs", 3, void 0), Ut = r(n, "subtag", 3, "div"), Wt = r(n, "subclass", 3, void 0), Bt = r(n, "subattrs", 3, void 0), ut = r(n, "dataset", 3, void 0), at = r(n, "styles", 3, void 0), It = r(n, "inert", 3, null), Nt = r(n, "scaleSpringOptions", 3, void 0), D = r(n, "scaleFrom", 3, void 0), v = r(n, "scale", 3, void 0), Yt = r(n, "opacitySpringOptions", 3, void 0), F = r(n, "opacityFrom", 3, void 0), x = r(n, "opacity", 3, void 0), Gt = r(n, "translation", 19, N), P = r(n, "translationFrom", 3, void 0), Ht = r(n, "translationSpringOptions", 3, void 0), m = r(n, "shouldRenderChildren", 3, !0), Jt = r(n, "onroot", 3, void 0), ct = r(n, "onelementmeasure", 3, void 0), lt = r(n, "onmeasure", 3, void 0), Kt = r(n, "onmeasureabsoluterect", 3, void 0), Qt = r(n, "onspringcomplete", 3, it), Xt = r(n, "beforeRenderChildren", 3, void 0), dt = !1;
  const d = new G(void 0), p = new G(v() || 1), g = new G(x() || 1), Zt = ot((e, u) => e !== u, () => Ht()), $t = ot((e, u) => e !== u, () => Nt()), te = ot((e, u) => e !== u, () => Yt());
  s(() => {
    Object.assign(d, {
      ...z(),
      ...Zt.current,
      precision: 1e-4
    });
  }), s(() => {
    Object.assign(p, {
      ...z(),
      ...$t.current,
      precision: 1e-4
    });
  }), s(() => {
    Object.assign(g, {
      ...z(),
      ...te.current,
      precision: 0.01
    });
  });
  let ft = f(!0), h = f(null);
  s(() => {
    t(h) && Kt()?.(t(h));
  });
  let y = f(null), mt = f(null), a = f(void 0);
  const S = i(() => t(a) ? Oe(t(a)) : void 0), C = i(() => t(a) ? rt(t(a)) : void 0), R = new G(void 0);
  s(() => {
    Object.assign(R, z());
  });
  let J;
  s(() => {
    t(C) && (t(C) && J && we(J, t(C)) || (R.set(t(C), { instant: st() }), J = { ...t(C) }));
  });
  let K, Q;
  const T = i(() => {
    if (t(S))
      return K && t(S) && Y(K, t(S)) || (K = { ...t(S) }, Q = Ee(t(S))), Q;
  });
  let M = f(!1);
  const pt = i(Gt);
  function ee(e) {
    e.parent && (e.parent.childSpringReadyCount--, e.parent.childSpringCount--);
  }
  let gt = f(0), ht = f(0);
  const yt = {
    get isReady() {
      return t(M);
    },
    get currentRect() {
      return t(y);
    },
    get currentRectCenter() {
      return t(mt);
    },
    get targetSize() {
      return t(C);
    },
    get currentSize() {
      return R.current;
    },
    get currentScale() {
      return p.current * (c.parent ? c.parent.currentScale : 1);
    },
    get childSpringCount() {
      return t(gt);
    },
    set childSpringCount(e) {
      l(gt, e, !0);
    },
    get childSpringReadyCount() {
      return t(ht);
    },
    set childSpringReadyCount(e) {
      l(ht, e, !0);
    },
    parent: null
  };
  if (!De())
    Dt(yt);
  else {
    const e = Mt(), u = Object.assign(yt, { parent: e });
    e.childSpringCount++, Dt(u);
  }
  const c = Mt(), X = i(() => ({ instant: st() }));
  function A() {
    dt || Qt()({
      opacity: g.current,
      scale: p.current
    });
  }
  let j;
  const w = i(() => {
    if (!t(S))
      return;
    const e = N(t(S).x + t(pt).x, t(S).y + t(pt).y);
    return j && Y(j, e) ? j : (j = e, e);
  });
  let Z;
  s(() => {
    if (t(w)) {
      if (!m()) {
        d.set(t(w), { instant: !0 });
        return;
      }
      P() && (!Z || !Y(P(), Z)) && (d.set(N(t(w).x + P().x, t(w).y + P().y), { instant: !0 }), Z = { ...P() }), !(d.current && Y(d.current, t(w))) && d.set(t(w), {
        instant: t(X).instant || !t(ft)
      });
    }
  }), E(v()) && v() === p.current && v() !== 1 && A();
  let St;
  s(() => {
    m() && (E(D()) && D() !== St && (p.set(D(), { instant: !0 }), St = D()), !(!E(v()) || p.target === v()) && p.set(v(), t(X)).then(() => {
      bt(() => {
        A();
      });
    }).catch(it));
  }), E(x()) && x() === g.current && x() !== 1 && A();
  let Ct;
  s(() => {
    m() && (E(F()) && F() !== Ct && (g.set(F(), { instant: !0 }), Ct = F()), !(!E(x()) || g.target === x()) && g.set(x(), t(X)).then(() => {
      bt(() => {
        A();
      });
    }).catch(it));
  });
  const Rt = i(() => {
    const e = c.parent?.currentRect;
    return e || _t();
  }), ne = i(() => c.childSpringCount > 0), re = i(() => !!t(y) || !t(ne));
  s(() => {
    t(re) && (t(M) || (l(M, !0), c.parent && c.parent.childSpringReadyCount++));
  });
  let $ = f(!1);
  s(() => {
    t($) || l($, c.childSpringCount === c.childSpringReadyCount);
  });
  let vt = 1;
  s(() => {
    vt = c.parent ? c.parent.currentScale : 1;
  });
  function ie(e) {
    const u = Pt(e);
    if (u.width <= 0 || u.height <= 0)
      return;
    t(M) && lt() && lt()(e);
    const q = c.parent?.currentRectCenter || N();
    l(h, Tt(u, 1 / vt, q));
    const o = _t(t(h).x - t(Rt).x, t(h).y - t(Rt).y, t(h).width, t(h).height);
    if (o.x = H(o.x, 5), o.y = H(o.y, 5), o.width = H(o.width, 5), o.height = H(o.height, 5), t(a)) {
      const tt = t(a).width, O = o.width, V = Math.abs(tt - O), et = t(a).x + t(a).width, L = o.x + o.width, nt = Math.abs(et - L), U = Math.abs(t(a).y - o.y);
      l(ft, !(nt < 1e-4 && V > 1e-4 && U < 1e-4));
    }
    t(a) && Fe(t(a), o) || (l(a, { ...o }), Te(ct()) && ct()({ ...t(a) }));
  }
  function oe(e) {
    const u = Pt(e);
    l(y, Tt(u, 1 / c.currentScale)), l(mt, Pe(t(y)));
  }
  const se = i(() => !!t(y)), ue = i(() => !m() || !t(T) || !d.current || !R.current ? !1 : (
    // not yet at target position
    d.current.x + t(T).x !== 0 || d.current.y + t(T).y !== 0 || // not yet at taget size
    R.current.width !== t(C).width || R.current.height !== t(C).height || // not yet at target scale
    p.current !== 1
  )), _ = i(() => t(ue)), ae = i(() => t(_) ? "relative" : null), ce = i(() => t(_) ? `${t(T).x}px` : null), le = i(() => t(_) ? `${t(T).y}px` : null), de = i(() => t(_) ? "center" : null), fe = i(() => E(g.current) && g.current < 1 ? g.current : null), me = i(() => t(_) ? `translate3d(${d.current?.x}px,${d.current?.y}px,0)scale(${p.current})` : null);
  let k = f(void 0);
  s(() => {
    if (!m() || !t(h)) {
      t(y) && l(k, rt(t(y)));
      return;
    }
    l(k, rt(t(h)));
  });
  let b = f(void 0);
  s(() => {
    !t(b) || !m() || !ut() || _e(t(b), ut());
  }), s(() => {
    !t(b) || !m() || !at() || ze(t(b), at());
  }), s(() => {
    Jt()?.(t(b));
  });
  const pe = i(() => t(y) !== null ? {
    // @ts-ignore
    ...t(y),
    ...R.current
  } : { ...R.current }), ge = i(() => Xt()?.({ visualRect: t(pe) }));
  Se(() => {
    dt = !0, ee(c);
  });
  var xt = B(), he = W(xt);
  Ot(he, kt, !1, (e, u) => {
    be(e, (O) => l(b, O), () => t(b)), Et(e, () => t($) && zt({ onmeasure: ie })), wt(e, () => ({
      id: jt(),
      class: Vt(),
      part: qt(),
      ...Lt(),
      inert: It(),
      [Ft]: {
        contain: "layout",
        height: m() ? void 0 : `${t(k)?.height}px`,
        opacity: m() ? void 0 : F()
      }
    }));
    var q = B(), o = W(q);
    {
      var tt = (O) => {
        var V = B(), et = W(V);
        Ot(et, Ut, !1, (L, nt) => {
          Et(L, () => zt({ onmeasure: oe })), wt(L, () => ({
            class: Wt(),
            ...Bt(),
            [Ft]: {
              position: t(ae),
              left: t(ce),
              top: t(le),
              transformOrigin: t(de),
              transform: t(me),
              opacity: t(fe),
              height: "100%",
              "min-height": t(se) ? void 0 : `${t(k)?.height}px`,
              "max-height": "inherit"
            }
          }));
          var U = B(), ye = W(U);
          xe(ye, () => n.children, () => t(ge)), I(nt, U);
        }), I(O, V);
      };
      ve(o, (O) => {
        m() && O(tt);
      });
    }
    I(u, q);
  }), I(At, xt), Ce();
}
export {
  sn as default
};
