/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as nt } from "./createExtension.js";
import { isNullOrUndefined as R, isFile as h, isFileEntry as rt, isBlob as ct } from "../../utils/test.js";
import { Status as a } from "../../common/status.js";
import { createPerceivedPerformanceProxy as ut } from "../../common/perceivedPerformanceProxy.js";
import { didAbort as P } from "../../utils/abort.js";
function _t(k) {
  const { name: S, props: B, factory: Y } = k;
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
      ...B
    },
    factory: (b, U) => {
      const { props: i, didSetProps: N } = b, {
        on: _,
        setExtensionStatus: I,
        updateEntry: l,
        removeEntries: C,
        pushTask: d,
        abortTask: F,
        getEntryExtensionState: D,
        getEntryExtensionStatus: A,
        setEntryExtensionStatus: E,
        createProgressHandler: L
      } = U;
      let p = null;
      N(({ perceivedPerformance: t }) => {
        t === !0 ? p = {
          minDuration: 1e3,
          maxDuration: 1500,
          minStep: 50,
          maxStep: 250
        } : t ? p = t : p = null;
      });
      const { restoreEntry: O, storeEntry: K, releaseEntry: y } = Y(b, U) ?? {};
      async function M(t, { signal: o }) {
        E(t, {
          type: a.System,
          code: "STORE_BUSY",
          progress: 1 / 0
        });
        try {
          const s = p && !document.hidden ? ut(K, {
            ...p,
            total: t.size
          }) : K, { valueKey: n } = i, u = await s(t, {
            onprogress: L(t),
            signal: o
          });
          R(u) || l(t, {
            state: {
              [n]: u
            },
            extensionState: {
              [S]: {
                status: {
                  type: a.Success,
                  code: "STORE_COMPLETE"
                }
              }
            }
          });
        } catch (e) {
          if (P(o, e)) {
            const { actionStore: s, actionAbort: n, valueKey: u } = i;
            l(t, {
              state: {
                // don't abort again
                [n]: !1,
                // need to halt store action or will keep storing
                [s]: null,
                // reset storage key
                [u]: null
              },
              extensionState: {
                [S]: {
                  status: {
                    type: a.System,
                    code: "STORE_ABORT"
                  }
                }
              }
            });
            return;
          }
          throw E(t, {
            type: a.Error,
            code: "STORE_ERROR",
            values: { error: e }
          }), e;
        }
      }
      async function Q(t, { signal: o }) {
        if (!O)
          return;
        E(t, {
          type: a.System,
          code: "STORE_RESTORE_BUSY",
          progress: 1 / 0
        });
        const { valueKey: e } = i, s = t.state[e];
        try {
          let n = await O(s, t, {
            onprogress: L(t),
            signal: o
          });
          l(t, {
            // if response is a blob we need BlobLoader to load the source
            src: ct(n) ? n : t.src,
            // if response is a file we can skip straight to file
            file: h(n) ? n : null,
            // new state
            state: {
              // remember storage key
              [e]: s
            },
            extensionState: {
              [S]: {
                // need to re-evaluate if we can store this file
                canStore: !0,
                // done!
                status: {
                  type: a.System,
                  code: "STORE_RESTORE_COMPLETE"
                }
              }
            }
          });
        } catch (n) {
          if (P(o, n)) {
            E(t, {
              type: a.System,
              code: "STORE_RESTORE_ABORT"
            });
            return;
          }
          throw E(t, {
            type: a.Error,
            code: "STORE_RESTORE_ERROR",
            values: { error: n }
          }), n;
        }
      }
      async function w(t, { signal: o }) {
        const { valueKey: e, actionLoad: s, actionStore: n, shouldStore: u } = i;
        try {
          const r = t.state[e];
          if (R(r))
            return;
          E(t, {
            type: a.System,
            code: "STORE_RELEASE_BUSY",
            progress: 1 / 0
          });
          let c = !1;
          if (u) {
            const f = t.state[n] === !1;
            c = await u(t) && f;
          }
          if (O && !h(t.file) && !c) {
            let f = await O(r, t, {
              onprogress: L(t),
              signal: o
            });
            l(t, {
              file: f
            });
          }
          y ? await y(r, t, {
            signal: o
          }) !== !1 && l(t, {
            state: {
              [e]: null,
              [s]: null
            },
            extensionState: {
              [S]: {
                canStore: !0,
                status: {
                  type: a.System,
                  code: "STORE_RELEASE_COMPLETE"
                }
              }
            }
          }) : l(t, {
            state: {
              [e]: null,
              [s]: null
            },
            extensionState: {
              [S]: {
                status: {
                  type: a.System,
                  code: "STORE_RELEASE_COMPLETE"
                }
              }
            }
          }), c && C(t);
        } catch (r) {
          if (P(o, r)) {
            E(t, {
              type: a.System,
              code: "STORE_RELEASE_ABORT"
            });
            return;
          }
          throw E(t, {
            type: a.Error,
            code: "STORE_RELEASE_ERROR",
            values: { error: r }
          }), r;
        }
      }
      async function z(t) {
        const { valueKey: o } = i, { entry: e } = t;
        if (!y)
          return;
        const s = e.state[o], n = !R(s), r = A(e)?.code !== "STORE_RESTORE_ERROR";
        if (!(!n || !r))
          try {
            await y(s, e);
          } catch {
          }
      }
      async function G(t) {
        const o = A(t), { valueKey: e, actionStore: s, actionLoad: n, actionAbort: u } = i, r = t.state[e] ?? null, c = R(t.state[s]) ? null : t.state[s];
        if (R(r)) {
          l(t, {
            state: {
              [e]: r,
              [s]: c
            },
            extensionState: {
              [S]: {
                // so we can match on extension actions
                actions: [s, n, u],
                // null means undetermined if we can activate, will trigger new test
                canStore: null,
                // awaiting new test
                status: {
                  type: a.System,
                  code: "STORE_LIMBO"
                }
              }
            }
          });
          return;
        }
        if (o.code !== "STORE_RESTORE_COMPLETE") {
          if (c !== !1 && o.code === "STORE_COMPLETE") {
            d(t.id, w), E(t, {
              type: a.System,
              code: "STORE_IDLE"
            });
            return;
          }
          l(t, {
            state: {
              [e]: r,
              [s]: c
            },
            extensionState: {
              [S]: {
                canStore: !0,
                status: {
                  type: a.Success,
                  code: "STORE_COMPLETE"
                }
              }
            }
          });
        }
      }
      async function H(t) {
        const { valueKey: o } = i, e = t.state[o], { canStore: s } = D(t);
        e && (s || E(t, {
          type: a.Success,
          code: "STORE_COMPLETE"
        }));
      }
      async function V(t) {
        const { valueKey: o } = i, e = t.state[o], s = rt(t) && h(t.file);
        l(t, {
          state: {
            [o]: e ?? null
          },
          extensionState: {
            [S]: {
              canStore: s,
              status: {
                type: a.System,
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
        l(t, {
          state: {
            [o]: s
          }
        });
      }
      async function j(t) {
        E(t, {
          code: "STORE_QUEUED",
          type: a.System,
          progress: 1 / 0
        });
      }
      async function q(t) {
        const { valueKey: o, parallel: e, actionLoad: s, actionStore: n, actionAbort: u, shouldStore: r } = i, c = t.state[n], f = t.state[s], g = t.state[u], et = t.state[o], x = A(t), { canStore: T = null } = D(t), v = x?.code === "STORE_BUSY", m = !R(et) && !v;
        if (T === null) {
          d(t.id, V);
          return;
        }
        if (c === null && r) {
          if (g === !1) {
            C(t);
            return;
          }
          d(t.id, W);
          return;
        }
        const st = !R(O);
        if (m && !h(t.file) && st && f === !0) {
          d(t.id, Q, { parallel: e });
          return;
        }
        if (m && c === !1) {
          d(t.id, w);
          return;
        }
        if (T === !1) {
          d(t.id, H);
          return;
        }
        if (!m && T && (c === !0 && g === !0)) {
          F(t.id, M), v || l(t, {
            state: {
              [u]: !1,
              [n]: null
            },
            extensionState: {
              [S]: {
                status: {
                  type: a.System,
                  code: "STORE_READY"
                }
              }
            }
          });
          return;
        }
        const ot = x?.code === "STORE_QUEUED", at = x?.code === "STORE_ERROR";
        if (!m && !ot && !at && !v && c === !0 && T) {
          d(t.id, j);
          return;
        }
        if (!m && !v && c === !0 && T) {
          d(t.id, M, {
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
              return I({
                type: a.Error,
                code: "STORE_AWAITING_COMPLETION",
                meta: { flag: "customError" }
              });
          I({
            type: a.System,
            code: "VALIDATION_COMPLETE"
          });
        }
      }
      const X = _("updateEntryData", G), Z = _("updateEntry", q), $ = _("removeEntry", z), tt = _("updateEntries", J);
      return {
        destroy() {
          X(), Z(), tt(), $();
        }
      };
    }
  });
}
export {
  _t as createStoreExtension
};
