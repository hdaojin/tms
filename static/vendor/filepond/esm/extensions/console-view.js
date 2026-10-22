/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as I } from "./common/createExtension.js";
import { bytesToNaturalFileSize as P } from "../utils/file.js";
import { isDirectoryEntry as D, isNumber as G } from "../utils/test.js";
import { Status as u } from "../common/status.js";
import { clamp as N } from "../utils/math.js";
import { arrayRemoveFalsy as S } from "../utils/array.js";
import { log as m, clear as R } from "../common/console.js";
import { toSpaceSeparatedString as T } from "../elements/common/string.js";
let E = 0;
const X = I({
  name: "ConsoleView",
  type: "view",
  props: {
    clearBeforeLog: !1,
    debounce: !0
  },
  factory: ({ props: w, extensionName: x }, { on: C, insertEntries: b, updateEntry: F, removeEntries: L, getEntries: B }) => {
    function p(e, r = /* @__PURE__ */ new WeakSet()) {
      if (e === null || typeof e != "object")
        return e;
      if (r.has(e))
        return null;
      if (r.add(e), Array.isArray(e))
        return e.map((o) => p(o, r));
      try {
        return structuredClone(e);
      } catch {
        if (/Error/.test(e.constructor.name))
          return {
            code: e.code,
            message: e.message
          };
        let t = {};
        for (const [l, a] of Object.entries(e))
          t[l] = p(a);
        return t;
      }
    }
    function O(e) {
      return p(e);
    }
    function U(e) {
      if (!G(e))
        return;
      if (e === 1 / 0)
        return "∞ busy";
      const r = N(e), o = 15, t = Math.round(r * o);
      return "█".repeat(t) + "░".repeat(o - t) + " " + Math.round(r * 100) + "%";
    }
    function k(e, r, o) {
      return !!e.status;
    }
    function d(e, r, o, t = "") {
      let l = "inherit";
      const f = S(Object.values(e.extensionState ?? {})).filter(k).map(({ status: n }) => {
        let h = [], s = l, $ = "", c = "";
        return n.type === u.Warning && (c = "▲", s = "Orange"), n.type === u.Error && (c = "✖︎", s = "OrangeRed"), n.type === u.Success && (c = "✔", s = "YellowGreen"), n.type === u.Info && (c = "i", s = "SkyBlue"), n.type === u.System && (n.code.includes("BUSY") ? (c = "⧗", $ = ` ${U(n.progress)}`) : n.code.includes("COMPLETE") ? c = "✔" : c = "•", s = "Grey"), h.push({ label: `${c} ${n.code}${$}`, color: s }), h;
      }).flat();
      let i = `%c%s %o	  %c${r}%c${o}%c${t} ${T(
        ...f.map(({ label: n }) => `%c ${n}`)
      )}`;
      i += " ".repeat(Math.max(0, 60 - i.length)) + "", m(
        ...S([
          i,
          "color:grey",
          e.id,
          { "🔍": O(e) },
          "color:grey",
          "color:" + l,
          "color:grey",
          ...f.flat().map(({ color: n }) => `color:${n}`)
        ])
      );
    }
    function A(e, r) {
      d(
        e,
        r,
        e.name ?? e?.state.src ?? "",
        // @ts-ignore
        "size" in e ? ` (${P(e.size)})` : ""
      );
    }
    function M(e, r) {
      d(e, r, e.name + "/");
    }
    function g(e, r, o) {
      e.forEach((t, l) => {
        let a = "";
        const f = l === e.length - 1;
        let i = [...o];
        if (r > 0 && (a = (f ? "└──" : "├──") + " "), D(t))
          return M(t, i.join("") + a), r > 0 && i.push(f ? "    " : "│   "), g(t.entries, r + 1, i);
        A(t, i.join("") + a);
      });
    }
    let y;
    function v() {
      const { debounce: e, clearBeforeLog: r } = w, o = () => {
        const t = B();
        r && R(), (t.length > 1 || r) && m(`
 handleUpdateEntries(%o)

`, t), g(t, 0, []);
      };
      cancelAnimationFrame(y), e ? y = requestAnimationFrame(o) : o();
    }
    if (window) {
      const e = `$pond${E}`, r = window[e] = {
        insertEntries: b,
        removeEntries: L,
        updateEntry: F
      };
      m(
        `%c${x}: %cFilePond instance available for debugging at %cwindow%c.%c${e}`,
        "color:grey",
        "color:auto",
        "color:grey",
        "color:grey",
        "color:auto",
        { "🔍": r }
      ), E++;
    }
    const z = C("updateEntries", v);
    return {
      destroy: () => {
        z();
      }
    };
  }
});
export {
  X as ConsoleView
};
