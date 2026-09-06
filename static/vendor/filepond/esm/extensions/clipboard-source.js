/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { addListener as u } from "../utils/dom.js";
import { createExtension as m } from "./common/createExtension.js";
const v = m({
  name: "ClipboardSource",
  type: "source",
  props: {
    shouldHandlePaste: () => !0,
    preventAddEntries: void 0
  },
  factory: ({ props: o, didSetProps: n }, { insertEntries: a, setExtensionState: i }) => {
    let t;
    function s(e) {
      const { shouldHandlePaste: d, preventAddEntries: p } = o;
      if (p || !e.clipboardData || !d(e))
        return;
      const { items: c, files: r } = e.clipboardData;
      (!r || !r.length) && ![...c].some((l) => l.kind === "file") || (e.preventDefault(), e.stopPropagation(), a({
        src: e.clipboardData,
        origin: "clipboard"
      }));
    }
    return n(() => {
      t?.(), t = u(document.documentElement, "paste", s), i({
        source: {
          type: "paste"
        }
      });
    }), {
      destroy: () => {
        t?.();
      }
    };
  }
});
export {
  v as ClipboardSource
};
