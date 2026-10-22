/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as e, untrack as ye } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as be, push as he } from "../../../../vendor/svelte/src/internal/client/context.js";
import { first_child as De } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { set as b, state as h } from "../../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_derived as t } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { comment as ve, append as Pe } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { snippet as Re } from "../../../../vendor/svelte/src/internal/client/dom/blocks/snippet.js";
import { bind_window_size as N } from "../../../../vendor/svelte/src/internal/client/dom/elements/bindings/window.js";
import { prop as a, spread_props as Ee } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { rectIntersectWithRect as Oe, rectCreate as Ie } from "../../../../utils/rect.js";
import { setEntryContext as Se } from "../../contexts/entryContext.js";
import Ae from "../../../components/SpringElement/index-svelte.js";
import { toSpaceSeparatedString as _e } from "../../../common/string.js";
import { getAppContext as T } from "../../contexts/appContext.js";
import { VIEWPORT_MARGIN as we } from "../../../attachments/measurable.js";
import { noop as D } from "../../../../utils/placeholder.js";
import { isNumber as z } from "../../../../utils/test.js";
function Je(L, r) {
  he(r, !0);
  let W = a(r, "tag", 3, "li"), j = a(r, "isDetached", 3, !1), F = a(r, "isRemoving", 3, !1), H = a(r, "isDraggable", 3, !0), V = a(r, "isDragging", 3, !1), Y = a(r, "isLastDraggedItem", 3, !1), g = a(r, "translation", 7);
  const k = t(Y), m = t(V), v = t(j), P = t(F), R = t(H), E = t(() => r.ariaDescribedby), d = t(() => r.entry), O = t(T), B = t(() => e(O).animatedEntries), I = t(() => e(O).entryAnimationProps), u = Object.freeze({ onspringcancel: D, onspringcomplete: D });
  function G(n) {
    const { animation: i, delayed: c, oncancel: s, oncomplete: l } = e(B)[n.id] ?? {};
    if (!e(I)[i])
      return u;
    const {
      scale: se,
      opacity: de,
      translation: ce,
      opacityFrom: w,
      scaleFrom: M,
      translationFrom: C,
      translationSpringOptions: le,
      scaleSpringOptions: ge,
      opacitySpringOptions: me
    } = e(I)[i], o = {
      scale: void 0,
      opacity: void 0,
      translation: void 0,
      translationSpringOptions: le,
      scaleSpringOptions: ge,
      opacitySpringOptions: me,
      onspringcancel() {
        s();
      },
      onspringcomplete({ opacity: ue, scale: pe }) {
        const x = z(o.opacity) ? o.opacity === ue : !0;
        if (x && o.opacity === 0) {
          l();
          return;
        }
        const fe = z(o.scale) ? o.scale === pe : !0;
        x && fe && l();
      }
    };
    return c ? Object.assign(o, {
      opacityFrom: w,
      scaleFrom: M,
      translationFrom: C,
      onspringcomplete: D
    }) : Object.assign(o, {
      opacityFrom: w,
      scaleFrom: M,
      translationFrom: C,
      scale: se,
      opacity: de,
      translation: ce
    });
  }
  const q = t(() => {
    const n = G(e(d));
    if (n === u)
      return;
    ye(() => {
      g(g() || n.translation);
    });
    const {
      // not interested in these props
      translation: i,
      onspringcancel: c,
      // capture rest of props
      ...s
    } = n;
    return s;
  });
  function J(n) {
    r.onmeasureitem(r.id, r.index, n);
  }
  Se({
    get current() {
      return e(d);
    },
    get ariaId() {
      return `entry-${e(d).id}`;
    }
  });
  const K = t(() => ({ id: e(d).id, entry: e(d) })), p = t(T), Q = t(() => e(p).locale), U = t(() => e(p).reduceMotion), X = t(() => e(p).springOptions);
  let f = h(void 0), y = h(void 0);
  const S = we, Z = t(() => !!(e(f) && e(y))), $ = t(() => e(Z) ? Ie(0, -S, e(f), e(y) + S * 2) : void 0);
  function ee(n, i, c) {
    return !n || !i ? !1 : c ? !0 : Oe(n, i);
  }
  let A = h(void 0);
  function te(n) {
    b(A, n);
  }
  const _ = t(() => !ee(e(A), e($), e(v))), ne = t(() => _e(r.part, e(_) ? "virtualized" : void 0, e(m) ? "dragging" : void 0)), re = t(() => ({
    // Makes it possible to drag this item
    draggable: e(R) ? "" : void 0,
    // Detach so doesn't take up room in list
    detached: e(v) ? "" : void 0,
    // When true will prevent hover effects on elements in subtree
    dragging: e(m) ? "" : void 0,
    // When set to true will increase z-index so renders above other items
    renderAbove: e(k) ? "" : void 0,
    // When set to true will decrease z-index so renders below other items
    renderBelow: e(P) ? "" : void 0
  })), ie = t(() => e(R) ? {
    tabindex: 0,
    role: "listitem",
    "aria-roledescription": e(Q).ariaItemRoleDescription,
    "aria-describedby": e(E)
  } : { role: "listitem", "aria-describedby": e(E) });
  function oe(n) {
    e(m) && n.focus({
      preventScroll: !0,
      // @ts-ignore, we hide the focus ring because it looks horrible on mobile devices, when a user drags the item with keyboard interaction it should be clear from the item being lifted that the item has focus.
      focusVisible: !1
    });
  }
  var ae = { EMPTY_ENTRY_ANIMATION: u };
  {
    let n = t(() => !e(_));
    Ae(L, Ee(
      {
        get id() {
          return r.id;
        },
        get tag() {
          return W();
        },
        get part() {
          return e(ne);
        },
        get dataset() {
          return e(re);
        },
        get attrs() {
          return e(ie);
        },
        get class() {
          return r.class;
        },
        get inert() {
          return e(P);
        }
      },
      () => e(q),
      {
        get translation() {
          return g();
        },
        get shouldRenderChildren() {
          return e(n);
        },
        onroot: oe,
        onelementmeasure: J,
        onmeasureabsoluterect: te,
        get reduceMotion() {
          return e(U);
        },
        get springOptions() {
          return e(X);
        },
        children: (i, c) => {
          var s = ve(), l = De(s);
          Re(l, () => r.children, () => e(K)), Pe(i, s);
        },
        $$slots: { default: !0 }
      }
    ));
  }
  return N("innerWidth", (n) => b(f, n)), N("innerHeight", (n) => b(y, n)), be(ae);
}
export {
  Je as default
};
