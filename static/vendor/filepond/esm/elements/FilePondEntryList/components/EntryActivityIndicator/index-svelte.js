/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onMount as Z } from "../../../../vendor/svelte/src/index-client.js";
import { user_effect as N, template_effect as $ } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { pop as tt, push as rt } from "../../../../vendor/svelte/src/internal/client/context.js";
import { get as t, untrack as et } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { first_child as ot, sibling as nt, child as st } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { set as p, state as L } from "../../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_derived as i } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as E, append as C } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as M } from "../../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { set_attribute as it } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_style as ut } from "../../../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { prop as d, spread_props as at } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { Spring as ct } from "../../../../vendor/svelte/src/motion/spring.js";
import { getExtensionStateByStatusCode as pt } from "../../../../common/entry.js";
import { isObjectValuesEqual as lt } from "../../../../utils/object.js";
import { getValueByKeyFromData as ft } from "../../../common/string.js";
import { getAppContext as mt } from "../../contexts/appContext.js";
import { getEntryContext as dt } from "../../contexts/entryContext.js";
import { gate as gt } from "../../../common/store-svelte.js";
import bt from "../../../components/SpringElement/index-svelte.js";
import "../../../components/Button/index.js";
import "../../../components/ProgressIndicator/index.js";
import Pt from "../../../components/NodeList/index-svelte.js";
import { addListener as O } from "../../../../utils/dom.js";
import yt from "../../../components/Button/index-svelte.js";
import vt from "../../../components/ProgressIndicator/index-svelte.js";
var ht = E("<div><!></div>"), _t = E("<!><!>", 1);
function Ut(I, s) {
  rt(s, !0);
  let R = d(s, "class", 3, void 0), w = d(s, "part", 3, void 0), A = d(s, "buttonPart", 3, void 0), F = d(s, "states", 19, () => []);
  const j = i(R), q = i(w), g = i(A);
  let l;
  const b = i(mt), V = i(() => t(b).locale), P = i(() => t(b).reduceMotion), D = i(() => t(b).springOptions), H = dt(), K = i(() => Object.values(H.current.extensionState));
  function T(r, e) {
    if (r.length) {
      for (const o of r) {
        const u = pt(e, o.codes);
        if (!u)
          continue;
        const h = o.button, _ = o.progress ? { ...o.progress, value: u.progress } : null;
        return { button: h, progress: _ };
      }
      return null;
    }
  }
  const S = i(() => T(F(), t(K))), z = i(() => t(S)?.progress), G = i(() => J(t(S)?.button)), a = gt(
    // should update value?
    (r, e) => r && e ? !lt(r.props, e.props) : r !== e,
    // $derived
    () => t(G)
  );
  function J(r) {
    if (!r)
      return;
    const e = { part: t(g), ...r.props };
    return { component: yt, ...r, props: e };
  }
  function Q(r, e) {
    if (!r)
      return;
    const { label: o } = r;
    return {
      ...r,
      label: ft(o, e, e.busy)
    };
  }
  const y = i(() => Q(t(z), t(V))), v = new ct(0);
  N(() => {
    v.set(t(y) ? 1 : 0, { instant: t(P) });
  });
  let k = L(void 0);
  N(() => {
    t(y) && p(k, { ...t(y) });
  });
  function U(r) {
    return !t(n).at(-1) ? !1 : t(n).at(-1)?.props.icon !== r.props.icon;
  }
  function W(r) {
    if (!t(n).length)
      return !1;
    const { props: e } = t(n).at(-1), { props: o } = r;
    return e.icon === o.icon && e.title === o.title && e.label === o.label && e.onclick.toString() === o.onclick.toString();
  }
  let n = L([]);
  N(() => {
    if (!(!a.current && !t(n).length)) {
      if (!a.current) {
        p(n, []);
        return;
      }
      et(() => {
        if (W(a.current))
          return p(n, t(n).map((e) => e.key === a.current.key ? a.current : e));
        const r = U(a.current);
        p(n, t(n).map((e) => ({
          ...e,
          props: {
            ...e.props,
            inert: !0,
            autofocus: !1,
            dataset: { state: r ? "outro" : "idle" }
          }
        })).filter((e, o, u) => o > u.length - 2)), p(n, [
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
          p(n, t(n).map((e, o, u) => ({
            ...e,
            props: {
              ...e.props,
              inert: o < u.length - 1,
              autofocus: f,
              dataset: { state: o < u.length - 1 ? "outro" : "idle" }
            }
          })));
        });
      });
    }
  });
  const B = i(() => t(n).length ? [
    {
      key: "entry-activity-indicator-buttons",
      tag: "element-stack",
      attrs: {
        layout: "pile",
        class: "button-pile",
        part: `${t(g)}-pile`
      },
      children: t(n)
    }
  ] : []);
  let f = !1;
  Z(() => {
    if (!l)
      return;
    const r = [
      O(l, "focusin", () => {
        f = !0;
      }),
      O(l, "focusout", () => {
        f = !1;
      })
    ];
    return () => {
      r.forEach((e) => e());
    };
  }), bt(I, {
    tag: "entry-activity-indicator",
    get class() {
      return t(j);
    },
    subtag: "element-stack",
    subattrs: { layout: "pile" },
    onroot: (r) => l = r,
    get part() {
      return t(q);
    },
    get reduceMotion() {
      return t(P);
    },
    get springOptions() {
      return t(D);
    },
    children: (r, e) => {
      var o = _t(), u = ot(o);
      {
        var h = (c) => {
          Pt(c, {
            get springOptions() {
              return s.subNodeListProps.springOptions;
            },
            get reduceMotion() {
              return s.subNodeListProps.reduceMotion;
            },
            get routes() {
              return s.subNodeListProps.routes;
            },
            get resources() {
              return s.subNodeListProps.resources;
            },
            get propResourceMap() {
              return s.subNodeListProps.propResourceMap;
            },
            get data() {
              return s.subNodeListProps.data;
            },
            get context() {
              return s.subNodeListProps.context;
            },
            get beforeRenderNode() {
              return s.subNodeListProps.beforeRenderNode;
            },
            get nodes() {
              return t(B);
            }
          });
        };
        M(u, (c) => {
          t(B).length && c(h);
        });
      }
      var _ = nt(u);
      {
        var X = (c) => {
          var m = ht();
          let x;
          var Y = st(m);
          vt(Y, at(() => t(k), {
            get reduceMotion() {
              return t(P);
            }
          })), $(() => {
            it(m, "part", `${t(g)}-pile`), x = ut(m, "", x, { opacity: v.current });
          }), C(c, m);
        };
        M(_, (c) => {
          v.current > 0 && c(X);
        });
      }
      C(r, o);
    },
    $$slots: { default: !0 }
  }), tt();
}
export {
  Ut as default
};
