/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as i } from "../../vendor/svelte/src/internal/client/runtime.js";
import { proxy as a } from "../../vendor/svelte/src/internal/client/proxy.js";
import { state as g, set as v } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_derived as M } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { createAnimationGuard as A } from "./animationGuard.js";
import { isBrowser as y } from "../../utils/test.js";
import { addListener as r } from "../../utils/dom.js";
let s = a({ current: null });
const u = [], f = /* @__PURE__ */ new Set();
function P(e) {
  f.add(e.pointerId);
}
function d(e) {
  f.delete(e.pointerId);
}
const l = A();
l.on("change", b);
function b(e) {
  s.current = !e;
}
const G = l.register("window");
function E() {
  G.prevent();
}
let m, t = null, p = a({ current: !1 });
function c() {
  t && (p.current = t.matches);
}
function I() {
  y() && (u.push(r(window, "pointerdown", P), r(window, "pointerup", d), r(window, "pointercancel", d)), t = window.matchMedia("(prefers-reduced-motion: reduce)"), t.addEventListener("change", c), c(), m = r(window, "resize", E));
}
function L() {
  u.forEach((e) => e()), u.length = 0, m?.(), t?.removeEventListener("change", c), t = null;
}
let o = 0;
function B() {
  o === 0 && I(), o++;
  let e = g(a({ current: "auto" }));
  const w = M(() => {
    const n = !s.current, h = !p.current;
    return i(e).current === "auto" ? { current: h && n } : i(e).current === "always" ? { current: n } : { current: !1 };
  });
  return {
    get current() {
      return i(w).current;
    },
    setPreference(n = "auto") {
      v(e, { current: n }, !0);
    },
    destroy() {
      o--, o === 0 && L();
    }
  };
}
export {
  B as createAnimationModeObserver
};
