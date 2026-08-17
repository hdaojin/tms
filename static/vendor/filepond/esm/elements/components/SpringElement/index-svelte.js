/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as Oe } from "../../../vendor/svelte/src/index-client.js";
import { user_effect as s } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { pop as Ee, push as Pe } from "../../../vendor/svelte/src/internal/client/context.js";
import { get as t, untrack as Ft } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { first_child as z } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { set as d, state as p } from "../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { comment as A, append as D } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { user_derived as i } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { if_block as _t } from "../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { snippet as we } from "../../../vendor/svelte/src/internal/client/dom/blocks/snippet.js";
import { element as Tt } from "../../../vendor/svelte/src/internal/client/dom/blocks/svelte-element.js";
import { attach as zt } from "../../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { attribute_effect as At, STYLE as Dt } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { bind_this as Fe } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as r } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { vectorCreate as B, vectorEqual as I, vectorFromRect as _e, vectorInvert as Te } from "../../../utils/vector.js";
import { sizeFromRect as at, sizeEqual as ze } from "../../../utils/size.js";
import { rectEqual as Mt, rectCreate as jt, rectFromBounds as kt, rectScale as qt, rectCenter as Ae } from "../../../utils/rect.js";
import { isNumber as E, isFunction as De } from "../../../utils/test.js";
import { Spring as N } from "../../../vendor/svelte/src/motion/spring.js";
import { updateDataset as Me, updateStyles as je } from "../../../utils/dom.js";
import { measurable as Lt } from "../../attachments/measurable.js";
import { hasSpringElementTreeContext as ke, setSpringElementTreeContext as Ut, getSpringElementTreeContext as Wt } from "../../FilePondEntryList/contexts/springElementTreeContext.js";
import { noop as st } from "../../../utils/placeholder.js";
import { gate as ut } from "../../common/store-svelte.js";
import { roundPrecision as V } from "../../../utils/math.js";
function ln(Bt, n) {
  Pe(n, !0);
  let ct = r(n, "enableAnimations", 3, !0), M = r(n, "springDefaults", 3, void 0), It = r(n, "tag", 3, "div"), Nt = r(n, "part", 3, void 0), Vt = r(n, "class", 3, void 0), Yt = r(n, "attrs", 3, void 0), Gt = r(n, "subtag", 3, "div"), Ht = r(n, "subclass", 3, void 0), Jt = r(n, "subattrs", 3, void 0), lt = r(n, "dataset", 3, void 0), dt = r(n, "styles", 3, void 0), Kt = r(n, "inert", 3, null), Qt = r(n, "scaleSpringOptions", 3, void 0), j = r(n, "scaleFrom", 3, void 0), C = r(n, "scale", 3, void 0), Xt = r(n, "opacitySpringOptions", 3, void 0), w = r(n, "opacityFrom", 3, void 0), x = r(n, "opacity", 3, void 0), Zt = r(n, "translation", 19, B), F = r(n, "translationFrom", 3, void 0), $t = r(n, "translationSpringOptions", 3, void 0), te = r(n, "onroot", 3, void 0), ft = r(n, "onelementmeasure", 3, void 0), mt = r(n, "onmeasure", 3, void 0), ee = r(n, "onspringcomplete", 3, st), ne = r(n, "onchangerendercontent", 3, void 0), pt = r(n, "shouldRenderContent", 3, void 0), gt = !1;
  const f = new N(void 0), g = new N(C() || 1), h = new N(x() || 1), re = ut((e, a) => e !== a, () => $t()), ie = ut((e, a) => e !== a, () => Qt()), oe = ut((e, a) => e !== a, () => Xt());
  s(() => {
    Object.assign(f, {
      ...M(),
      ...re.current,
      precision: 1e-4
    });
  }), s(() => {
    Object.assign(g, {
      ...M(),
      ...ie.current,
      precision: 1e-4
    });
  }), s(() => {
    Object.assign(h, {
      ...M(),
      ...oe.current,
      precision: 0.01
    });
  });
  let ht = p(!0), l = p(null), Y = null, G = !0;
  const m = i(() => pt() ? (t(l) && Y && Mt(t(l), Y) || (Y = { ...t(l) }, G = !!(t(l) && pt()(t(l)))), G) : !0);
  s(() => {
    ne()?.(t(m));
  });
  let y = p(null), yt = p(null), u = p(void 0);
  const v = i(() => t(u) ? _e(t(u)) : void 0), R = i(() => t(u) ? at(t(u)) : void 0), S = new N(void 0);
  s(() => {
    Object.assign(S, M());
  });
  let H;
  s(() => {
    t(R) && (t(R) && H && ze(H, t(R)) || (S.set(t(R), { instant: !ct() }), H = { ...t(R) }));
  });
  let J, K;
  const _ = i(() => {
    if (t(v))
      return J && t(v) && I(J, t(v)) || (J = { ...t(v) }, K = Te(t(v))), K;
  });
  let k = p(!1);
  const St = i(Zt);
  function ae(e) {
    e.parent && (e.parent.childSpringReadyCount--, e.parent.childSpringCount--);
  }
  let vt = p(0), Rt = p(0);
  const Ct = {
    get isReady() {
      return t(k);
    },
    get currentRect() {
      return t(y);
    },
    get currentRectCenter() {
      return t(yt);
    },
    get targetSize() {
      return t(R);
    },
    get currentSize() {
      return S.current;
    },
    get currentScale() {
      return g.current * (c.parent ? c.parent.currentScale : 1);
    },
    get childSpringCount() {
      return t(vt);
    },
    set childSpringCount(e) {
      d(vt, e, !0);
    },
    get childSpringReadyCount() {
      return t(Rt);
    },
    set childSpringReadyCount(e) {
      d(Rt, e, !0);
    },
    parent: null
  };
  if (!ke())
    Ut(Ct);
  else {
    const e = Wt(), a = Object.assign(Ct, { parent: e });
    e.childSpringCount++, Ut(a);
  }
  const c = Wt(), Q = i(() => ({ instant: !ct() }));
  function q() {
    gt || ee()({
      opacity: h.current,
      scale: g.current
    });
  }
  let L;
  const P = i(() => {
    if (!t(v))
      return;
    const e = B(t(v).x + t(St).x, t(v).y + t(St).y);
    return L && I(L, e) ? L : (L = e, e);
  });
  let X;
  s(() => {
    if (t(P)) {
      if (!t(m)) {
        f.set(t(P), { instant: !0 });
        return;
      }
      F() && (!X || !I(F(), X)) && (f.set(B(t(P).x + F().x, t(P).y + F().y), { instant: !0 }), X = { ...F() }), !(f.current && I(f.current, t(P))) && f.set(t(P), {
        instant: t(Q).instant || !t(ht)
      });
    }
  }), E(C()) && C() === g.current && C() !== 1 && q();
  let xt;
  s(() => {
    t(m) && (E(j()) && j() !== xt && (g.set(j(), { instant: !0 }), xt = j()), !(!E(C()) || g.target === C()) && g.set(C(), t(Q)).then(() => {
      Ft(() => {
        q();
      });
    }).catch(st));
  }), E(x()) && x() === h.current && x() !== 1 && q();
  let bt;
  s(() => {
    t(m) && (E(w()) && w() !== bt && (h.set(w(), { instant: !0 }), bt = w()), !(!E(x()) || h.target === x()) && h.set(x(), t(Q)).then(() => {
      Ft(() => {
        q();
      });
    }).catch(st));
  });
  const Z = i(() => {
    const e = c.parent?.currentRect;
    return e || jt();
  });
  let se = i(() => !!t(Z));
  const ue = i(() => c.childSpringCount > 0), ce = i(() => !!t(y) || !t(ue));
  s(() => {
    t(ce) && (t(k) || (d(k, !0), c.parent && c.parent.childSpringReadyCount++));
  });
  let $ = p(!1);
  s(() => {
    t($) || d($, c.childSpringCount === c.childSpringReadyCount);
  });
  let Ot = 1;
  s(() => {
    Ot = c.parent ? c.parent.currentScale : 1;
  });
  function le(e) {
    const a = kt(e);
    if (a.width <= 0 || a.height <= 0)
      return;
    t(k) && mt() && mt()(e);
    const et = c.parent?.currentRectCenter || B();
    d(l, qt(a, 1 / Ot, et));
    const o = jt(t(l).x - t(Z).x, t(l).y - t(Z).y, t(l).width, t(l).height);
    if (o.x = V(o.x, 5), o.y = V(o.y, 5), o.width = V(o.width, 5), o.height = V(o.height, 5), t(u)) {
      const nt = t(u).width, U = o.width, rt = Math.abs(nt - U), it = t(u).x + t(u).width, O = o.x + o.width, W = Math.abs(it - O), ot = Math.abs(t(u).y - o.y);
      d(ht, !(W < 1e-4 && rt > 1e-4 && ot < 1e-4));
    }
    t(u) && Mt(t(u), o) || (d(u, { ...o }), De(ft()) && ft()({ ...t(u) }));
  }
  function de(e) {
    const a = kt(e);
    d(y, qt(a, 1 / c.currentScale)), d(yt, Ae(t(y)));
  }
  const fe = i(() => !t(m) || !t(_) || !f.current || !S.current ? !1 : (
    // not yet at target position
    f.current.x + t(_).x !== 0 || f.current.y + t(_).y !== 0 || // not yet at taget size
    S.current.width !== t(R).width || S.current.height !== t(R).height || // not yet at target scale
    g.current !== 1
  )), T = i(() => t(fe)), me = i(() => t(T) ? "relative" : null), pe = i(() => t(T) ? `${t(_).x}px` : null), ge = i(() => t(T) ? `${t(_).y}px` : null), he = i(() => t(T) ? "center" : null), ye = i(() => E(h.current) && h.current < 1 ? h.current : null), Se = i(() => t(T) ? `translate3d(${f.current?.x}px,${f.current?.y}px,0)scale(${g.current})` : null);
  let tt = p(void 0);
  s(() => {
    if (!t(m) || !t(l)) {
      t(y) && d(tt, at(t(y)));
      return;
    }
    d(tt, at(t(l)));
  });
  let b = p(void 0);
  s(() => {
    !t(b) || !t(m) || !lt() || Me(t(b), lt());
  }), s(() => {
    !t(b) || !t(m) || !dt() || je(t(b), dt());
  }), s(() => {
    te()?.(t(b));
  }), Oe(() => {
    gt = !0, ae(c);
  });
  var Et = A(), ve = z(Et);
  {
    var Re = (e) => {
      var a = A(), et = z(a);
      Tt(et, It, !1, (o, nt) => {
        Fe(o, (O) => d(b, O), () => t(b)), zt(o, () => Lt({ disabled: !t($), onmeasure: le })), At(o, () => ({
          class: Vt(),
          part: Nt(),
          ...Yt(),
          inert: Kt(),
          [Dt]: {
            contain: "layout",
            height: t(m) ? void 0 : `${t(tt)?.height}px`,
            opacity: t(m) ? void 0 : w()
          }
        }));
        var U = A(), rt = z(U);
        {
          var it = (O) => {
            var W = A(), ot = z(W);
            Tt(ot, Gt, !1, (Pt, Ce) => {
              zt(Pt, () => Lt({ onmeasure: de })), At(Pt, () => ({
                class: Ht(),
                ...Jt(),
                [Dt]: {
                  position: t(me),
                  left: t(pe),
                  top: t(ge),
                  transformOrigin: t(he),
                  transform: t(Se),
                  opacity: t(ye),
                  height: "100%",
                  "max-height": "inherit"
                }
              }));
              var wt = A(), xe = z(wt);
              {
                let be = i(() => ({
                  currentSize: S.current,
                  targetRect: t(u),
                  clientRect: t(y),
                  visualRect: t(y) !== null ? { ...t(y), ...S.current } : { ...S.current }
                }));
                we(xe, () => n.children, () => t(be));
              }
              D(Ce, wt);
            }), D(O, W);
          };
          _t(rt, (O) => {
            t(m) && O(it);
          });
        }
        D(nt, U);
      }), D(e, a);
    };
    _t(ve, (e) => {
      t(se) && e(Re);
    });
  }
  D(Bt, Et), Ee();
}
export {
  ln as default
};
