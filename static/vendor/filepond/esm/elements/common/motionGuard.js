/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { arrayAddUnique as c, arrayRemove as l } from "../../utils/array.js";
import { pubsub as m } from "../../utils/pubsub.js";
function d({ timeout: i = 100 }) {
  const { on: a, pub: r } = m();
  let e = !0, t = [];
  return {
    on: a,
    register(o) {
      let n;
      return {
        prevent() {
          t = c(t, o), e && (e = !1, r("change", !e)), clearTimeout(n), n = setTimeout(() => {
            t = l(t, (s) => s === o);
            const u = t.length === 0;
            u !== e && (e = u, r("change", !e));
          }, i);
        }
      };
    }
  };
}
export {
  d as createMotionGuard
};
