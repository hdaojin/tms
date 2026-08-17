/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as s } from "./common/createExtension.js";
import { addListener as n } from "../utils/dom.js";
const f = s({
  name: "DragDropSource",
  type: "source",
  props: {
    shouldHandleDrop: () => !0
  },
  factory: ({ didSetProps: o, props: a }, { insertEntries: d }) => {
    let r, t;
    function u(e) {
      e.preventDefault();
    }
    async function p(e) {
      const { shouldHandleDrop: c } = a;
      !e.dataTransfer || !e.target || e.target.type === "file" || c(e) && (e.preventDefault(), d({
        src: e.dataTransfer,
        origin: "drop"
      }));
    }
    return o(() => {
      r?.(), t?.(), r = n(document.documentElement, "drop", p), t = n(
        document.documentElement,
        "dragover",
        u
      );
    }), {
      destroy: () => {
        r?.(), t?.();
      }
    };
  }
});
export {
  f as DragDropSource
};
