/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { arrayRemoveFalsy as q } from "../../utils/array.js";
import { addListener as h } from "../../utils/dom.js";
import { pubsub as P } from "../../utils/pubsub.js";
import { isFunction as R } from "../../utils/test.js";
import { createExtension as V } from "./createExtension.js";
function B(y) {
  const { name: g, props: v, factory: x } = y;
  return V({
    name: g,
    type: "source",
    props: {
      // disabled state
      disabled: void 0,
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
        autofocus: !0,
        autocomplete: "off"
      },
      // overwrite with custom props
      ...v
    },
    factory: (S, c) => {
      const { pub: m, on: E } = P(), { didSetProps: w, props: i } = S, { setExtensionState: I, getExtensionState: A, insertEntries: D } = c, { createSourceTemplate: F, destroy: L } = x(
        S,
        {
          ...c,
          setExtensionSourceState: (e) => {
            const t = A()?.source;
            c.setExtensionState({
              source: {
                ...t,
                ...e
              }
            });
          },
          // @ts-ignore listen for events
          on: (e, t) => e.startsWith("dialog") ? E(e, t) : c.on(e, t)
        }
      );
      let d, a, b;
      w(({ sourceIcon: e, sourceLabel: t, sourceType: r, disabled: n }) => {
        I({
          // is adds source button
          source: {
            type: r,
            label: t,
            icon: e,
            disabled: n,
            onopen: T,
            onopened: C,
            onclosed: N
          }
        });
      });
      function O(e) {
        const { inputAttributes: t, insertIndex: r, beforeInsertSource: n } = i, { target: l } = e, f = l ? new FormData(l) : null;
        if (!f)
          throw e.preventDefault(), new Error("No form reference");
        const s = f.getAll(t.name);
        if (!s.length)
          throw e.preventDefault(), new Error(
            `No values found for input with name "${t.name}"`
          );
        const p = q(
          s.map((u) => {
            if (R(n)) {
              let o = n(u, i);
              return o ? { src: o } : void 0;
            }
            return { src: u };
          })
        );
        if (!p.length) {
          e.preventDefault();
          return;
        }
        D(p, r);
      }
      function T({
        dialog: e,
        setDialogContentTemplate: t,
        setDialogImportButtonCount: r
      }) {
        const { inputAttributes: n } = i;
        d = d || F(n), t(d, i), m("dialogOpen", e), a = h(e, "submit", O), b = h(
          e,
          "change",
          (l) => {
            const { target: f } = l, { name: s, validity: p, value: u } = f;
            if (s !== n.name)
              return;
            let o = 0;
            p.valid && (u instanceof FormData ? o = u.getAll(s).length : o = 1), r(o);
          }
        );
      }
      function C({ dialog: e }) {
        m("dialogOpened", e);
      }
      function N({
        dialog: e,
        setDialogContentTemplate: t,
        setDialogImportButtonCount: r
      }) {
        m("dialogClosed", e), a?.(), a = null, b?.(), b = null, e?.querySelector("form")?.reset(), t(null), r(0);
      }
      return {
        destroy() {
          L?.(), a?.();
        }
      };
    }
  });
}
export {
  B as createSourceExtension
};
