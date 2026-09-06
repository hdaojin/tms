/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as z } from "./createExtension.js";
import { isFileEntry as M, isBlobOrFile as G, isFile as y, isNullOrUndefined as x, isFunction as O } from "../../utils/test.js";
import { cloneFile as J, cloneFileWithOptions as K } from "../../utils/file.js";
import { Status as i } from "../../common/status.js";
import { didAbort as L } from "../../utils/abort.js";
function tt(P) {
  const { name: d, props: k, factory: b } = P;
  return z({
    name: d,
    type: "transform",
    props: {
      // default action props
      actionTransform: "transform",
      actionLoad: "load",
      shouldTransform: void 0,
      parallel: 1,
      filterEntry: (R) => !0,
      ...k
    },
    factory: (R, F) => {
      const { props: f } = R, {
        on: h,
        updateEntry: u,
        pushTask: m,
        abortTask: w,
        abortTasks: U,
        setEntryExtensionStatus: p,
        getEntryExtensionState: T,
        setEntryExtensionState: C,
        createProgressHandler: A
      } = F, {
        transformEntry: D = () => null,
        canTransformEntry: I = (t) => M(t) && G(t.file),
        prepareTransformEntry: N = void 0
      } = b(R, F);
      async function v(t, { signal: o }) {
        const { actionTransform: s, actionLoad: n, shouldTransform: r } = f;
        if (O(N)) {
          p(t, {
            type: i.System,
            code: "TRANSFORM_PREPARE",
            progress: 1 / 0
          });
          try {
            await N(t, {
              signal: o,
              onprogress: A(t)
            });
          } catch (l) {
            if (L(o, l))
              return;
            p(t, {
              type: i.Error,
              code: "TRANSFORM_PREPARE_ERROR",
              values: { error: l }
            });
            return;
          }
          p(t, {
            type: i.System,
            code: "TRANSFORM_PREPARE_COMPLETE"
          });
        }
        p(t, {
          type: i.System,
          code: "TRANSFORM_BUSY",
          progress: 1 / 0
        });
        let a;
        try {
          a = await D(t, {
            signal: o,
            onprogress: A(t)
          });
        } catch (l) {
          if (L(o, l))
            return;
          if (p(t, {
            type: i.Error,
            code: "TRANSFORM_ERROR",
            values: { error: l }
          }), O(r))
            throw l;
          return;
        }
        const c = {
          [s]: O(r) ? !1 : null
        };
        if (!a) {
          u(t, {
            state: c,
            extensionState: {
              [d]: {
                status: {
                  type: i.System,
                  code: "TRANSFORM_CANCEL"
                }
              }
            }
          });
          return;
        }
        let { file: e, history: S } = y(a) ? { file: a } : a;
        e.lastModified <= t.file.lastModified && (e = K(e, {
          lastModified: e.lastModified + 1
        }));
        const { input: E } = T(t);
        u(
          // current entry
          t,
          // transformed file props
          {
            file: e
          },
          // programmatically updated props
          {
            // we don't transform again
            state: {
              ...c,
              [n]: null
            },
            // did edit Entry
            extensionState: {
              [d]: {
                // the input file used
                input: E ?? t.file,
                // data for this edit
                history: S,
                // update status
                status: {
                  type: i.System,
                  code: "TRANSFORM_COMPLETE"
                }
              }
            }
          }
        );
      }
      async function g(t) {
        const { actionTransform: o } = f, { input: s } = T(t);
        U(t.id), u(
          // current entry
          t,
          // reset to original file
          {
            file: J(s)
          },
          // reset all changes
          {
            state: {
              [o]: null
            },
            extensionState: {
              [d]: {
                input: null,
                history: [],
                status: {
                  type: i.System,
                  code: "TRANSFORM_IDLE"
                }
              }
            }
          }
        );
      }
      async function B(t) {
        const { actionTransform: o, shouldTransform: s } = f;
        if (!s)
          return;
        const { input: n } = T(t);
        if (n)
          return;
        const r = await s(t);
        u(t, {
          state: {
            [o]: r
          }
        });
      }
      async function _(t) {
        const { actionTransform: o, filterEntry: s } = f;
        let n = await I(t);
        n && (n = await s(t)), C(t, {
          canTransform: n,
          actions: n ? [o] : [],
          status: {
            type: i.System,
            code: "TRANSFORM_IDLE"
          }
        });
      }
      async function H(t) {
        const { actionLoad: o } = f;
        u(t, {
          state: {
            [o]: !0
          }
        });
      }
      async function W(t) {
        if (!M(t) || !y(t.file))
          return;
        const { actionTransform: o, shouldTransform: s } = f, { file: n } = t, r = x(t.state[o]) ? null : t.state[o], { canTransform: a, input: c } = T(t);
        a !== null && (c && n.lastModified >= c.lastModified || (w(t.id, _), u(t, {
          state: {
            // when `shouldTransform` is set we don't accept `false` for transform action
            [o]: s && r === !1 ? null : r
          },
          extensionState: {
            [d]: {
              // the action string that triggers this transform extension
              actions: a ? [o] : [],
              // null means undetermined if we can activate
              canTransform: null,
              // reset last transform date
              input: null,
              // now idle
              status: {
                type: i.System,
                code: "TRANSFORM_LIMBO"
              }
            }
          }
        })));
      }
      async function Y(t) {
        const { actionTransform: o, actionLoad: s, parallel: n, shouldTransform: r } = f;
        if (!M(t))
          return;
        const { canTransform: a = null, input: c } = T(t), e = t.state[o], S = t.state[s], E = !x(e) && e !== !1;
        if (a === !1)
          return;
        if (E && S === null && !y(t.file)) {
          m(t.id, H);
          return;
        }
        if (a === null) {
          m(t.id, _);
          return;
        }
        if (e === null && r) {
          m(t.id, B);
          return;
        }
        if (e === !1 && !!c && !r) {
          m(t.id, g, { parallel: n });
          return;
        }
        if (E && a) {
          m(t.id, v, { parallel: n });
          return;
        }
      }
      const j = h("updateEntryData", W), q = h("updateEntry", Y);
      return {
        destroy() {
          q(), j();
        }
      };
    }
  });
}
export {
  tt as createTransformExtension
};
