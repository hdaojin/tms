/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as qt } from "../../vendor/svelte/src/index-client.js";
import { user_effect as h, template_effect as z } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as Ft, pop as jt } from "../../vendor/svelte/src/internal/client/context.js";
import { get as t } from "../../vendor/svelte/src/internal/client/runtime.js";
import { child as b, first_child as kt, only_child as At, sibling as O } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as p, set as a } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { set_text as It } from "../../vendor/svelte/src/internal/client/render.js";
import { user_derived as l } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as I, append as j } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as nt } from "../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { attach as it } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_attribute as Ht } from "../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { delegate as Vt, event as at, delegated as Xt } from "../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { set_style as st } from "../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { proxy as Yt } from "../../vendor/svelte/src/internal/client/proxy.js";
import { bind_this as G } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as y, spread_props as k } from "../../vendor/svelte/src/internal/client/reactivity/props.js";
import { Spring as J } from "../../vendor/svelte/src/motion/spring.js";
import lt from "../components/NodeList/index-svelte.js";
import { withResources as K } from "../common/string.js";
import "../components/Button/index.js";
import "../components/ElementPane/index.js";
import { measurable as dt } from "../attachments/measurable.js";
import { rectFromBounds as ut, rectContainsPoint as zt } from "../../utils/rect.js";
import { vectorCreate as Gt } from "../../utils/vector.js";
import { supportsDisplayTransition as ct } from "../../utils/support.js";
import { passthrough as Jt, noop as Kt } from "../../utils/placeholder.js";
import A from "../components/SpringElement/index-svelte.js";
import { dispatchCustomEvent as Qt, addListener as Ut } from "../../utils/dom.js";
import { createMotionStateObserver as Wt, shouldReduceMotion as Zt } from "../common/motionState-svelte.js";
import Q from "../components/Button/index-svelte.js";
import $t from "../components/ElementPane/index-svelte.js";
var te = I('<p part="dialog-title"> </p>'), ee = I("<element-pane-wrapper><!></element-pane-wrapper>", 2), re = I('<dialog part="dialog" closedby="closerequest"><form method="dialog" part="dialog-form"><div part="dialog-header"><!> <!></div> <div part="dialog-content"><!></div> <div part="dialog-footer"><!> <!></div></form> <!></dialog> <!>', 1), oe = I('<div class="root"><!></div>');
function Fe(pt, n) {
  Ft(n, !0);
  let gt = y(n, "disabled", 3, !1), H = y(n, "sources", 19, () => []), x = y(n, "assets", 19, () => ({})), M = y(n, "locale", 19, () => ({})), R = y(n, "propResourceMap", 19, () => ({ title: "locale", label: "locale", icon: "assets" })), U = y(n, "beforeRenderNode", 3, Jt);
  const W = Wt(), g = l(() => Zt(W.current, n.reducedMotionPreference));
  let Z = p(Yt({})), $ = p(0), E = p(void 0);
  h(() => {
    t(E) && Qt(t(E), "sourceschange", { detail: H().length });
  });
  let d = p(void 0), m = p(void 0), w = p(!1);
  const mt = l(() => K({ icon: "close", label: "close" }, R(), { locale: M(), assets: x() })), ft = l(() => K({ label: "cancel" }, R(), { locale: M(), assets: x() })), ht = l(() => K({ label: "import" }, R(), { locale: M(), assets: x() }));
  let tt = p("");
  function vt(e) {
    e.command === "show-modal" && _t(e);
  }
  function bt(e) {
    t(d)?.open || Ot();
  }
  function _t(e) {
    a(tt, e?.source?.textContent.trim() || "");
  }
  function Ot(e) {
    ct() || et();
  }
  function yt(e) {
    const r = e.currentTarget;
    e.target !== r || !t(f) || zt(t(f), Gt(e.clientX, e.clientY)) || r.close();
  }
  function xt(e) {
    e.propertyName !== "display" || t(d)?.open || et();
  }
  function et() {
    a(f, null), s.set(null, { instant: !0 }), a(_, null), S.set(null, { instant: !0 }), N.set(0, { instant: !0 }), a(w, !1);
  }
  let f = p(null), s = new J(null);
  h(() => {
    t(f) && s.set(t(f), { instant: t(g) });
  }), h(() => {
    Object.assign(s, n.springOptions);
  });
  function Mt(e) {
    if (!t(d)?.open || !t(m)?.children.length)
      return;
    const r = ut(e);
    if (t(w)) {
      a(f, r, !0);
      return;
    }
    const i = 10;
    a(
      f,
      {
        x: r.x + i,
        y: r.y + i,
        width: r.width - i * 2,
        height: r.height - i * 2
      },
      !0
    ), requestAnimationFrame(() => {
      a(f, r, !0), a(w, !0);
    });
  }
  let N = new J(0);
  h(() => {
    Object.assign(N, n.springOptions);
  });
  let _ = p(null), S = new J(null);
  h(() => {
    t(_) && (S.set(t(_), { instant: t(g) }), N.set(1, { instant: t(g) }));
  }), h(() => {
    Object.assign(S, n.springOptions);
  });
  const Rt = l(() => {
    if (!t(_) || !S.current)
      return;
    const { x: e, y: r, width: i, height: X } = t(_), { x: C, y: D, width: T, height: B } = S.current, L = D - r, v = e + i - (C + T), q = r + X - (D + B), F = C - e;
    if (!(L === 0 && v === 0 && q === 0 && F === 0))
      return `${L}px ${v}px ${q}px ${F}px`;
  });
  function wt(e) {
    !t(d)?.open || !t(m)?.children.length || a(_, ut(e), !0);
  }
  function St() {
    t(m)?.querySelector("[autofocus]")?.focus(), t(m)?.querySelectorAll("button[command=close]").forEach((r) => {
      r.commandForElement = t(d);
    });
  }
  function Ct(e, r) {
    a(Z, { data: r, nodes: e }, !0);
  }
  function Dt(e) {
    a($, e, !0);
  }
  h(() => {
    if (!t(d))
      return;
    const e = Ut(t(d), "command", vt);
    return () => {
      e();
    };
  });
  const P = l(() => t(g) || !t(w)), rt = new MutationObserver((e) => {
    for (const r of e) {
      const [i] = r.addedNodes;
      !i || i.nodeType !== Node.ELEMENT_NODE || St();
    }
  });
  h(() => {
    if (t(m))
      return rt.observe(t(m), { childList: !0 }), () => {
        rt.disconnect();
      };
  }), qt(() => {
    W.destroy();
  });
  var V = oe(), Et = b(V);
  {
    var Nt = (e) => {
      var r = re(), i = kt(r), X = l(() => ct() ? xt : Kt);
      let C;
      var D = b(i), T = b(D), B = b(T);
      A(B, {
        get reduceMotion() {
          return t(P);
        },
        class: "dialog-title-spring",
        get springOptions() {
          return n.springOptions;
        },
        children: (o, u) => {
          var c = te(), Y = At(c, !0);
          z(() => It(Y, t(tt))), j(o, c);
        },
        $$slots: { default: !0 }
      });
      var L = O(B, 2);
      A(L, {
        class: "dialog-button-close-spring",
        get reduceMotion() {
          return t(P);
        },
        get springOptions() {
          return n.springOptions;
        },
        children: (o, u) => {
          Q(o, k(() => t(mt), {
            part: "dialog-button-close",
            command: "close",
            get commandfor() {
              return t(d);
            }
          }));
        },
        $$slots: { default: !0 }
      });
      var v = O(T, 2), q = b(v);
      {
        let o = l(() => ({
          reduceMotion: t(g),
          springOptions: n.springOptions
        })), u = l(() => ({ locale: M(), assets: x() }));
        lt(q, k(() => t(Z), {
          get context() {
            return t(o);
          },
          get reduceMotion() {
            return t(g);
          },
          get springOptions() {
            return n.springOptions;
          },
          get resources() {
            return t(u);
          },
          get propResourceMap() {
            return R();
          },
          get beforeRenderNode() {
            return U();
          }
        }));
      }
      G(v, (o) => a(m, o), () => t(m)), it(v, () => dt({ onmeasure: wt }));
      var F = O(v, 2), ot = b(F);
      A(ot, {
        class: "dialog-button-cancel-spring",
        get reduceMotion() {
          return t(P);
        },
        get springOptions() {
          return n.springOptions;
        },
        children: (o, u) => {
          Q(o, k(() => t(ft), {
            part: "dialog-button-cancel",
            get commandfor() {
              return t(d);
            },
            command: "close"
          }));
        },
        $$slots: { default: !0 }
      });
      var Pt = O(ot, 2);
      A(Pt, {
        class: "dialog-button-import-spring",
        get reduceMotion() {
          return t(P);
        },
        get springOptions() {
          return n.springOptions;
        },
        children: (o, u) => {
          {
            let c = l(() => ({ counter: t($) }));
            Q(o, k(() => t(ht), {
              get dataset() {
                return t(c);
              },
              part: "dialog-button-import",
              type: "submit"
            }));
          }
        },
        $$slots: { default: !0 }
      });
      var Tt = O(D, 2);
      {
        var Bt = (o) => {
          var u = ee();
          let c;
          var Y = b(u);
          $t(Y, {
            get width() {
              return s.current.width;
            },
            get height() {
              return s.current.height;
            }
          }), z(() => c = st(u, "", c, {
            left: s.target ? `${-s.target.x}px` : void 0,
            top: s.target ? `${-s.target.y}px` : void 0,
            translate: s.current ? `${s.current.x}px ${s.current.y}px` : void 0
          })), j(o, u);
        };
        nt(Tt, (o) => {
          s.current && o(Bt);
        });
      }
      G(i, (o) => a(d, o), () => t(d)), it(i, () => dt({ onmeasure: Mt }));
      var Lt = O(i, 2);
      {
        let o = l(() => ({ locale: M(), assets: x() })), u = l(() => ({ items: H() })), c = l(() => ({
          disabled: gt(),
          dialog: t(d),
          reduceMotion: t(g),
          springOptions: n.springOptions,
          setDialogContentTemplate: Ct,
          setDialogImportButtonCount: Dt
        }));
        lt(Lt, {
          get reduceMotion() {
            return t(g);
          },
          get springOptions() {
            return n.springOptions;
          },
          get resources() {
            return t(o);
          },
          get propResourceMap() {
            return R();
          },
          get nodes() {
            return n.template;
          },
          get data() {
            return t(u);
          },
          get context() {
            return t(c);
          },
          get beforeRenderNode() {
            return U();
          }
        });
      }
      z(() => {
        Ht(i, "data-visible", t(w) ? "" : void 0), C = st(i, "", C, {
          "--dialog-content-clip-path": t(Rt),
          "--dialog-transition": N.current
        });
      }), at("transitionend", i, function(...o) {
        t(X)?.apply(this, o);
      }), Xt("click", i, yt), at("toggle", i, bt), j(e, r);
    };
    nt(Et, (e) => {
      H().length && e(Nt);
    });
  }
  G(V, (e) => a(E, e), () => t(E)), j(pt, V), jt();
}
Vt(["click"]);
export {
  Fe as default
};
