/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as O } from "./common/createExtension.js";
import { addListener as P } from "../utils/dom.js";
import { COMPONENT_PROPS as g } from "../elements/FilePondEntryList/index.js";
const w = O({
  name: "EntryListView",
  type: "view",
  props: {
    // set default props, we need to do this because extension manager uses it to determine if it can propagate props to this extension
    ...g.reduce((n, r) => (n[r] = void 0, n), {}),
    // element reference
    element: void 0,
    // this toggles drop on the element
    preventAddEntries: void 0
  },
  factory: (n, r) => {
    const { didSetProps: c } = n, {
      on: s,
      getEntries: d,
      setEntries: l,
      pushTask: u,
      abortTask: y,
      insertEntries: p,
      removeEntries: b,
      updateEntry: m,
      setExtensionState: k,
      getEntryExtensionState: v,
      setEntryExtensionState: S
    } = r;
    let t, o;
    c(
      ({
        element: e,
        preventAddEntries: L,
        ...a
      }) => {
        if (!e)
          return;
        t = e;
        const { drop: E } = a;
        Object.assign(t, {
          ...a,
          drop: E && !L
        }), i(), o?.(), o = P(t, "connected", () => {
          i();
        }), k({
          source: E ? {
            type: "drop"
          } : void 0
        });
      }
    );
    function i() {
      t.setSetEntriesCallback(l), t.setInsertEntriesCallback(p), t.setRemoveEntriesCallback(b), t.setUpdateEntryCallback(m), t.setSetEntryExtensionStateCallback(S), t.setGetEntryExtensionStateCallback(v), t.setPushTaskCallback(u), t.setAbortTaskCallback(y), t.onSetEntries(d());
    }
    function C(e) {
      t?.onRemoveEntry(e);
    }
    function f(e) {
      t?.onInsertEntry(e);
    }
    function x(e) {
      t?.onSetEntries(e);
    }
    const h = s("insertEntry", f), R = s("removeEntry", C), T = s("updateEntries", x);
    return {
      destroy() {
        o?.(), T?.(), h?.(), R?.();
      }
    };
  }
});
export {
  w as EntryListView
};
