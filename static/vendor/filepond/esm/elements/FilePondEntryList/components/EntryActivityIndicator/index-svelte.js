/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onMount as X } from "../../../../vendor/svelte/src/index-client.js";
import { user_effect as P, template_effect as Y } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { pop as Z, push as $ } from "../../../../vendor/svelte/src/internal/client/context.js";
import { get as t, untrack as tt } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { first_child as rt, sibling as et, child as ot } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { set as c, state as A } from "../../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { from_html as F, append as E } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { user_derived as i } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { if_block as I } from "../../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { set_attribute as nt } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_style as st } from "../../../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { prop as d, spread_props as D } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { Spring as it } from "../../../../vendor/svelte/src/motion/spring.js";
import { getExtensionStateByStatusCode as at } from "../../../../common/entry.js";
import { isObjectValuesEqual as ut } from "../../../../utils/object.js";
import { getValueByKeyFromData as lt } from "../../../common/string.js";
import { getAppContext as ct } from "../../contexts/appContext.js";
import { getEntryContext as pt } from "../../contexts/entryContext.js";
import { gate as ft } from "../../../common/store-svelte.js";
import mt from "../../../components/SpringElement/index-svelte.js";
import "../../../components/Button/index.js";
import "../../../components/ProgressIndicator/index.js";
import dt from "../../../components/NodeList/index-svelte.js";
import { addListener as w } from "../../../../utils/dom.js";
import gt from "../../../components/Button/index-svelte.js";
import bt from "../../../components/ProgressIndicator/index-svelte.js";
var yt = F("<div><!></div>"), ht = F("<!><!>", 1);
function Gt(N, l) {
  $(l, !0);
  let O = d(l, "class", 3, void 0), j = d(l, "part", 3, void 0), g = d(l, "buttonPart", 3, void 0), q = d(l, "states", 19, () => []), p;
  const b = i(ct), L = i(() => t(b).locale), y = i(() => t(b).enableAnimations), R = i(() => t(b).springDefaults), V = pt(), H = i(() => Object.values(V.current.extensionState));
  function K(r, e) {
    if (r.length) {
      for (const o of r) {
        const s = at(e, o.codes);
        if (!s)
          continue;
        const _ = o.button, S = o.progress ? { ...o.progress, value: s.progress } : null;
        return { button: _, progress: S };
      }
      return null;
    }
  }
  const B = i(() => K(q(), t(H))), M = i(() => t(B)?.progress), T = i(() => z(t(B)?.button)), a = ft(
    // should update value?
    (r, e) => r && e ? !ut(r, e) : r !== e,
    // $derived
    () => t(T)
  );
  function z(r) {
    if (!r)
      return;
    const e = { part: g(), ...r.props };
    return { component: gt, ...r, props: e };
  }
  function G(r, e) {
    if (!r)
      return;
    const { label: o } = r;
    return {
      ...r,
      label: lt(o, e, e.busy)
    };
  }
  const h = i(() => G(t(M), t(L))), v = new it(0);
  P(() => {
    v.set(t(h) ? 1 : 0, { instant: !t(y) });
  });
  let C = A(void 0);
  P(() => {
    t(h) && c(C, { ...t(h) });
  });
  function J(r) {
    return !t(n).at(-1) ? !1 : t(n).at(-1)?.props.icon !== r.props.icon;
  }
  function Q(r) {
    if (!t(n).length)
      return !1;
    const { props: e } = t(n).at(-1), { props: o } = r;
    return e.icon === o.icon && e.title === o.title && e.label === o.label && e.onclick.toString() === o.onclick.toString();
  }
  let n = A([]);
  P(() => {
    if (!(!a.current && !t(n).length)) {
      if (!a.current) {
        c(n, []);
        return;
      }
      tt(() => {
        if (Q(a.current))
          return c(n, t(n).map((e) => e.key === a.current.key ? a.current : e));
        const r = J(a.current);
        c(n, t(n).map((e) => ({
          ...e,
          props: {
            ...e.props,
            inert: !0,
            autofocus: !1,
            dataset: { state: r ? "outro" : "idle" }
          }
        })).filter((e, o, s) => o > s.length - 2)), c(n, [
          ...t(n),
          {
            ...a.current,
            props: {
              ...a.current.props,
              inert: r,
              autofocus: f,
              dataset: { state: r ? "intro" : "idle" }
            }
          }
        ]), r && requestAnimationFrame(() => {
          c(n, t(n).map((e, o, s) => ({
            ...e,
            props: {
              ...e.props,
              inert: o < s.length - 1,
              autofocus: f,
              dataset: { state: o < s.length - 1 ? "outro" : "idle" }
            }
          })));
        });
      });
    }
  });
  const k = i(() => t(n).length ? [
    {
      tag: "element-stack",
      attrs: {
        layout: "pile",
        class: "button-pile",
        part: `${g()}-pile`
      },
      children: t(n)
    }
  ] : []);
  let f = !1;
  X(() => {
    if (!p)
      return;
    const r = [
      w(p, "focusin", () => {
        f = !0;
      }),
      w(p, "focusout", () => {
        f = !1;
      })
    ];
    return () => {
      r.forEach((e) => e());
    };
  }), mt(N, {
    tag: "entry-activity-indicator",
    get class() {
      return O();
    },
    subtag: "element-stack",
    subattrs: { layout: "pile" },
    onroot: (r) => p = r,
    get part() {
      return j();
    },
    get enableAnimations() {
      return t(y);
    },
    get springDefaults() {
      return t(R);
    },
    children: (r, e) => {
      var o = ht(), s = rt(o);
      {
        var _ = (u) => {
          dt(u, D(
            {
              get nodes() {
                return t(k);
              }
            },
            () => l.nodeContext
          ));
        };
        I(s, (u) => {
          t(k).length && u(_);
        });
      }
      var S = et(s);
      {
        var U = (u) => {
          var m = yt();
          let x;
          var W = ot(m);
          bt(W, D(() => t(C), {
            get enableAnimations() {
              return t(y);
            }
          })), Y(() => {
            nt(m, "part", `${g()}-pile`), x = st(m, "", x, { opacity: v.current });
          }), E(u, m);
        };
        I(S, (u) => {
          v.current > 0 && u(U);
        });
      }
      E(r, o);
    },
    $$slots: { default: !0 }
  }), Z();
}
export {
  Gt as default
};
