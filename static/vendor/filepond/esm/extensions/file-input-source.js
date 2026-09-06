/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { getAsElement as v, addListener as b } from "../utils/dom.js";
import { createExtension as I } from "./common/createExtension.js";
import { noop as h } from "../utils/placeholder.js";
import { warn as E } from "../common/console.js";
import { mapTree as g } from "../utils/tree.js";
const L = I({
  name: "FileInputSource",
  type: "source",
  props: {
    element: void 0,
    resetFilesOnAdd: !1,
    insertIndex: 0,
    preventAddEntries: void 0,
    // source label and icon to use
    sourceIcon: "device",
    sourceLabel: void 0
  },
  factory: ({ didSetProps: d, props: c }, { insertEntries: u, removeEntries: f, setExtensionState: m }) => {
    let i, e, s, r;
    function a() {
      const { insertIndex: t, resetFilesOnAdd: o } = c;
      s && f(s);
      const n = g(Array.from(e.files ?? []), (p) => ({
        src: p,
        origin: "input"
      }));
      s = n, u(n, t > -1 ? t : void 0), o && (e.files = new DataTransfer().files);
    }
    function l() {
      const { sourceLabel: t, sourceIcon: o } = c, n = !e.hasAttribute("data-readonly");
      m({
        source: n ? {
          type: "browse",
          label: t,
          icon: o,
          onclick: () => {
            e.click();
          }
        } : void 0
      });
    }
    return d(({ element: t, preventAddEntries: o }) => {
      if (!t)
        return;
      const n = v(t);
      n || E(`FileInputSource: HTMLInputElement not found ${t}`), e !== n && (i?.(), i = void 0, r || (r = new MutationObserver(() => {
        l();
      })), r.disconnect(), r.observe(n, { attributeFilter: ["data-readonly"] }), e = n), e.disabled = o, i = e ? b(e, "change", a) : h, e.files?.length || Promise.resolve().then(a), l();
    }), {
      destroy() {
        r?.disconnect(), i?.();
      }
    };
  }
});
export {
  L as FileInputSource
};
