/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { boundsOutsideBounds as b } from "../../utils/bounds.js";
import { pubsub as d } from "../../utils/pubsub.js";
import { isFunction as g, isObject as m, isArray as x, isBoolean as O, isNullOrUndefined as y } from "../../utils/test.js";
function D(t, e, r) {
  const { cacheClientRectangles: n = 250, searchBounds: u } = r;
  let f, a = Number.MAX_SAFE_INTEGER;
  if (t.length === 1)
    return t[0];
  let p = Date.now();
  for (const i of t) {
    let s;
    const o = l.get(i);
    if (o && p - o.ts < n ? s = o.clientRect : s = i.getBoundingClientRect(), u && b(s, u)) {
      l.set(i, { clientRect: s, ts: p });
      continue;
    }
    const h = A(s, e);
    h < a && (a = h, f = i);
  }
  return f;
}
const l = /* @__PURE__ */ new WeakMap();
function A(t, e) {
  const r = Math.max(t.x - e.x, 0, e.x - (t.x + t.width)), n = Math.max(t.y - e.y, 0, e.y - (t.y + t.height));
  return Math.hypot(r, n);
}
function M() {
  const { on: t, pub: e } = d();
  return {
    on: t,
    suspend(r) {
      r.setAttribute("suspend", ""), e("suspend", r);
    }
  };
}
let c;
function E() {
  return c || (c = M()), c;
}
function T(t) {
  return Object.entries(t).reduce((e, [r, n]) => (g(n) && !r.startsWith("on") || m(n) || x(n) || O(n) || y(n) || (e[r] = n), e), {});
}
export {
  D as getClosestElement,
  E as getSuspensionObserver,
  T as propsToAttributes
};
