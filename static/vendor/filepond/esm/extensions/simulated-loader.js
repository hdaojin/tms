/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createProgressEvent as T } from "../utils/xhr.js";
import { isFileEntry as H, isBlobOrFile as G, isString as _, isNumber as J } from "../utils/test.js";
import { createExtension as K } from "./common/createExtension.js";
import { Status as n } from "../common/status.js";
import { sleep as f } from "../utils/sleep.js";
import { log as N } from "../common/console.js";
const et = K({
  name: "SimulatedLoader",
  type: "loader",
  props: {
    actionLoad: "load",
    actionAbort: "abort",
    bitrate: 1024e3,
    tickrate: 250,
    connectionDelay: 250,
    errorDelay: void 0,
    parallel: 4,
    log: !0,
    fetchFile: void 0
  },
  factory: ({ extensionName: F, props: h, didSetProps: x }, R) => {
    const {
      setEntryExtensionStatus: d,
      getEntryExtensionStatus: P,
      createProgressHandler: B,
      removeEntries: k,
      updateEntry: L,
      pushTask: v,
      abortTasks: z,
      on: M
    } = R;
    let U;
    x(({ bitrate: t = 1024e3, tickrate: e = 250 }) => {
      U = t / 8 * (e / 1e3);
    });
    async function Y(t) {
      d(t, {
        type: n.System,
        code: "LOAD_QUEUED"
      });
    }
    async function g(t) {
      const { src: e, size: l = 1024 * 1024 } = t, { log: o, connectionDelay: r, errorDelay: a } = h;
      if (d(t, {
        type: n.System,
        code: "LOAD_BUSY",
        progress: 1 / 0
      }), await f(r), a) {
        await f(a);
        const i = "Simulated error";
        throw d(t, {
          type: n.Error,
          code: "LOAD_ERROR",
          values: { error: i }
        }), o && c(["did throw load info error", t.id]), i;
      }
      o && c(["did load info", t.id]), L(t, {
        name: e.split("/").pop(),
        type: "plain/text",
        size: l
      });
    }
    async function Q(t, { signal: e }) {
      const { src: l, size: o = 1024 * 1024 } = t, {
        log: r,
        actionLoad: a,
        actionAbort: i,
        tickrate: w,
        connectionDelay: D,
        fetchFile: p,
        errorDelay: m
      } = h;
      t = d(t, {
        type: n.System,
        code: "LOAD_BUSY",
        progress: 1 / 0
      });
      const u = B(t, { code: "LOAD_BUSY" });
      let b, O, y = !1;
      const s = () => {
        y || (y = !0, clearInterval(b), r && c(["did abort load data", t.id]), t = L(t, {
          state: {
            [a]: !1,
            [i]: !1
          }
        }), queueMicrotask(() => {
          k(t);
        }), O?.(e.reason));
      };
      if (e.addEventListener("abort", s, { once: !0 }), await f(D), e.aborted)
        throw e.reason;
      if (m) {
        if (await f(m), e.aborted)
          throw e.reason;
        const E = "Simulated error";
        throw t = d(t, {
          type: n.Error,
          code: "LOAD_ERROR",
          values: { error: E }
        }), r && c(["did throw load data error", t.id]), e.removeEventListener("abort", s), E;
      }
      return await new Promise((E, I) => {
        let S = 0;
        O = I, b = setInterval(async () => {
          if (e.aborted) {
            s();
            return;
          }
          if (S = Math.min(o, S + U), u(T(!0, S, o)), S < o)
            return;
          u(T(!0, o, o)), clearInterval(b);
          let A;
          try {
            if (p)
              A = await p(t, { onprogress: u, signal: e });
            else {
              if (await f(0), e.aborted)
                throw e.reason;
              A = new File(["#".repeat(o)], l.split("/").pop(), {
                type: "plain/text"
              });
            }
          } catch (C) {
            e.removeEventListener("abort", s), I(C);
            return;
          }
          if (e.aborted) {
            s();
            return;
          }
          e.removeEventListener("abort", s), t = L(t, {
            file: A,
            state: {
              load: !1
            },
            extensionState: {
              [F]: {
                status: {
                  type: n.Success,
                  code: "LOAD_COMPLETE"
                }
              }
            }
          }), r && c(["did load data", t.id]), E();
        }, w);
      });
    }
    function j(t) {
      const e = P(t), l = Object.keys(e).length > 0;
      if (e?.type === "error" || !H(t) || G(t.file))
        return;
      const { src: r, name: a, size: i } = t, { actionLoad: w, actionAbort: D, parallel: p } = h, m = t.state[w], u = t.state[D];
      if (!_(r))
        return;
      if (u) {
        z(t.id), k(t);
        return;
      }
      if (m === !1)
        return;
      if (!(_(a) && J(i))) {
        v(t.id, g);
        return;
      }
      if (!l) {
        v(t.id, Y);
        return;
      }
      v(t.id, Q, { parallel: p });
    }
    function c(t) {
      N("⧗", F, "(", ...t, ")");
    }
    const q = M("updateEntry", j);
    return {
      destroy: () => {
        q();
      }
    };
  }
});
export {
  et as SimulatedLoader
};
