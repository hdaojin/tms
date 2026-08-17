/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { getAsElement as f } from "../utils/dom.js";
import { isFileEntry as l } from "../utils/test.js";
import { createExtension as E } from "./common/createExtension.js";
import { debounce as d } from "../utils/debounce.js";
import { warn as c } from "../common/console.js";
const S = E({
  name: "TextInputStore",
  type: "store",
  props: {
    element: void 0
  },
  factory: ({ props: o, didSetProps: i }, { on: s }) => {
    let t;
    i(({ element: e }) => {
      t = f(e), t.type !== "text" && (t = void 0), (!t || t.type !== "text") && c(`TextInputStore: HTMLInputElement not found ${e}`);
    });
    function p(e) {
      const { targetElement: r } = o;
      if (!r || !e.every(l))
        return;
      const n = e.filter((u) => !Object.values(u.extensionState ?? {}).some((a) => a.status?.type === "error"));
      r.value = n.length ? JSON.stringify(n) : "";
    }
    const m = s("updateEntries", d(p));
    return {
      destroy: () => {
        m();
      }
    };
  }
});
export {
  S as TextInputStore
};
