/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as Ee } from "../../vendor/svelte/src/index-client.js";
import { user_effect as p, template_effect as z } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as Me, pop as Te } from "../../vendor/svelte/src/internal/client/context.js";
import { get as e } from "../../vendor/svelte/src/internal/client/runtime.js";
import { child as g, first_child as Be, sibling as x } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as h, set as s } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { set_text as Le } from "../../vendor/svelte/src/internal/client/render.js";
import { user_derived as u } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as j, append as O } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as W } from "../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { attach as Z } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_attribute as Ne } from "../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { delegate as qe, event as $, delegated as Fe } from "../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { set_style as ee } from "../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { bind_this as G } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as v, spread_props as I } from "../../vendor/svelte/src/internal/client/reactivity/props.js";
import { Spring as te } from "../../vendor/svelte/src/motion/spring.js";
import { createAnimationModeObserver as Oe } from "../common/animationPreference-svelte.js";
import ke from "../components/NodeList/index-svelte.js";
import { withResources as J } from "../common/string.js";
import "../components/Button/index.js";
import "../components/ElementPane/index.js";
import { measurable as re } from "../attachments/measurable.js";
import { rectFromBounds as ne, rectContainsPoint as je } from "../../utils/rect.js";
import { vectorCreate as He } from "../../utils/vector.js";
import { supportsDisplayTransition as oe } from "../../utils/support.js";
import { passthrough as Ve, noop as Xe } from "../../utils/placeholder.js";
import k from "../components/SpringElement/index-svelte.js";
import { dispatchCustomEvent as Ye, addListener as ze } from "../../utils/dom.js";
import K from "../components/Button/index-svelte.js";
import Ge from "../components/ElementPane/index-svelte.js";
var Ie = j('<p part="dialog-title"> </p>'), Je = j("<element-pane-wrapper><!></element-pane-wrapper>", 2), Ke = j('<dialog part="dialog" closedby="closerequest"><form method="dialog" part="dialog-form"><div part="dialog-header"><!> <!></div> <div part="dialog-content"></div> <div part="dialog-footer"><!> <!></div></form> <!></dialog> <!>', 1), Qe = j('<div class="root"><!></div>');
function At(ie, o) {
  Me(o, !0);
  let ae = v(o, "disabled", 3, !1), le = v(o, "animations", 3, "auto"), H = v(o, "sources", 19, () => []), A = v(o, "assets", 19, () => ({})), P = v(o, "locale", 19, () => ({})), E = v(o, "propResourceMap", 19, () => ({ title: "locale", label: "locale", icon: "assets" })), se = v(o, "beforeRenderNode", 3, Ve);
  const V = Oe(), M = u(() => V.current);
  p(() => {
    V.setPreference(le());
  });
  let T = h(void 0);
  p(() => {
    e(T) && Ye(e(T), "sourceschange", { detail: H().length });
  });
  let a = h(void 0), m = h(void 0), D = h(!1);
  const de = u(() => J({ icon: "close", label: "close" }, E(), { locale: P(), assets: A() })), ue = u(() => J({ label: "cancel" }, E(), { locale: P(), assets: A() })), ce = u(() => J({ label: "import" }, E(), { locale: P(), assets: A() }));
  let Q = h("");
  function me(t) {
    t.command === "show-modal" && pe(t);
  }
  function fe(t) {
    e(a)?.open || ge();
  }
  function pe(t) {
    s(Q, t?.source?.textContent.trim() || "");
  }
  function ge(t) {
    oe() || U();
  }
  function he(t) {
    const i = t.currentTarget;
    t.target !== i || !e(c) || je(e(c), He(t.clientX, t.clientY)) || i.close();
  }
  function ve(t) {
    t.propertyName !== "display" || e(a)?.open || U();
  }
  function U() {
    s(c, null), l.set(null, { instant: !0 }), s(b, null), y.set(null, { instant: !0 }), s(D, !1);
  }
  let c = h(null), l = new te(null);
  p(() => {
    e(c) && l.set(e(c), { instant: !e(M) });
  }), p(() => {
    Object.assign(l, o.springDefaults);
  });
  function be(t) {
    if (!e(a)?.open || !e(m)?.children.length)
      return;
    const i = ne(t);
    if (e(D)) {
      s(c, i, !0);
      return;
    }
    const n = 10;
    s(
      c,
      {
        x: i.x + n,
        y: i.y + n,
        width: i.width - n * 2,
        height: i.height - n * 2
      },
      !0
    ), requestAnimationFrame(() => {
      s(c, i, !0), s(D, !0);
    });
  }
  let b = h(null), y = new te(null);
  p(() => {
    e(b) && y.set(e(b), { instant: !e(M) });
  }), p(() => {
    Object.assign(y, o.springDefaults);
  });
  const _e = u(() => {
    if (!e(b) || !y.current)
      return;
    const { x: t, y: i, width: n, height: Y } = e(b), { x: w, y: R, width: L, height: N } = y.current, q = R - i, _ = t + n - (w + L), F = i + Y - (R + N), S = w - t;
    if (!(q === 0 && _ === 0 && F === 0 && S === 0))
      return `${q}px ${_}px ${F}px ${S}px`;
  });
  function xe(t) {
    !e(a)?.open || !e(m)?.children.length || s(b, ne(t), !0);
  }
  function De(...t) {
    e(m)?.append(...t), e(m)?.querySelector("[autofocus]")?.focus(), e(m)?.querySelectorAll("button[command=close]").forEach((n) => {
      n.commandForElement = e(a);
    });
  }
  p(() => {
    if (!e(a))
      return;
    e(a).append = De;
    const t = ze(e(a), "command", me);
    return () => {
      t();
    };
  });
  const B = u(() => e(M) && e(D)), ye = u(() => ({
    disabled: ae(),
    dialog: e(a),
    resources: { locale: P(), assets: A() },
    propResourceMap: E(),
    enableAnimations: e(M),
    springDefaults: o.springDefaults
  }));
  Ee(() => {
    V.destroy();
  });
  var X = Qe(), we = g(X);
  {
    var Re = (t) => {
      var i = Ke(), n = Be(i), Y = u(() => oe() ? ve : Xe);
      let w;
      var R = g(n), L = g(R), N = g(L);
      k(N, {
        get enableAnimations() {
          return e(B);
        },
        class: "dialog-title-spring",
        get springDefaults() {
          return o.springDefaults;
        },
        children: (r, d) => {
          var f = Ie(), C = g(f);
          z(() => Le(C, e(Q))), O(r, f);
        },
        $$slots: { default: !0 }
      });
      var q = x(N, 2);
      k(q, {
        class: "dialog-button-close-spring",
        get enableAnimations() {
          return e(B);
        },
        get springDefaults() {
          return o.springDefaults;
        },
        children: (r, d) => {
          K(r, I(() => e(de), {
            part: "dialog-button-close",
            command: "close",
            get commandfor() {
              return e(a);
            }
          }));
        },
        $$slots: { default: !0 }
      });
      var _ = x(L, 2);
      G(_, (r) => s(m, r), () => e(m)), Z(_, () => re({ onmeasure: xe }));
      var F = x(_, 2), S = g(F);
      k(S, {
        class: "dialog-button-cancel-spring",
        get enableAnimations() {
          return e(B);
        },
        get springDefaults() {
          return o.springDefaults;
        },
        children: (r, d) => {
          K(r, I(() => e(ue), {
            part: "dialog-button-cancel",
            get commandfor() {
              return e(a);
            },
            command: "close"
          }));
        },
        $$slots: { default: !0 }
      });
      var Se = x(S, 2);
      k(Se, {
        class: "dialog-button-import-spring",
        get enableAnimations() {
          return e(B);
        },
        get springDefaults() {
          return o.springDefaults;
        },
        children: (r, d) => {
          K(r, I(() => e(ce), { part: "dialog-button-import", type: "submit" }));
        },
        $$slots: { default: !0 }
      });
      var Ce = x(R, 2);
      {
        var Ae = (r) => {
          var d = Je();
          let f;
          var C = g(d);
          Ge(C, {
            get width() {
              return l.current.width;
            },
            get height() {
              return l.current.height;
            }
          }), z(() => f = ee(d, "", f, {
            left: l.target ? `${-l.target.x}px` : void 0,
            top: l.target ? `${-l.target.y}px` : void 0,
            translate: l.current ? `${l.current.x}px ${l.current.y}px` : void 0
          })), O(r, d);
        };
        W(Ce, (r) => {
          l.current && r(Ae);
        });
      }
      G(n, (r) => s(a, r), () => e(a)), Z(n, () => re({ onmeasure: be }));
      var Pe = x(n, 2);
      {
        let r = u(() => ({ items: H() }));
        ke(Pe, {
          beforeRenderNode: (d, f, C) => se()(d, f, C),
          get nodes() {
            return o.template;
          },
          get context() {
            return e(r);
          },
          get sharedContext() {
            return e(ye);
          }
        });
      }
      z(() => {
        Ne(n, "data-visible", e(D) ? "" : void 0), w = ee(n, "", w, {
          "--dialog-content-clip-path": e(_e)
        });
      }), $("transitionend", n, function(...r) {
        e(Y)?.apply(this, r);
      }), Fe("click", n, he), $("toggle", n, fe), O(t, i);
    };
    W(we, (t) => {
      H().length && t(Re);
    });
  }
  G(X, (t) => s(T, t), () => e(T)), O(ie, X), Te();
}
qe(["click"]);
export {
  At as default
};
