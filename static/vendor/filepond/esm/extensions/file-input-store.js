/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { debounce as l } from "../utils/debounce.js";
import { createExtension as f } from "./common/createExtension.js";
import { getAsElement as m, setFileInputFilesFromEntries as d } from "../utils/dom.js";
import { isFileEntry as E } from "../utils/test.js";
import { warn as c } from "../common/console.js";
const U = f({
  name: "FileInputStore",
  type: "store",
  props: {
    element: void 0,
    // the event fired on the element when it's updated, defaults to 'update'
    valueChangeEvent: "fileschange"
  },
  factory: ({ props: r, didSetProps: o }, { on: i }) => {
    let e;
    o(({ element: t }) => {
      e = m(t), e?.type !== "file" && (e = null), t && (!e || e.type !== "file") && c(`FileInputStore: HTMLInputElement not found ${t}`);
    });
    function s(t) {
      if (!e || !t.every(E))
        return;
      const { valueChangeEvent: u } = r;
      d(
        e,
        // @ts-ignore we know these are file entries
        t.filter((n) => n.extensionState ? !Object.values(n.extensionState).some((a) => a.status?.type === "error") : !0)
      ) && e.dispatchEvent(new CustomEvent(u));
    }
    const p = i("updateEntries", l(s));
    return {
      destroy: () => {
        p();
      }
    };
  }
});
export {
  U as FileInputStore
};
