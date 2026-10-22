/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { addListener as y, dispatchCustomEvent as w } from "../../utils/dom.js";
import { debounce as X } from "../../utils/debounce.js";
import { getUniqueId as Y } from "../../utils/string.js";
import { vectorCreate as o } from "../../utils/vector.js";
import { isObjectValuesEqual as C } from "../../utils/object.js";
import { noop as L } from "../../utils/placeholder.js";
function U(u = {}) {
  const { disabled: m, willAcceptDrop: g } = u;
  return (D) => {
    let s = 0, p, r, i, n, d, c;
    const E = () => {
      s = 0, r = void 0, i = void 0, d = void 0, n = void 0;
    }, l = (t) => {
      if (i = o(t.clientX, t.clientY), !r || !n)
        return;
      const e = o(
        i.x - r.x,
        i.y - r.y
      );
      d = o(
        e.x - n.x,
        e.y - n.y
      ), n = e, c = {
        clientX: t.clientX,
        clientY: t.clientY,
        type: t.type
      };
    };
    function f(t = null) {
      return {
        id: p,
        element: void 0,
        translation: { ...n },
        offset: o(0, 0),
        startPosition: { ...r },
        viewPosition: { ...i },
        vector: { ...d },
        dataTransfer: t
      };
    }
    const a = (t, e) => {
      if (m)
        return;
      const v = f(e);
      (u[`on${t}`] ?? L)(v), w(D, t, {
        detail: v
      });
    }, h = (t) => {
      t.preventDefault(), !(s++ > 0) && (p = Y(), n = o(), r = o(t.pageX, t.pageY), l(t), a("itemdragin"));
    }, b = (t) => {
      t.preventDefault(), !(--s > 0) && (l(t), a("itemdragout"));
    }, P = X(
      (t) => {
        c && C(c, t) || (l(t), a("itemdrag"));
      },
      {
        beforeDebounce: (t) => {
          t.preventDefault(), t.stopPropagation();
        },
        // can't push forward events
        runLast: !1
      }
    ), x = Object.entries({
      // enter and leave drop area
      dragenter: h,
      dragleave: b,
      // handle dragover only (drag pageX and pageY is 0 on Firefox)
      dragover: P,
      // a file was dropped
      drop: (t) => {
        const e = t.defaultPrevented;
        l(t), g?.(f(t.dataTransfer)) && t.preventDefault(), e ? a("itemdropcancel") : a("itemdrop", t.dataTransfer), E();
      }
    }).map(
      ([t, e]) => y(document.documentElement, t, e)
    );
    return () => {
      x.forEach((t) => t());
    };
  };
}
export {
  U as dropArea
};
