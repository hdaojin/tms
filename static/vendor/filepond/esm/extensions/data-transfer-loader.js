/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as O } from "./common/createExtension.js";
import { didAbort as v } from "../utils/abort.js";
import { isFileEntry as y, isDataTransfer as F, isDirectoryEntry as R } from "../utils/test.js";
import { Status as c } from "../common/status.js";
import { shouldLoadWithIdleCallback as U, readEntriesFromDataTransfer as _, dataTransferToFiles as k } from "../common/readEntriesFromDataTransfer.js";
import { flattenTree as w } from "../utils/tree.js";
import { createPerceivedPerformanceProxy as C } from "../common/perceivedPerformanceProxy.js";
import { EMPTY_ARRAY as I } from "../utils/array.js";
const J = O({
  name: "DataTransferLoader",
  type: "loader",
  props: {
    actionLoad: "load",
    actionAbort: "abort",
    mode: "flatten",
    ignoredEntryPatterns: I
  },
  factory: (u, l) => {
    const { props: p, didSetProps: E } = u, {
      on: T,
      removeEntries: D,
      replaceEntry: h,
      pushTask: S,
      abortTasks: g,
      setEntryExtensionStatus: s,
      getEntryExtensionStatus: b
    } = l;
    let e = null;
    E(({ perceivedPerformance: r }) => {
      r === !0 ? e = {
        minDuration: 500,
        maxDuration: 750,
        minStep: 50,
        maxStep: 150
      } : r ? e = r : e = null;
    });
    async function A(r, { signal: d }) {
      const { mode: f, ignoredEntryPatterns: a } = p;
      r = s(r, {
        type: c.System,
        code: "LOAD_BUSY",
        progress: 1 / 0
      });
      let i;
      try {
        if (U(r.src)) {
          const o = e && !document.hidden, m = function(t, n) {
            return _(t, {
              ...n,
              ignoredEntryPatterns: a
            });
          }, x = await (o ? C(m, {
            ...e
          }) : m)(r.src, {
            signal: d,
            onprogress: ({ loaded: t, total: n }) => {
              r = s(r, {
                type: c.System,
                code: "LOAD_BUSY",
                progress: t / n,
                values: {
                  processed: t,
                  total: n
                }
              });
            }
          });
          f === "flatten" && (i = w(x, "entries").filter((t) => !R(t)).map((t) => ({
            src: t,
            origin: r.origin,
            containerId: r.id
          })));
        } else
          i = (await k(r.src, {
            ignoredEntryPatterns: a
          })).map((o) => ({
            src: o,
            origin: r.origin,
            containerId: r.id
          }));
      } catch (o) {
        if (v(d, o)) {
          D(r);
          return;
        }
        throw s(r, {
          type: c.Error,
          code: "LOAD_ERROR",
          values: { error: o }
        }), o;
      }
      r = s(r, {
        type: c.Success,
        code: "LOAD_COMPLETE"
      }), h(r, i);
    }
    function L(r) {
      if (b(r)?.type === "error" || !y(r) || !F(r.src))
        return;
      const { actionAbort: a } = p;
      if (r.state[a]) {
        g(r.id);
        return;
      }
      S(r.id, A);
    }
    const P = T("updateEntry", L);
    return {
      destroy: () => {
        P();
      }
    };
  }
});
export {
  J as DataTransferLoader
};
