/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { boundsOutsideBounds as g } from "../../utils/bounds.js";
import { pubsub as h } from "../../utils/pubsub.js";
import { isFunction as l, isObject as m, isArray as x, isBoolean as y, isNullOrUndefined as O, isString as w } from "../../utils/test.js";
function S(t, e, r) {
  const { cacheClientRectangles: n = 250, searchBounds: u } = r;
  let a, f = Number.MAX_SAFE_INTEGER;
  if (t.length === 1)
    return t[0];
  let b = Date.now();
  for (const i of t) {
    let s;
    const o = d.get(i);
    if (o && b - o.ts < n ? s = o.clientRect : s = i.getBoundingClientRect(), u && g(s, u)) {
      d.set(i, { clientRect: s, ts: b });
      continue;
    }
    const p = T(s, e);
    p < f && (f = p, a = i);
  }
  return a;
}
const d = /* @__PURE__ */ new WeakMap();
function T(t, e) {
  const r = Math.max(t.x - e.x, 0, e.x - (t.x + t.width)), n = Math.max(t.y - e.y, 0, e.y - (t.y + t.height));
  return Math.hypot(r, n);
}
function A() {
  const { on: t, pub: e } = h();
  return {
    on: t,
    suspend(r) {
      r.setAttribute("suspend", ""), e("suspend", r);
    }
  };
}
let c;
function B() {
  return c || (c = A()), c;
}
function D(t) {
  return Object.entries(t).reduce((e, [r, n]) => (l(n) && !r.startsWith("on") || m(n) || x(n) || y(n) || O(n) || (e[r] = n), e), {});
}
function R(t) {
  return w(t) && C.has(t.toLowerCase());
}
const C = /* @__PURE__ */ new Set([
  "area",
  "base",
  "br",
  "col",
  "command",
  "embed",
  "hr",
  "img",
  "input",
  "keygen",
  "param",
  "source",
  "track",
  "wbr"
]);
export {
  S as getClosestElement,
  B as getSuspensionObserver,
  R as isVoidElementTag,
  D as propsToAttributes
};
