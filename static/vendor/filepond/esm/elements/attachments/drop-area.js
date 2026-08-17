/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { addListener as P, dispatchCustomEvent as x } from "../../utils/dom.js";
import { debounce as y } from "../../utils/debounce.js";
import { getUniqueId as X } from "../../utils/string.js";
import { vectorCreate as o } from "../../utils/vector.js";
import { isObjectValuesEqual as Y } from "../../utils/object.js";
import { noop as w } from "../../utils/placeholder.js";
function I(u = {}) {
  const { disabled: f } = u;
  return (m) => {
    let d = 0, p, r, i, n, l, c;
    const g = () => {
      d = 0, r = void 0, i = void 0, l = void 0, n = void 0;
    }, s = (t) => {
      if (i = o(t.clientX, t.clientY), !r || !n)
        return;
      const e = o(
        i.x - r.x,
        i.y - r.y
      );
      l = o(
        e.x - n.x,
        e.y - n.y
      ), n = e, c = {
        clientX: t.clientX,
        clientY: t.clientY,
        type: t.type
      };
    }, a = (t, e) => {
      if (f)
        return;
      const v = {
        id: p,
        element: void 0,
        translation: { ...n },
        offset: o(0, 0),
        startPosition: { ...r },
        viewPosition: { ...i },
        vector: { ...l },
        dataTransfer: e
      };
      (u[`on${t}`] ?? w)(v), x(m, t, {
        detail: v
      });
    }, D = (t) => {
      t.preventDefault(), !(d++ > 0) && (p = X(), n = o(), r = o(t.pageX, t.pageY), s(t), a("itemdragin"));
    }, h = (t) => {
      t.preventDefault(), !(--d > 0) && (s(t), a("itemdragout"));
    }, E = y(
      (t) => {
        c && Y(c, t) || (s(t), a("itemdrag"));
      },
      {
        beforeDebounce: (t) => {
          t.preventDefault(), t.stopPropagation();
        },
        // can't push forward events
        runLast: !1
      }
    ), b = Object.entries({
      // enter and leave drop area
      dragenter: D,
      dragleave: h,
      // handle dragover only (drag pageX and pageY is 0 on Firefox)
      dragover: E,
      // a file was dropped
      drop: (t) => {
        const e = t.defaultPrevented;
        t.preventDefault(), s(t), e ? a("itemdropcancel") : a("itemdrop", t.dataTransfer), g();
      }
    }).map(
      ([t, e]) => P(document.documentElement, t, e)
    );
    return () => {
      b.forEach((t) => t());
    };
  };
}
export {
  I as dropArea
};
