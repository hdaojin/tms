/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { arrayRemoveFalsy as C } from "../../utils/array.js";
import { setAttributes as P, addListener as T } from "../../utils/dom.js";
import { pubsub as R } from "../../utils/pubsub.js";
import { isFunction as V } from "../../utils/test.js";
import { createExtension as W } from "./createExtension.js";
function G(y) {
  const { name: E, props: h, factory: x } = y;
  return W({
    name: E,
    type: "source",
    props: {
      // by default insert to top of list
      insertIndex: 0,
      // source label and icon locale keys to use in sourcelist
      sourceIcon: void 0,
      sourceIconError: void 0,
      sourceLabel: void 0,
      sourceType: "select",
      // default input name to use
      inputAttributes: {
        name: "value",
        required: !0,
        autofocus: "",
        autocomplete: "off"
      },
      // overwrite with custom props
      ...h
    },
    factory: (a, n) => {
      const { pub: u, on: g } = R(), { didSetProps: v, props: c } = a, { setExtensionState: I, getExtensionState: w, insertEntries: A } = n, { createSourceElement: D, destroy: F } = x(
        a,
        {
          ...n,
          setExtensionSourceState: (e) => {
            const t = w()?.source;
            n.setExtensionState({
              source: {
                ...t,
                ...e
              }
            });
          },
          // @ts-ignore listen for events
          on: (e, t) => e.startsWith("dialog") ? g(e, t) : n.on(e, t)
        }
      );
      let o, r, s;
      v(({ sourceIcon: e, sourceLabel: t, sourceType: i }) => {
        I({
          // is adds source button
          source: {
            type: i,
            label: t,
            icon: e,
            onopen: O,
            onopened: N,
            onclosed: q
          }
        });
      });
      function L(e) {
        const { inputAttributes: t, insertIndex: i, beforeInsertSource: l } = c, { target: p } = e, f = p ? new FormData(p) : null;
        if (!f)
          throw e.preventDefault(), new Error("No form reference");
        const m = f.getAll(t.name);
        if (!m.length)
          throw e.preventDefault(), new Error(
            `No values found for input with name "${t.name}"`
          );
        const d = C(
          m.map((S) => {
            if (V(l)) {
              let b = l(S, c);
              return b ? { src: b } : void 0;
            }
            return { src: S };
          })
        );
        if (!d.length) {
          e.preventDefault();
          return;
        }
        A(d, i);
      }
      function O(e) {
        const { inputAttributes: t } = c;
        r = e, o = o || D(), P(o, t), r.append(o), u("dialogOpen", e), s = T(r, "submit", L);
      }
      function N(e) {
        u("dialogOpened", e);
      }
      function q() {
        u("dialogClosed", r), s?.(), s = null, r?.querySelector("form")?.reset(), o.remove(), r = null;
      }
      return {
        destroy() {
          F?.(), s?.();
        }
      };
    }
  });
}
export {
  G as createSourceExtension
};
