/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { addListener as s, dispatchCustomEvent as B } from "../../utils/dom.js";
import { debounce as N } from "../../utils/debounce.js";
import { getUniqueId as $ } from "../../utils/string.js";
import { vectorCreate as p, vectorLengthSquared as j } from "../../utils/vector.js";
import { isElement as k } from "../../utils/test.js";
import { noop as z } from "../../utils/placeholder.js";
function Z(C = {}) {
  const {
    disabled: G = !1,
    grabTimeout: P = 300,
    grabIgnoreMoveDistance: U = 5,
    itemSelector: M = "li"
  } = C, g = document.documentElement;
  return (i) => {
    if (G)
      return;
    let b = !1;
    const A = s(
      g,
      "touchmove",
      (t) => {
        !t.cancelable || !b || t.preventDefault();
      },
      {
        passive: !1
      }
    );
    let n, o, c, u, h, v, d, a, f, r, D, w;
    const T = (t) => {
      b = !1, i.releasePointerCapture(t.pointerId), v = void 0, d = void 0, D = void 0, a = void 0, f = void 0, r = void 0, clearTimeout(h), n = n && n(), o = o && o(), c = c && c(), setTimeout(() => {
        u = u && u();
      }, 0);
    }, m = (t) => {
      if (f = p(t.clientX, t.clientY), !a || !r)
        return;
      const e = p(
        f.x - a.x,
        f.y - a.y
      );
      D = p(
        e.x - r.x,
        e.y - r.y
      ), r = e;
    }, l = (t) => {
      const e = {
        id: v,
        element: d,
        translation: { ...r },
        offset: { ...w },
        startPosition: { ...a },
        viewPosition: { ...f },
        vector: { ...D }
      }, x = C[`on${t}`] ?? z;
      x && x(e), B(i, t, {
        detail: e
      });
    };
    function L(t) {
      return t.target?.closest(M);
    }
    function q(t) {
      const { target: e } = t;
      if (!k(e) || !i.contains(e))
        return !1;
      const Y = t.composedPath().shift();
      return !/input|select|textarea|button/i.test(Y.nodeName);
    }
    const F = (t) => {
      if (t.button !== 0 || !q(t) || (d = L(t), !d))
        return;
      a = p(t.clientX, t.clientY);
      const e = d.getBoundingClientRect();
      if (w = p(a.x - e.x, a.y - e.y), r = p(), m(t), l("itemgrabattempt"), o && o(), o = s(g, "pointerup", y), n && n(), n = s(g, "pointermove", y), P <= 0) {
        E(t.pointerId);
        return;
      }
      clearTimeout(h), h = setTimeout(() => {
        E(t.pointerId);
      }, P);
    }, y = (t) => {
      m(t), !(t.type === "pointermove" && r && j(r) < U * U) && (o && o(), n && n(), l("itemgrabcancel"), T(t));
    }, E = (t) => {
      b = !0, i.setPointerCapture(t), o && o(), o = s(i, "pointerup", I), n && n(), n = s(i, "pointermove", S), c && c(), c = s(i, "pointercancel", R), u && u(), u = s(window, "pointerup", W), v = $(), l("itemgrab");
    }, R = (t) => {
      t.preventDefault(), m(t), l("itemdragcancel"), T(t);
    }, S = N(
      (t) => {
        m(t), l("itemdrag");
      },
      {
        beforeDebounce: (t) => {
          t.preventDefault(), t.stopPropagation();
        },
        // can't push forward events
        runLast: !1
      }
    ), I = (t) => {
      t.preventDefault(), m(t), l("itemdrop"), T(t);
    }, W = (t) => {
      v && I(t);
    }, X = s(i, "pointerdown", F);
    return () => {
      A(), X();
    };
  };
}
export {
  Z as dragArea
};
