/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as f } from "./common/createExtension.js";
import { addListener as p } from "../utils/dom.js";
import { COMPONENT_PROPS as m } from "../elements/FilePondSourceList/index.js";
const v = f({
  name: "SourceListView",
  type: "view",
  props: {
    // set default props, we need to do this because extension manager uses it to determine if it can propagate props to this extension
    ...m.reduce((e, o) => (e[o] = void 0, e), {}),
    // what element the extension will set the dynamic source list to
    element: void 0,
    // we don't prevent entries by default
    preventAddEntries: void 0,
    // filters the sources, this is used to hide the browse button when no other sources are present
    filterSources: (e) => e.length === 1 && e[0].type === "browse" ? [] : e
  },
  factory: ({ props: e, didSetProps: o }, { on: d }) => {
    let c, r, i;
    o(
      ({
        element: n,
        preventAddEntries: s,
        ...t
      }) => {
        n && (r = n, Object.assign(r, {
          ...t,
          disabled: s
        }), u(), i?.(), i = p(r, "connected", () => {
          u();
        }));
      }
    );
    function u() {
      const { filterSources: n } = e;
      r.sources = n(c || []);
    }
    function a(n) {
      const { filterSources: s } = e;
      c = Object.values(n).filter(
        (t) => t?.source && (t?.source.icon || t?.source.label)
      ).map((t) => t?.source), r && (r.sources = s(c));
    }
    const l = d("updateExtensionState", a);
    return {
      destroy() {
        i?.(), l?.();
      }
    };
  }
});
export {
  v as SourceListView
};
