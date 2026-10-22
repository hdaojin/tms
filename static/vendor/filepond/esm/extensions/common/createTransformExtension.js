/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as z } from "./createExtension.js";
import { isFileEntry as M, isBlobOrFile as G, isFile as O, isNullOrUndefined as P, isFunction as F } from "../../utils/test.js";
import { cloneFile as J, cloneFileWithOptions as K } from "../../utils/file.js";
import { Status as i } from "../../common/status.js";
import { didAbort as x } from "../../utils/abort.js";
function tt(L) {
  const { name: d, props: k, factory: U } = L;
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
    factory: (R, A) => {
      const { props: f } = R, {
        on: y,
        updateEntry: u,
        pushTask: m,
        abortTask: b,
        abortTasks: w,
        setEntryExtensionStatus: p,
        getEntryExtensionState: T,
        setEntryExtensionState: C,
        createProgressHandler: h
      } = A, {
        transformEntry: D = () => null,
        canTransformEntry: I = (t) => M(t) && G(t.file),
        prepareTransformEntry: N = void 0
      } = U(R, A);
      async function v(t, { signal: o }) {
        const { actionTransform: n, actionLoad: s, shouldTransform: r } = f;
        if (F(N)) {
          t = p(t, {
            type: i.System,
            code: "TRANSFORM_PREPARE",
            progress: 1 / 0
          });
          try {
            await N(t, {
              signal: o,
              onprogress: h(t, { code: "TRANSFORM_PREPARE" })
            });
          } catch (l) {
            if (x(o, l))
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
        t = p(t, {
          type: i.System,
          code: "TRANSFORM_BUSY",
          progress: 1 / 0
        });
        let a;
        try {
          a = await D(t, {
            signal: o,
            onprogress: h(t, { code: "TRANSFORM_BUSY" })
          });
        } catch (l) {
          if (x(o, l))
            return;
          if (p(t, {
            type: i.Error,
            code: "TRANSFORM_ERROR",
            values: { error: l }
          }), F(r))
            throw l;
          return;
        }
        const c = {
          [n]: F(r) ? !1 : null
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
        let { file: e, history: S } = O(a) ? { file: a } : a;
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
              [s]: null
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
      async function B(t) {
        const { actionTransform: o } = f, { input: n } = T(t);
        w(t.id), u(
          // current entry
          t,
          // reset to original file
          {
            file: J(n)
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
      async function g(t) {
        const { actionTransform: o, shouldTransform: n } = f;
        if (!n)
          return;
        const { input: s } = T(t);
        if (s)
          return;
        const r = await n(t);
        u(t, {
          state: {
            [o]: r
          }
        });
      }
      async function _(t) {
        const { actionTransform: o, filterEntry: n } = f;
        let s = await I(t);
        s && (s = await n(t)), C(t, {
          canTransform: s,
          actions: s ? [o] : [],
          status: {
            type: i.System,
            code: "TRANSFORM_IDLE"
          }
        });
      }
      async function Y(t) {
        const { actionLoad: o } = f;
        u(t, {
          state: {
            [o]: !0
          }
        });
      }
      async function H(t) {
        if (!M(t) || !O(t.file))
          return;
        const { actionTransform: o, shouldTransform: n } = f, { file: s } = t, r = P(t.state[o]) ? null : t.state[o], { canTransform: a, input: c } = T(t);
        a !== null && (c && s.lastModified >= c.lastModified || (b(t.id, _), u(t, {
          state: {
            // when `shouldTransform` is set we don't accept `false` for transform action
            [o]: n && r === !1 ? null : r
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
      async function W(t) {
        const { actionTransform: o, actionLoad: n, parallel: s, shouldTransform: r } = f;
        if (!M(t))
          return;
        const { canTransform: a = null, input: c } = T(t), e = t.state[o], S = t.state[n], E = !P(e) && e !== !1;
        if (a === !1)
          return;
        if (E && S === null && !O(t.file)) {
          m(t.id, Y);
          return;
        }
        if (a === null) {
          m(t.id, _);
          return;
        }
        if (e === null && r) {
          m(t.id, g);
          return;
        }
        if (e === !1 && !!c && !r) {
          m(t.id, B, { parallel: s });
          return;
        }
        if (E && a) {
          m(t.id, v, { parallel: s });
          return;
        }
      }
      const j = y("updateEntryData", H), q = y("updateEntry", W);
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
