/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { boundsCreate as w, boundsUpdate as V, boundsEqual as C, boundsUpdateWithBounds as E } from "../../utils/bounds.js";
import { noop as I } from "../../utils/placeholder.js";
import { getSuspensionObserver as R } from "../common/dom.js";
const O = 100, b = /* @__PURE__ */ new Map();
let r = null;
function A() {
  function e() {
    return !document.hidden;
  }
  r = {
    visible: e(),
    destroy: () => {
      document.removeEventListener("visibilitychange", t);
    }
  };
  function t() {
    r && (r.visible = e()), e() ? p() : g();
  }
  document.addEventListener("visibilitychange", t), t();
}
let m;
function B() {
  m = R(), m.on("suspend", (e) => {
    for (const t of l)
      e.contains(t) && h.add(t);
  });
}
let u = null;
function M() {
  const e = {
    // viewport
    root: null,
    // we're interested in elements near the viewport
    // rootMargin: `0px 0px 0px 0px`,
    rootMargin: `${O}px 0px 0px ${O}px`,
    // if one pixel is visible we detect it
    threshold: 1
  }, t = new IntersectionObserver((o) => {
    o.forEach((n) => {
      const s = n.boundingClientRect, i = n.target;
      if (f.has(i) && !n.isIntersecting && s.x === 0 && s.y === 0 && s.width === 0 && s.height === 0)
        return;
      f.set(i, n.isIntersecting);
      const d = Array.from(f.values()).some(Boolean);
      u && (u.visible = d), d ? p() : g(), !a.has(i) && (x(i, s.top, s.right, s.bottom, s.left), l.push(i), d && p());
    });
  }, e);
  u = {
    unobserve: (o) => {
      t.unobserve(o);
    },
    observe: (o) => {
      t.observe(o);
    },
    visible: !1
  };
}
const v = w(), a = /* @__PURE__ */ new Map(), f = /* @__PURE__ */ new Map(), h = /* @__PURE__ */ new Set(), x = (e, t, o, n, s) => {
  if (!b.has(e) || h.has(e))
    return;
  a.has(e) || a.set(e, w());
  const i = a.get(e);
  if (V(v, t, o, n, s), !C(i, v))
    return E(i, v), b.get(e)(i), i;
}, S = (e) => {
  const t = e.getBoundingClientRect();
  x(e, t.top, t.right, t.bottom, t.left);
}, l = [];
let c = null;
function y() {
  l.forEach(S), c = requestAnimationFrame(y);
}
function p() {
  !r?.visible || !u?.visible || c === null && (c = requestAnimationFrame(y));
}
function g() {
  c !== null && (cancelAnimationFrame(c), c = null);
}
function k(e = {}) {
  const { disabled: t, onmeasure: o = I } = e;
  return (n) => {
    if (t)
      return () => {
      };
    u || M(), r || A(), m || B(), b.set(n, o), u?.observe(n);
    function s() {
      const i = l.indexOf(n);
      i >= 0 && l.splice(i, 1), u?.unobserve(n), h.delete(n), f.delete(n), a.delete(n), b.delete(n), l.length || (g(), r?.destroy(), r = null);
    }
    return s;
  };
}
export {
  O as VIEWPORT_MARGIN,
  k as measurable
};
