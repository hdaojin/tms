/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { arrayRemoveInPlace as R } from "../../utils/array.js";
import { boundsCreate as w, boundsUpdate as V, boundsEqual as C, boundsUpdateWithBounds as A } from "../../utils/bounds.js";
import { getSuspensionObserver as B } from "../common/dom.js";
const y = 100, l = /* @__PURE__ */ new Map();
let o = null;
function M() {
  function t() {
    return !document.hidden;
  }
  o = {
    visible: t(),
    destroy: () => {
      document.removeEventListener("visibilitychange", e);
    }
  };
  function e() {
    o && (o.visible = t()), t() ? h() : O();
  }
  document.addEventListener("visibilitychange", e), e();
}
let p;
function N() {
  p = B(), p.on("suspend", (t) => {
    for (const e of a)
      t.contains(e) && g.add(e);
  });
}
let u = null;
function S() {
  const t = {
    // viewport
    root: null,
    // we're interested in elements near the viewport
    // rootMargin: `0px 0px 0px 0px`,
    rootMargin: `${y}px 0px 0px ${y}px`,
    // if one pixel is visible we detect it
    threshold: 0
  }, e = new IntersectionObserver((r) => {
    r.forEach((n) => {
      const i = n.boundingClientRect, s = n.target;
      if (!l.has(s) || d.has(s) && !n.isIntersecting && i.x === 0 && i.y === 0 && i.width === 0 && i.height === 0)
        return;
      d.set(s, n.isIntersecting);
      const b = Array.from(d.values()).some(Boolean);
      if (u && (u.visible = b), b ? h() : O(), c.has(s))
        return;
      const I = x(s, i.top, i.right, i.bottom, i.left);
      l.get(s).onmeasuresync?.(I), m.push(s), a.push(s), b && h();
    });
  }, t);
  u = {
    unobserve: (r) => {
      e.unobserve(r);
    },
    observe: (r) => {
      e.observe(r);
    },
    visible: !1
  };
}
const v = w(), c = /* @__PURE__ */ new Map(), d = /* @__PURE__ */ new Map(), g = /* @__PURE__ */ new Set(), m = [];
function x(t, e, r, n, i) {
  if (!l.has(t) || g.has(t))
    return;
  c.has(t) || c.set(t, w());
  const s = c.get(t);
  if (V(v, e, r, n, i), !C(s, v))
    return A(s, v), s;
}
function q(t) {
  const e = t.getBoundingClientRect();
  return x(
    t,
    e.top,
    e.right,
    e.bottom,
    e.left
  );
}
const a = [];
let f = null;
function E() {
  a.filter((e) => q(e)).forEach((e) => {
    l.get(e)?.onmeasure?.(c.get(e));
  }), m.forEach((e) => {
    l.get(e)?.onmeasure?.(c.get(e));
  }), m.length = 0, f = requestAnimationFrame(E);
}
function h() {
  f === null && (!o?.visible || !u?.visible || (f = requestAnimationFrame(E)));
}
function O() {
  f !== null && (cancelAnimationFrame(f), f = null);
}
function L(t = {}) {
  const { onmeasure: e, onmeasuresync: r } = t;
  return (n) => {
    u || S(), o || M(), p || N(), l.set(n, { onmeasure: e, onmeasuresync: r }), u?.observe(n);
    function i() {
      const s = a.indexOf(n);
      s >= 0 && a.splice(s, 1), u?.unobserve(n), R(m, (b) => b === n), g.delete(n), d.delete(n), c.delete(n), l.delete(n), a.length || (O(), o?.destroy(), o = null);
    }
    return i;
  };
}
export {
  y as VIEWPORT_MARGIN,
  L as measurable
};
