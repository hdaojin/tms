/*!
* FilePond v5.0.0-beta.78
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as kt } from "../../vendor/svelte/src/index-client.js";
import { user_effect as h, template_effect as z } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as qt, pop as Ft } from "../../vendor/svelte/src/internal/client/context.js";
import { get as t } from "../../vendor/svelte/src/internal/client/runtime.js";
import { child as b, first_child as jt, only_child as At, sibling as O } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as p, set as a } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { set_text as It } from "../../vendor/svelte/src/internal/client/render.js";
import { user_derived as s } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as H, append as j } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as nt } from "../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { attach as it } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_attribute as Ht } from "../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { delegate as Vt, event as at, delegated as Xt } from "../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { set_style as lt } from "../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { proxy as Yt } from "../../vendor/svelte/src/internal/client/proxy.js";
import { bind_this as G } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as y, spread_props as A } from "../../vendor/svelte/src/internal/client/reactivity/props.js";
import { Spring as J } from "../../vendor/svelte/src/motion/spring.js";
import st from "../components/NodeList/index-svelte.js";
import { withResources as K } from "../common/string.js";
import "../components/Button/index.js";
import "../components/ElementPane/index.js";
import { measurable as dt } from "../attachments/measurable.js";
import { rectFromBounds as ut, rectContainsPoint as zt } from "../../utils/rect.js";
import { vectorCreate as Gt } from "../../utils/vector.js";
import { supportsDialogCloseTransition as ct } from "../../utils/support.js";
import { passthrough as Jt, noop as Kt } from "../../utils/placeholder.js";
import I from "../components/SpringElement/index-svelte.js";
import { dispatchCustomEvent as Qt, addListener as Ut } from "../../utils/dom.js";
import { createMotionStateObserver as Wt, shouldReduceMotion as Zt } from "../common/motionState-svelte.js";
import Q from "../components/Button/index-svelte.js";
import $t from "../components/ElementPane/index-svelte.js";
var te = H('<p part="dialog-title"> </p>'), ee = H("<element-pane-wrapper><!></element-pane-wrapper>", 2), re = H('<dialog part="dialog" closedby="closerequest"><form method="dialog" part="dialog-form"><div part="dialog-header"><!> <!></div> <div part="dialog-content"><!></div> <div part="dialog-footer"><!> <!></div></form> <!></dialog> <!>', 1), oe = H('<div class="root"><!></div>');
function qe(pt, n) {
  qt(n, !0);
  let gt = y(n, "disabled", 3, !1), V = y(n, "sources", 19, () => []), x = y(n, "assets", 19, () => ({})), M = y(n, "locale", 19, () => ({})), C = y(n, "propResourceMap", 19, () => ({ title: "locale", label: "locale", icon: "assets" })), U = y(n, "beforeRenderNode", 3, Jt);
  const W = Wt(), g = s(() => Zt(W.current, n.reducedMotionPreference));
  let Z = p(Yt({})), $ = p(0), N = p(void 0);
  h(() => {
    t(N) && Qt(t(N), "sourceschange", { detail: V().length });
  });
  let d = p(void 0), m = p(void 0), R = p(!1);
  const mt = s(() => K({ icon: "close", label: "close" }, C(), { locale: M(), assets: x() })), ft = s(() => K({ label: "cancel" }, C(), { locale: M(), assets: x() })), ht = s(() => K({ label: "import" }, C(), { locale: M(), assets: x() }));
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
    a(f, null), l.set(null, { instant: !0 }), a(_, null), w.set(null, { instant: !0 }), P.set(0, { instant: !0 }), a(R, !1);
  }
  let f = p(null), l = new J(null);
  h(() => {
    t(f) && l.set(t(f), { instant: t(g) });
  }), h(() => {
    Object.assign(l, n.springOptions);
  });
  function Mt(e) {
    if (!t(d)?.open || !t(m)?.children.length)
      return;
    const r = ut(e);
    if (t(R)) {
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
      a(f, r, !0), a(R, !0);
    });
  }
  let P = new J(0);
  h(() => {
    Object.assign(P, n.springOptions);
  });
  let _ = p(null), w = new J(null);
  h(() => {
    t(_) && (w.set(t(_), { instant: t(g) }), P.set(1, { instant: t(g) }));
  }), h(() => {
    Object.assign(w, n.springOptions);
  });
  const Ct = s(() => {
    if (!t(_) || !w.current)
      return;
    const { x: e, y: r, width: i, height: S } = t(_), { x: D, y: E, width: B, height: L } = w.current, k = E - r, v = e + i - (D + B), q = r + S - (E + L), F = D - e;
    if (!(k === 0 && v === 0 && q === 0 && F === 0))
      return `${k}px ${v}px ${q}px ${F}px`;
  });
  function Rt(e) {
    !t(d)?.open || !t(m)?.children.length || a(_, ut(e), !0);
  }
  function wt() {
    t(m)?.querySelector("[autofocus]")?.focus(), t(m)?.querySelectorAll("button[command=close]").forEach((r) => {
      r.commandForElement = t(d);
    });
  }
  function St(e, r) {
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
  const T = s(() => t(g) || !t(R)), rt = new MutationObserver((e) => {
    let r = !1;
    for (const i of e)
      for (const S of i.addedNodes)
        if (S.nodeType === Node.ELEMENT_NODE && (r = !0, r))
          break;
    r && wt();
  });
  h(() => {
    if (t(m))
      return rt.observe(t(m), { childList: !0 }), () => {
        rt.disconnect();
      };
  }), kt(() => {
    W.destroy();
  });
  var X = oe(), Et = b(X);
  {
    var Nt = (e) => {
      var r = re(), i = jt(r), S = s(() => ct() ? xt : Kt);
      let D;
      var E = b(i), B = b(E), L = b(B);
      I(L, {
        get reduceMotion() {
          return t(T);
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
      var k = O(L, 2);
      I(k, {
        class: "dialog-button-close-spring",
        get reduceMotion() {
          return t(T);
        },
        get springOptions() {
          return n.springOptions;
        },
        children: (o, u) => {
          Q(o, A(() => t(mt), {
            part: "dialog-button-close",
            command: "close",
            get commandfor() {
              return t(d);
            }
          }));
        },
        $$slots: { default: !0 }
      });
      var v = O(B, 2), q = b(v);
      {
        let o = s(() => ({
          reduceMotion: t(g),
          springOptions: n.springOptions
        })), u = s(() => ({ locale: M(), assets: x() }));
        st(q, A(() => t(Z), {
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
            return C();
          },
          get beforeRenderNode() {
            return U();
          }
        }));
      }
      G(v, (o) => a(m, o), () => t(m)), it(v, () => dt({ onmeasure: Rt }));
      var F = O(v, 2), ot = b(F);
      I(ot, {
        class: "dialog-button-cancel-spring",
        get reduceMotion() {
          return t(T);
        },
        get springOptions() {
          return n.springOptions;
        },
        children: (o, u) => {
          Q(o, A(() => t(ft), {
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
      I(Pt, {
        class: "dialog-button-import-spring",
        get reduceMotion() {
          return t(T);
        },
        get springOptions() {
          return n.springOptions;
        },
        children: (o, u) => {
          {
            let c = s(() => ({ counter: t($) }));
            Q(o, A(() => t(ht), {
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
      var Tt = O(E, 2);
      {
        var Bt = (o) => {
          var u = ee();
          let c;
          var Y = b(u);
          $t(Y, {
            get width() {
              return l.current.width;
            },
            get height() {
              return l.current.height;
            }
          }), z(() => c = lt(u, "", c, {
            left: l.target ? `${-l.target.x}px` : void 0,
            top: l.target ? `${-l.target.y}px` : void 0,
            translate: l.current ? `${l.current.x}px ${l.current.y}px` : void 0
          })), j(o, u);
        };
        nt(Tt, (o) => {
          l.current && o(Bt);
        });
      }
      G(i, (o) => a(d, o), () => t(d)), it(i, () => dt({ onmeasure: Mt }));
      var Lt = O(i, 2);
      {
        let o = s(() => ({ locale: M(), assets: x() })), u = s(() => ({ items: V() })), c = s(() => ({
          disabled: gt(),
          dialog: t(d),
          reduceMotion: t(g),
          springOptions: n.springOptions,
          setDialogContentTemplate: St,
          setDialogImportButtonCount: Dt
        }));
        st(Lt, {
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
            return C();
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
        Ht(i, "data-visible", t(R) ? "" : void 0), D = lt(i, "", D, {
          "--dialog-content-clip-path": t(Ct),
          "--dialog-transition": P.current
        });
      }), at("transitionend", i, function(...o) {
        t(S)?.apply(this, o);
      }), Xt("click", i, yt), at("toggle", i, bt), j(e, r);
    };
    nt(Et, (e) => {
      V().length && e(Nt);
    });
  }
  G(X, (e) => a(N, e), () => t(N)), j(pt, X), Ft();
}
Vt(["click"]);
export {
  qe as default
};
