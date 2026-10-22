import { is_function as S, noop as h } from "../../../shared/utils.js";
import { effect as x } from "../../reactivity/effects.js";
import { active_effect as B, untrack as M } from "../../runtime.js";
import { loop as j } from "../../loop.js";
import { should_intro as q } from "../../render.js";
import { TRANSITION_GLOBAL as G } from "../../../../constants.js";
import { EFFECT_TRANSPARENT as K, BLOCK_EFFECT as P, REACTION_RAN as U } from "../../constants.js";
import { queue_micro_task as k } from "../task.js";
import { without_reactive_context as L } from "./bindings/shared.js";
function T(t, r) {
  L(() => {
    t.dispatchEvent(new CustomEvent(r));
  });
}
function W(t) {
  if (t === "float") return "cssFloat";
  if (t === "offset") return "cssOffset";
  if (t.startsWith("--")) return t;
  const r = t.split("-");
  return r.length === 1 ? r[0] : r[0] + r.slice(1).map(
    /** @param {any} word */
    (o) => o[0].toUpperCase() + o.slice(1)
  ).join("");
}
function I(t) {
  const r = {}, o = t.split(";");
  for (const a of o) {
    const [e, n] = a.split(":");
    if (!e || n === void 0) break;
    const c = W(e.trim());
    r[c] = n.trim();
  }
  return r;
}
const z = (t) => t;
function rr(t, r, o, a) {
  var e = (t & G) !== 0, n = "both", c, m = r.inert, d = r.style.overflow, p, u;
  function s() {
    return L(() => c ??= o()(r, a?.() ?? /** @type {P} */
    {}, {
      direction: n
    }));
  }
  var _ = {
    is_global: e,
    in() {
      r.inert = m, p = C(
        r,
        s(),
        u,
        1,
        () => {
          T(r, "introstart");
        },
        () => {
          T(r, "introend"), p?.abort(), p = c = void 0, r.style.overflow = d;
        }
      );
    },
    out(l) {
      r.inert = !0, u = C(
        r,
        s(),
        p,
        0,
        () => {
          T(r, "outrostart");
        },
        () => {
          T(r, "outroend"), l?.();
        }
      );
    },
    stop: () => {
      p?.abort(), u?.abort();
    }
  }, i = (
    /** @type {Effect & { nodes: EffectNodes }} */
    B
  );
  if ((i.nodes.t ??= []).push(_), q) {
    var v = e;
    if (!v) {
      for (var f = (
        /** @type {Effect | null} */
        i.parent
      ); f && (f.f & K) !== 0; )
        for (; (f = f.parent) && (f.f & P) === 0; )
          ;
      v = !f || (f.f & U) !== 0;
    }
    v && x(() => {
      M(() => _.in());
    });
  }
}
function C(t, r, o, a, e, n) {
  var c = a === 1, m = !1;
  if (S(r)) {
    var d;
    return k(() => {
      if (!m) {
        var f = r({ direction: c ? "in" : "out" });
        d = C(t, f, o, a, e, n);
      }
    }), {
      abort: () => {
        m = !0, d?.abort();
      },
      deactivate: () => d.deactivate(),
      reset: () => d.reset(),
      t: () => d.t()
    };
  }
  if (o?.deactivate(), !r?.duration && !r?.delay)
    return e(), n(), {
      abort: h,
      deactivate: h,
      reset: h,
      t: () => a
    };
  const { delay: p = 0, css: u, tick: s, easing: _ = z } = r;
  var i, v = () => 1 - a;
  return k(() => {
    if (!m) {
      var f = [];
      if (c && o === void 0 && (s && s(0, 1), u)) {
        var l = I(u(0, 1));
        f.push(l, l);
      }
      i = t.animate(f, { duration: p, fill: "forwards" }), i.onfinish = () => {
        i.cancel(), e();
        var y = o?.t() ?? 1 - a;
        o?.abort();
        var b = a - y, w = (
          /** @type {number} */
          r.duration * Math.abs(b)
        ), N = [];
        if (w > 0) {
          var F = !1;
          if (u)
            for (var O = Math.ceil(w / 16.666666666666668), A = 0; A <= O; A += 1) {
              var R = y + b * _(A / O), g = I(u(R, 1 - R));
              N.push(g), F ||= g.overflow === "hidden";
            }
          F && (t.style.overflow = "hidden"), v = () => {
            var E = (
              /** @type {number} */
              /** @type {globalThis.Animation} */
              i.currentTime
            );
            return y + b * _(E / w);
          }, s && j(() => {
            if (i.playState !== "running") return !1;
            var E = v();
            return s(E, 1 - E), !0;
          });
        }
        i = t.animate(N, { duration: w, fill: "forwards" }), i.onfinish = () => {
          v = () => a, s?.(a, 1 - a), n();
        };
      };
    }
  }), {
    abort: () => {
      m = !0, i && (i.cancel(), i.effect = null, i.onfinish = h);
    },
    deactivate: () => {
      n = h;
    },
    reset: () => {
      a === 0 && s?.(1, 0);
    },
    t: () => v()
  };
}
export {
  rr as transition
};
