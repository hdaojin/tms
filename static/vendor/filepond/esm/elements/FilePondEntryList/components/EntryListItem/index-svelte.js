/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as t } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as M, push as P } from "../../../../vendor/svelte/src/internal/client/context.js";
import { first_child as B } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { set as g, state as l } from "../../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_derived as n } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { comment as G, append as N } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { snippet as O } from "../../../../vendor/svelte/src/internal/client/dom/blocks/snippet.js";
import { bind_window_size as y } from "../../../../vendor/svelte/src/internal/client/dom/elements/bindings/window.js";
import { prop as i, spread_props as T } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { rectIntersectWithRect as j, rectCreate as k } from "../../../../utils/rect.js";
import { setEntryContext as q } from "../../contexts/entryContext.js";
import F from "../../../components/SpringElement/index-svelte.js";
import { toSpaceSeparatedString as J } from "../../../common/string.js";
import { getAppContext as p } from "../../contexts/appContext.js";
import { VIEWPORT_MARGIN as K } from "../../../attachments/measurable.js";
function ge(R, e) {
  P(e, !0);
  let w = i(e, "tag", 3, "li"), m = i(e, "isDetached", 3, !1), u = i(e, "isRemoving", 3, !1), f = i(e, "isDraggable", 3, !0), a = i(e, "isDragging", 3, !1), I = i(e, "isLastDraggedItem", 3, !1);
  q({
    get current() {
      return e.entry;
    },
    get ariaId() {
      return `entry-${e.entry.id}`;
    }
  }), p();
  const o = n(p), A = n(() => t(o).locale), C = n(() => t(o).enableAnimations), _ = n(() => t(o).springDefaults);
  let d = l(void 0), s = l(void 0);
  const c = K, S = n(() => !!(t(d) && t(s))), b = n(() => t(S) ? k(0, -c, t(d), t(s) + c * 2) : void 0);
  let h = l(!1);
  const x = n(() => J(e.part, t(h) ? "virtualized" : void 0, a() ? "dragging" : void 0));
  function E(r) {
    g(h, !r);
  }
  function W(r, D) {
    return !r || !t(b) || D ? !0 : j(r, t(b));
  }
  const z = n(() => ({
    // Makes it possible to drag this item
    draggable: f() ? "" : void 0,
    // Detach so doesn't take up room in list
    detached: m() ? "" : void 0,
    // When true will prevent hover effects on elements in subtree
    dragging: a() ? "" : void 0,
    // When set to true will increase z-index so renders above other items
    renderAbove: I() ? "" : void 0,
    // When set to true will decrease z-index so renders below other items
    renderBelow: u() ? "" : void 0
  })), H = n(() => f() ? {
    tabindex: 0,
    role: "listitem",
    "aria-roledescription": t(A).ariaItemRoleDescription,
    "aria-describedby": e.ariaDescribedby
  } : {
    role: "listitem",
    "aria-describedby": e.ariaDescribedby
  });
  function L(r) {
    a() && r.focus({
      preventScroll: !0,
      // @ts-ignore, we hide the focus ring because it looks horrible on mobile devices, when a user drags the item with keyboard interaction it should be clear from the item being lifted that the item has focus.
      focusVisible: !1
    });
  }
  F(R, T(
    {
      get tag() {
        return w();
      },
      get part() {
        return t(x);
      },
      get dataset() {
        return t(z);
      },
      get attrs() {
        return t(H);
      },
      get class() {
        return e.class;
      },
      get inert() {
        return u();
      }
    },
    () => e.springAnimation,
    {
      get translation() {
        return e.translation;
      },
      shouldRenderContent: (r) => W(r, m()),
      onroot: L,
      onchangerendercontent: E,
      get onelementmeasure() {
        return e.onmeasureitem;
      },
      get enableAnimations() {
        return t(C);
      },
      get springDefaults() {
        return t(_);
      },
      children: (r, D) => {
        var v = G(), V = B(v);
        O(V, () => e.children, () => ({ id: e.entry.id, entry: e.entry })), N(r, v);
      },
      $$slots: { default: !0 }
    }
  )), y("innerWidth", (r) => g(d, r)), y("innerHeight", (r) => g(s, r)), M();
}
export {
  ge as default
};
