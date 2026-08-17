/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as Me } from "../../vendor/svelte/src/index-client.js";
import { user_effect as g, template_effect as I } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as Te, pop as Be } from "../../vendor/svelte/src/internal/client/context.js";
import { get as e } from "../../vendor/svelte/src/internal/client/runtime.js";
import { child as v, first_child as Le, sibling as D } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as h, set as d } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { set_text as Ne } from "../../vendor/svelte/src/internal/client/render.js";
import { user_derived as u } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { if_block as q } from "../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { from_html as R, append as y } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { attach as ee } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { delegate as qe, event as te, delegated as Fe } from "../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { set_style as re } from "../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { bind_this as J } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as b, spread_props as K } from "../../vendor/svelte/src/internal/client/reactivity/props.js";
import { Spring as oe } from "../../vendor/svelte/src/motion/spring.js";
import { createAnimationModeObserver as Oe } from "../common/animationPreference-svelte.js";
import ke from "../components/NodeList/index-svelte.js";
import { withResources as Q } from "../common/string.js";
import "../components/Button/index.js";
import "../components/ElementPane/index.js";
import { measurable as ne } from "../attachments/measurable.js";
import { rectFromBounds as ae, rectContainsPoint as je } from "../../utils/rect.js";
import { vectorCreate as He } from "../../utils/vector.js";
import { supportsDisplayTransition as ie } from "../../utils/support.js";
import { passthrough as Ve, noop as Xe } from "../../utils/placeholder.js";
import F from "../components/SpringElement/index-svelte.js";
import { dispatchCustomEvent as Ye, addListener as ze } from "../../utils/dom.js";
import U from "../components/Button/index-svelte.js";
import Ge from "../components/ElementPane/index-svelte.js";
var Ie = R('<p part="dialog-title"> </p>'), Je = R('<div part="dialog-header"><!> <!></div>'), Ke = R('<div part="dialog-footer"><!> <!></div>'), Qe = R("<element-pane-wrapper><!></element-pane-wrapper>", 2), Ue = R('<dialog part="dialog" closedby="closerequest"><form method="dialog" part="dialog-form"><!> <div part="dialog-content"></div> <!></form> <!></dialog> <!>', 1), We = R('<div class="root"><!></div>');
function Pt(le, o) {
  Te(o, !0);
  let se = b(o, "disabled", 3, !1), de = b(o, "animations", 3, "auto"), O = b(o, "sources", 19, () => []), E = b(o, "assets", 19, () => ({})), M = b(o, "locale", 19, () => ({})), T = b(o, "propResourceMap", 19, () => ({ title: "locale", label: "locale", icon: "assets" })), ce = b(o, "beforeRenderNode", 3, Ve);
  const k = Oe(), m = u(() => k.current);
  g(() => {
    k.setPreference(de());
  });
  let B = h(void 0);
  g(() => {
    e(B) && Ye(e(B), "sourceschange", { detail: O().length });
  });
  let n = h(void 0), w = h(void 0), L = h(!1);
  const ue = u(() => Q({ icon: "close", label: "close" }, T(), { locale: M(), assets: E() })), me = u(() => Q({ label: "cancel" }, T(), { locale: M(), assets: E() })), fe = u(() => Q({ label: "import" }, T(), { locale: M(), assets: E() }));
  let W = h("");
  function pe(t) {
    t.command === "show-modal" && ve(t);
  }
  function ge(t) {
    e(n)?.open || he();
  }
  function ve(t) {
    d(W, t?.source?.textContent.trim() || ""), requestAnimationFrame(() => {
      d(L, !0);
    });
  }
  function he(t) {
    ie() || Z();
  }
  function be(t) {
    const c = t.currentTarget;
    t.target !== c || !e(_) || je(e(_), He(t.clientX, t.clientY)) || c.close();
  }
  function _e(t) {
    t.propertyName !== "display" || e(n)?.open || Z();
  }
  function Z() {
    d(_, null), a.set(null, { instant: !0 }), d(x, null), C.set(null, { instant: !0 }), d(L, !1);
  }
  let _ = h(null), a = new oe(null);
  g(() => {
    e(_) && a.set(e(_), { instant: !e(m) });
  }), g(() => {
    Object.assign(a, o.springDefaults);
  });
  function xe(t) {
    e(n)?.open && d(_, ae(t), !0);
  }
  let x = h(null), C = new oe(null);
  g(() => {
    e(x) && C.set(e(x), { instant: !e(m) });
  }), g(() => {
    Object.assign(C, o.springDefaults);
  });
  const De = u(() => {
    if (!e(x) || !C.current)
      return "0px";
    const { x: t, y: c, width: i, height: H } = e(x), { x: S, y: A, width: N, height: V } = C.current, P = A - c, X = t + i - (S + N), Y = c + H - (A + V), z = S - t;
    return `${P}px ${X}px ${Y}px ${z}px`;
  });
  function ye(t) {
    e(n)?.open && d(x, ae(t), !0);
  }
  function Re(...t) {
    e(w)?.append(...t), e(w)?.querySelector("[autofocus]")?.focus(), e(w)?.querySelectorAll("button[command=close]").forEach((i) => {
      i.commandForElement = e(n);
    });
  }
  g(() => {
    if (!e(n))
      return;
    e(n).append = Re;
    const t = ze(e(n), "command", pe);
    return () => {
      t();
    };
  });
  const we = u(() => ({
    disabled: se(),
    dialog: e(n),
    resources: { locale: M(), assets: E() },
    propResourceMap: T(),
    enableAnimations: e(m),
    springDefaults: o.springDefaults
  }));
  Me(() => {
    k.destroy();
  });
  var j = We(), Ce = v(j);
  {
    var Se = (t) => {
      var c = Ue(), i = Le(c), H = u(() => ie() ? _e : Xe);
      let S;
      var A = v(i), N = v(A);
      {
        var V = (r) => {
          var l = Je(), s = v(l);
          F(s, {
            class: "dialog-title-spring",
            get enableAnimations() {
              return e(m);
            },
            get springDefaults() {
              return o.springDefaults;
            },
            children: (p, G) => {
              var $ = Ie(), Ee = v($);
              I(() => Ne(Ee, e(W))), y(p, $);
            },
            $$slots: { default: !0 }
          });
          var f = D(s, 2);
          F(f, {
            class: "dialog-button-close-spring",
            get enableAnimations() {
              return e(m);
            },
            get springDefaults() {
              return o.springDefaults;
            },
            children: (p, G) => {
              U(p, K(() => e(ue), {
                part: "dialog-button-close",
                command: "close",
                get commandfor() {
                  return e(n);
                }
              }));
            },
            $$slots: { default: !0 }
          }), y(r, l);
        };
        q(N, (r) => {
          e(L) && r(V);
        });
      }
      var P = D(N, 2);
      J(P, (r) => d(w, r), () => e(w)), ee(P, () => ne({ onmeasure: ye }));
      var X = D(P, 2);
      {
        var Y = (r) => {
          var l = Ke(), s = v(l);
          F(s, {
            class: "dialog-button-cancel-spring",
            get enableAnimations() {
              return e(m);
            },
            get springDefaults() {
              return o.springDefaults;
            },
            children: (p, G) => {
              U(p, K(() => e(me), {
                part: "dialog-button-cancel",
                get commandfor() {
                  return e(n);
                },
                command: "close"
              }));
            },
            $$slots: { default: !0 }
          });
          var f = D(s, 2);
          F(f, {
            class: "dialog-button-import-spring",
            get enableAnimations() {
              return e(m);
            },
            get springDefaults() {
              return o.springDefaults;
            },
            children: (p, G) => {
              U(p, K(() => e(fe), { part: "dialog-button-import", type: "submit" }));
            },
            $$slots: { default: !0 }
          }), y(r, l);
        };
        q(X, (r) => {
          e(L) && r(Y);
        });
      }
      var z = D(A, 2);
      {
        var Ae = (r) => {
          var l = Qe();
          let s;
          var f = v(l);
          Ge(f, {
            get width() {
              return a.current.width;
            },
            get height() {
              return a.current.height;
            }
          }), I(() => s = re(l, "", s, {
            left: a.target ? `${-a.target.x}px` : void 0,
            top: a.target ? `${-a.target.y}px` : void 0,
            translate: a.current ? `${a.current.x}px ${a.current.y}px` : void 0
          })), y(r, l);
        };
        q(z, (r) => {
          a.current && r(Ae);
        });
      }
      J(i, (r) => d(n, r), () => e(n)), ee(i, () => ne({ onmeasure: xe }));
      var Pe = D(i, 2);
      {
        let r = u(() => ({ items: O() }));
        ke(Pe, {
          beforeRenderNode: (l, s, f) => ce()(l, s, f),
          get nodes() {
            return o.template;
          },
          get context() {
            return e(r);
          },
          get sharedContext() {
            return e(we);
          }
        });
      }
      I(() => S = re(i, "", S, {
        "--dialog-content-clip-path": e(De)
      })), te("transitionend", i, function(...r) {
        e(H)?.apply(this, r);
      }), Fe("click", i, be), te("toggle", i, ge), y(t, c);
    };
    q(Ce, (t) => {
      O().length && t(Se);
    });
  }
  J(j, (t) => d(B, t), () => e(B)), y(le, j), Be();
}
qe(["click"]);
export {
  Pt as default
};
