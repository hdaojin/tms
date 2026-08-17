/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { noop as b } from "../../utils/placeholder.js";
import { sizeCreate as p, sizeUpdate as l, sizeEqual as v, sizeUpdateWithSize as d } from "../../utils/size.js";
import { getSuspensionObserver as O } from "../common/dom.js";
let u;
function h() {
  u = O(), u.on("suspend", (e) => {
    for (const s of i.keys())
      e.contains(s) && f.set(s, !0);
  });
}
const o = p(), c = /* @__PURE__ */ new Map(), i = /* @__PURE__ */ new Map(), f = /* @__PURE__ */ new Map(), m = (e, s, t) => {
  if (f.has(e))
    return;
  c.has(e) || c.set(e, p());
  const n = c.get(e);
  l(o, s, t), !v(n, o) && (d(n, o), i.get(e)(n));
};
let a = 0, r;
function S() {
  r = new ResizeObserver((e) => {
    e.forEach((s) => {
      const t = s.target, { width: n, height: z } = s.contentRect;
      m(t, n, z);
    });
  });
}
function R(e = {}) {
  const { onresize: s = b } = e;
  return (t) => (r || S(), u || h(), i.set(t, s), r.observe(t), a++, () => {
    r.unobserve(t), i.delete(t), f.delete(t), a--, a === 0 && (r.disconnect(), r = null);
  });
}
export {
  R as resizable
};
