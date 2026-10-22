/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { proxy as c } from "../../vendor/svelte/src/internal/client/proxy.js";
import { addListener as s } from "../../utils/dom.js";
import { isBrowser as a } from "../../utils/test.js";
import { createMotionGuard as f } from "./motionGuard.js";
const i = c({ prefersReducedMotion: void 0, reduceMotion: !1 }), u = f({ timeout: 100 });
u.on("change", (o) => {
  i.reduceMotion = o;
});
let d;
const M = u.register("window");
function m() {
  M.prevent();
}
let e = null;
function n() {
  e && (i.prefersReducedMotion = e.matches);
}
function l() {
  a() && (d = s(window, "resize", m), e = window.matchMedia("(prefers-reduced-motion: reduce)"), e.addEventListener("change", n), n());
}
function p() {
  d?.(), e?.removeEventListener("change", n), e = null;
}
let r = 0;
function R() {
  return r === 0 && l(), r++, {
    get current() {
      return i;
    },
    destroy() {
      r--, r === 0 && p();
    }
  };
}
function y(o, t = "auto") {
  return t === "on" || t === "" ? !0 : t === "off" ? o.reduceMotion : o.prefersReducedMotion || o.reduceMotion;
}
export {
  R as createMotionStateObserver,
  y as shouldReduceMotion
};
