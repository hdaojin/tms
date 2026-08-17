/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { setAttributes as N, addListener as q } from "../../utils/dom.js";
import { pubsub as C } from "../../utils/pubsub.js";
import { isFunction as P } from "../../utils/test.js";
import { createExtension as T } from "./createExtension.js";
function z(S) {
  const { name: b, props: E, factory: x } = S;
  return T({
    name: b,
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
      ...E
    },
    factory: (a, n) => {
      const { pub: u, on: y } = C(), { didSetProps: h, props: p } = a, { setExtensionState: g, getExtensionState: v, insertEntries: I } = n, { createSourceElement: w, destroy: D } = x(
        a,
        {
          ...n,
          setExtensionSourceState: (e) => {
            const t = v()?.source;
            n.setExtensionState({
              source: {
                ...t,
                ...e
              }
            });
          },
          // @ts-ignore listen for events
          on: (e, t) => e.startsWith("dialog") ? y(e, t) : n.on(e, t)
        }
      );
      let o, r, s;
      h(({ sourceIcon: e, sourceLabel: t, sourceType: c }) => {
        g({
          // is adds source button
          source: {
            type: c,
            label: t,
            icon: e,
            onopen: L,
            onopened: O,
            onclosed: F
          }
        });
      });
      function A(e) {
        const { inputAttributes: t, insertIndex: c, beforeInsertSource: l } = p, { target: f } = e, m = f ? new FormData(f) : null;
        if (!m)
          throw e.preventDefault(), new Error("No form reference");
        const i = m.get(t.name);
        if (!i)
          throw e.preventDefault(), new Error(`No value for input with name "${t.name}"`);
        const d = P(l) ? l({ src: i }) : i;
        if (!d) {
          e.preventDefault();
          return;
        }
        I({ src: d }, c);
      }
      function L(e) {
        const { inputAttributes: t } = p;
        r = e, o = o || w(), N(o, t), r.append(o), u("dialogOpen", e), s = q(r, "submit", A);
      }
      function O(e) {
        u("dialogOpened", e);
      }
      function F() {
        u("dialogClosed", r), s?.(), s = null, r?.querySelector("form")?.reset(), o.remove(), r = null;
      }
      return {
        destroy() {
          D?.(), s?.();
        }
      };
    }
  });
}
export {
  z as createSourceExtension
};
