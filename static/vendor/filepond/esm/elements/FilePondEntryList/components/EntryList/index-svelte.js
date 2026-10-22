/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as t } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { pop as pt, push as yt } from "../../../../vendor/svelte/src/internal/client/context.js";
import { first_child as T, sibling as Dt, only_child as vt } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { set as _, state as L } from "../../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_effect as B, template_effect as It } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as r } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as St } from "../../../../vendor/svelte/src/internal/client/render.js";
import { snippet as xt } from "../../../../vendor/svelte/src/internal/client/dom/blocks/snippet.js";
import { comment as J, append as M, from_html as _t } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as Et } from "../../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { each as Ct } from "../../../../vendor/svelte/src/internal/client/dom/blocks/each.js";
import { set_attribute as k } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_style as bt } from "../../../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { proxy as zt } from "../../../../vendor/svelte/src/internal/client/proxy.js";
import { bind_this as wt } from "../../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { sizeFromRect as Rt } from "../../../../utils/size.js";
import { SvelteMap as Pt } from "../../../../vendor/svelte/src/reactivity/map.js";
import { vectorAdd as Tt, vectorCreate as K } from "../../../../utils/vector.js";
import { getAppContext as Lt } from "../../contexts/appContext.js";
import { getDragContext as Mt } from "../../contexts/dragContext.js";
import { getDropContext as kt } from "../../contexts/dropContext.js";
import { getUniqueId as At } from "../../../../utils/string.js";
var Ft = _t('<ul role="list" class="entry-list"></ul> <div class="implicit"> </div>', 1);
function oe(N, g) {
  yt(g, !0);
  const Q = r(() => g.part), D = Lt(), X = r(() => D.locale), Y = r(() => D.enableDrag), A = r(() => D.updateEntryPlaceholderRect), Z = Mt(), s = r(() => Z.current), u = r(() => t(s) ? t(s).index : -1), E = r(() => t(s) ? t(s).id : null), F = r(() => t(s) ? t(s).outside : !1), W = r(() => !!t(s)), $ = kt(), v = r(() => $.current), C = r(() => t(v) ? t(v).id : null), b = r(() => t(v) ? t(v).remove : null);
  let q = L(void 0);
  B(() => {
    if (!t(W))
      return;
    const e = g.entries[t(u)];
    e && _(q, e.id);
  });
  function z(e) {
    return D.retainedEntries.find(({ entry: i }) => i.id === e);
  }
  const I = zt(new Pt());
  function tt(e, i, n) {
    I.set(e, { index: i, rect: n });
  }
  let h = L(void 0);
  B(() => {
    if (!t(W)) {
      _(h, void 0);
      return;
    }
    if (t(h))
      return;
    const e = g.entries[t(u)];
    if (!e)
      return;
    const { rect: i } = I.get(e.id) ?? {};
    i && _(h, { ...i });
  });
  function et(e, i, n, c) {
    const a = K(
      e.width > 0 ? n.x / e.width * (t(h).width - i.width) : 0,
      e.height > 0 ? n.y / e.height * (e.height - i.height) : 0
    );
    return K(c.x + (e.x - i.x) + a.x, c.y + (e.y - i.y) + a.y);
  }
  let S = null;
  const rt = r(() => {
    const e = g.entries.find((y, R) => t(u) === R);
    if (!e)
      return;
    const i = e.id, n = !!z(i), c = t(s)?.translation, a = i === t(E), p = n && t(b) && i === t(C);
    let { rect: l } = I.get(i) ?? {};
    const m = l !== void 0, f = t(h) !== void 0;
    let o;
    return c && !a && m && f ? (o = et(t(h), l, t(s).offset, t(s).translation), o = Tt(o, t(s).parentTranslation), S = { ...o }) : p && S && (o = { ...S }), o;
  }), w = /* @__PURE__ */ new WeakMap(), d = r(() => {
    let e = null;
    return { entries: g.entries.map((n, c) => {
      const a = n.id, p = c === t(u), m = !!z(a) && t(b) && a === t(C), f = p && t(F) || m;
      let { rect: o } = I.get(a) ?? {};
      if (o && f && (e = Rt(o)), w.has(n))
        return w.get(n);
      const y = { id: a, ariaId: `entry-${a}`, entry: n };
      return w.set(n, y), y;
    }), detachedItemSize: e };
  });
  let x = L(void 0);
  const nt = r(() => t(u) > -1), G = r(() => t(x) && t(nt) ? getComputedStyle(t(x)) : void 0), it = r(() => !!t(G)), ot = r(() => t(it) ? parseFloat(t(G).getPropertyValue("gap")) : 0), H = `aria-drag-description-${At()}`, at = r(() => t(d).detachedItemSize ? `${t(d).detachedItemSize?.height + (t(d).entries.length > 1 ? t(ot) : 0)}px` : null), st = r(() => t(d).detachedItemSize ? `${t(d).detachedItemSize?.width}px` : null), dt = r(() => t(d).detachedItemSize ? `${t(d).detachedItemSize?.height}px` : null);
  function ct(e, i, n) {
    if (e === t(E)) {
      t(A)(n);
      return;
    }
    if (n) {
      tt(e, i, n);
      return;
    }
    t(A)();
  }
  var O = J(), lt = T(O);
  {
    var mt = (e) => {
      var i = Ft(), n = T(i);
      let c;
      Ct(n, 23, () => t(d).entries, ({ id: l, ariaId: m, entry: f }) => l, (l, m, f) => {
        let o = () => t(m).id, y = () => t(m).ariaId, R = () => t(m).entry;
        const P = r(() => t(f) === t(u)), U = r(() => !!z(o())), V = r(() => !!(t(U) && t(b) && o() === t(C))), gt = r(() => t(P) && t(F) || t(V)), ft = r(() => t(q) === o()), ut = r(() => o() === t(E));
        var j = J(), ht = T(j);
        xt(ht, () => g.children, () => ({
          id: o(),
          index: t(f),
          isPlaceholder: t(ut),
          entry: R(),
          ariaId: y(),
          isDraggable: t(Y),
          isDetached: t(gt),
          isRemoving: t(U),
          isDragging: t(P),
          isLastDraggedItem: t(ft),
          translation: t(P) ? t(rt) : t(V) ? S : void 0,
          onmeasureitem: ct
        })), M(l, j);
      }), wt(n, (l) => _(x, l), () => t(x));
      var a = Dt(n, 2), p = vt(a, !0);
      It(() => {
        k(n, "aria-describedby", H), k(n, "part", t(Q)), c = bt(n, "", c, {
          "--_detached-entry-spacing": t(at),
          "--_detached-entry-width": t(st),
          "--_detached-entry-height": t(dt)
        }), k(a, "id", H), St(p, t(X).ariaDragDescription);
      }), M(e, i);
    };
    Et(lt, (e) => {
      t(d).entries.length && e(mt);
    });
  }
  M(N, O), pt();
}
export {
  oe as default
};
