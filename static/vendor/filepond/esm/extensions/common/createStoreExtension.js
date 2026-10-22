/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as nt } from "./createExtension.js";
import { isNullOrUndefined as R, isFile as A, isFileEntry as rt, isBlob as ct } from "../../utils/test.js";
import { Status as n } from "../../common/status.js";
import { createPerceivedPerformanceProxy as ut } from "../../common/perceivedPerformanceProxy.js";
import { didAbort as P } from "../../utils/abort.js";
function mt(g) {
  const { name: S, props: k, factory: Y } = g;
  return nt({
    name: S,
    type: "store",
    props: {
      perceivedPerformance: null,
      parallel: 4,
      actionStore: "store",
      actionLoad: "load",
      actionAbort: "abort",
      valueKey: "value",
      ...k
    },
    factory: (b, I) => {
      const { props: i, didSetProps: N } = b, {
        on: m,
        setExtensionStatus: B,
        updateEntry: E,
        removeEntries: D,
        pushTask: d,
        abortTask: F,
        getEntryExtensionState: C,
        getEntryExtensionStatus: L,
        setEntryExtensionStatus: l,
        createProgressHandler: U
      } = I;
      let p = null;
      N(({ perceivedPerformance: t }) => {
        t === !0 ? p = {
          minDuration: 1e3,
          maxDuration: 1500,
          minStep: 50,
          maxStep: 250
        } : t ? p = t : p = null;
      });
      const { restoreEntry: O, storeEntry: K, releaseEntry: y } = Y(b, I) ?? {};
      async function w(t, { signal: o }) {
        t = l(t, {
          type: n.System,
          code: "STORE_BUSY",
          progress: 1 / 0
        });
        try {
          const s = p && !document.hidden ? ut(K, {
            ...p,
            total: t.size
          }) : K, { valueKey: a } = i, u = await s(t, {
            onprogress: U(t, { code: "STORE_BUSY" }),
            signal: o
          });
          R(u) || E(t, {
            state: {
              [a]: u
            },
            extensionState: {
              [S]: {
                status: {
                  type: n.Success,
                  code: "STORE_COMPLETE"
                }
              }
            }
          });
        } catch (e) {
          if (P(o, e)) {
            const { actionStore: s, actionAbort: a, valueKey: u } = i;
            E(t, {
              state: {
                // don't abort again
                [a]: !1,
                // need to halt store action or will keep storing
                [s]: null,
                // reset storage key
                [u]: null
              },
              extensionState: {
                [S]: {
                  status: {
                    type: n.System,
                    code: "STORE_ABORT"
                  }
                }
              }
            });
            return;
          }
          throw l(t, {
            type: n.Error,
            code: "STORE_ERROR",
            values: { error: e }
          }), e;
        }
      }
      async function Q(t, { signal: o }) {
        if (!O)
          return;
        t = l(t, {
          type: n.System,
          code: "STORE_RESTORE_BUSY",
          progress: 1 / 0
        });
        const { valueKey: e } = i, s = t.state[e];
        try {
          let a = await O(s, t, {
            onprogress: U(t, { code: "STORE_RESTORE_BUSY" }),
            signal: o
          });
          E(t, {
            // if response is a blob we need BlobLoader to load the source
            src: ct(a) ? a : t.src,
            // if response is a file we can skip straight to file
            file: A(a) ? a : null,
            // new state
            state: {
              // remember storage key
              [e]: s
            },
            extensionState: {
              [S]: {
                // we can store this entry
                canStore: !0,
                // done!
                status: {
                  type: n.System,
                  code: "STORE_RESTORE_COMPLETE"
                }
              }
            }
          });
        } catch (a) {
          if (P(o, a)) {
            l(t, {
              type: n.System,
              code: "STORE_RESTORE_ABORT"
            });
            return;
          }
          throw l(t, {
            type: n.Error,
            code: "STORE_RESTORE_ERROR",
            values: { error: a }
          }), a;
        }
      }
      async function M(t, { signal: o }) {
        const { valueKey: e, actionLoad: s, actionStore: a, shouldStore: u } = i;
        try {
          const r = t.state[e];
          if (R(r))
            return;
          t = l(t, {
            type: n.System,
            code: "STORE_RELEASE_BUSY",
            progress: 1 / 0
          });
          let c = !1;
          if (u) {
            const f = t.state[a] === !1;
            c = await u(t) && f;
          }
          if (O && !A(t.file) && !c) {
            let f = await O(r, t, {
              onprogress: U(t, {
                code: "STORE_RELEASE_BUSY"
              }),
              signal: o
            });
            E(t, {
              file: f
            });
          }
          const v = {
            state: {
              [e]: null,
              [s]: null
            },
            extensionState: {
              [S]: {
                // we can store this entry
                canStore: !0,
                status: {
                  type: n.System,
                  code: "STORE_RELEASE_COMPLETE"
                }
              }
            }
          };
          if (y ? await y(r, t, {
            signal: o
          }) !== !1 && E(t, v) : E(t, v), c) {
            D(t);
            return;
          }
        } catch (r) {
          if (P(o, r)) {
            l(t, {
              type: n.System,
              code: "STORE_RELEASE_ABORT"
            });
            return;
          }
          throw l(t, {
            type: n.Error,
            code: "STORE_RELEASE_ERROR",
            values: { error: r }
          }), r;
        }
      }
      async function z(t) {
        const { valueKey: o } = i, { entry: e } = t;
        if (!y)
          return;
        const s = e.state[o], a = !R(s), r = L(e)?.code !== "STORE_RESTORE_ERROR";
        if (!(!a || !r))
          try {
            await y(s, e);
          } catch {
          }
      }
      async function G(t) {
        const o = L(t), { valueKey: e, actionStore: s, actionLoad: a, actionAbort: u } = i, r = t.state[e] ?? null, c = R(t.state[s]) ? null : t.state[s];
        if (R(r)) {
          E(t, {
            state: {
              [e]: r,
              [s]: c
            },
            extensionState: {
              [S]: {
                // so we can match on extension actions
                actions: [s, a, u],
                // null means undetermined if we can activate, will trigger new test
                canStore: null,
                // awaiting new test
                status: {
                  type: n.System,
                  code: "STORE_LIMBO"
                }
              }
            }
          });
          return;
        }
        if (o.code !== "STORE_RESTORE_COMPLETE") {
          if (c !== !1 && o.code === "STORE_COMPLETE") {
            d(t.id, M), l(t, {
              type: n.System,
              code: "STORE_IDLE"
            });
            return;
          }
          E(t, {
            state: {
              [e]: r,
              [s]: c
            },
            extensionState: {
              [S]: {
                canStore: !0,
                status: {
                  type: n.Success,
                  code: "STORE_COMPLETE"
                }
              }
            }
          });
        }
      }
      async function H(t) {
        const { valueKey: o } = i, e = t.state[o], { canStore: s } = C(t);
        e && (s || l(t, {
          type: n.Success,
          code: "STORE_COMPLETE"
        }));
      }
      async function V(t) {
        const { valueKey: o } = i, e = t.state[o], s = rt(t) && A(t.file);
        E(t, {
          state: {
            [o]: e ?? null
          },
          extensionState: {
            [S]: {
              canStore: s,
              status: {
                type: n.System,
                code: s ? "STORE_READY" : "STORE_IDLE"
              }
            }
          }
        });
      }
      async function W(t) {
        const { actionStore: o, shouldStore: e } = i;
        if (!e)
          return;
        const s = await e(t);
        E(t, {
          state: {
            [o]: s
          }
        });
      }
      async function j(t) {
        l(t, {
          code: "STORE_QUEUED",
          type: n.System,
          progress: 1 / 0
        });
      }
      async function q(t) {
        const { valueKey: o, parallel: e, actionLoad: s, actionStore: a, actionAbort: u, shouldStore: r } = i, c = t.state[a], v = t.state[s], f = t.state[u], et = t.state[o], x = L(t), { canStore: T = null } = C(t), h = x?.code === "STORE_BUSY", _ = !R(et) && !h;
        if (T === null) {
          d(t.id, V);
          return;
        }
        if (c === null && r) {
          if (f === !1) {
            D(t);
            return;
          }
          d(t.id, W);
          return;
        }
        const ot = !R(O);
        if (_ && !A(t.file) && ot && v === !0) {
          d(t.id, Q, { parallel: e });
          return;
        }
        if (_ && c === !1) {
          d(t.id, M);
          return;
        }
        if (T === !1) {
          d(t.id, H);
          return;
        }
        if (!_ && T && (c === !0 && f === !0)) {
          F(t.id, w), h || E(t, {
            state: {
              [u]: !1,
              [a]: null
            },
            extensionState: {
              [S]: {
                status: {
                  type: n.System,
                  code: "STORE_READY"
                }
              }
            }
          });
          return;
        }
        const st = x?.code === "STORE_QUEUED", at = x?.code === "STORE_ERROR";
        if (!_ && !st && !at && !h && c === !0 && T) {
          d(t.id, j);
          return;
        }
        if (!_ && !h && c === !0 && T) {
          d(t.id, w, {
            parallel: e
          });
          return;
        }
      }
      function J(t) {
        const { valueKey: o } = i;
        if (o) {
          for (const e of t)
            if (R(e.state[o]))
              return B({
                type: n.Error,
                code: "STORE_AWAITING_COMPLETION",
                meta: { flag: "customError" }
              });
          B({
            type: n.System,
            code: "VALIDATION_COMPLETE"
          });
        }
      }
      const X = m("updateEntryData", G), Z = m("updateEntry", q), $ = m("removeEntry", z), tt = m("updateEntries", J);
      return {
        destroy() {
          X(), Z(), tt(), $();
        }
      };
    }
  });
}
export {
  mt as createStoreExtension
};
