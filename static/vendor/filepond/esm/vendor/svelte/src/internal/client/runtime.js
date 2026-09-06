import rf from "../../../../esm-env/false.js";
import { index_of as tf, includes as x } from "../shared/utils.js";
import { destroy_block_effect_children as lf, destroy_effect_children as uf, execute_effect_teardown as ef, effect_tracking as nf } from "./reactivity/effects.js";
import { CONNECTED as c, REACTION_RAN as U, ERROR_VALUE as F, DERIVED as A, DIRTY as C, MAYBE_DIRTY as Y, DESTROYED as V, CLEAN as O, BLOCK_EFFECT as _f, MANAGED_EFFECT as sf, BRANCH_EFFECT as z, ROOT_EFFECT as G, REACTION_IS_UPDATING as b, WAS_MARKED as K, STALE_REACTION as H } from "./constants.js";
import { old_values as I } from "./reactivity/sources.js";
import { update_derived as P, unfreeze_derived_effects as W, freeze_derived_effects as of, execute_derived as af } from "./reactivity/deriveds.js";
import { tracing_mode_flag as pf } from "../flags/index.js";
import { UNINITIALIZED as Z } from "../../constants.js";
import { set_component_context as M, is_runes as vf, component_context as cf } from "./context.js";
import { batch_values as y, current_batch as mf, schedule_effect as hf } from "./reactivity/batch.js";
import { handle_error as Ef } from "./error-handling.js";
import { without_reactive_context as j } from "./dom/elements/bindings/shared.js";
import { set_signal_status as w, update_derived_status as Af } from "./reactivity/status.js";
let N = !1, L = !1;
function Sf(f) {
  L = f;
}
let n = null, v = !1;
function Yf(f) {
  n = f;
}
let T = null;
function Bf(f) {
  T = f;
}
let m = null;
function Mf(f) {
  n !== null && (m ??= /* @__PURE__ */ new Set()).add(f);
}
let s = null, a = 0, p = null;
function Uf(f) {
  p = f;
}
let q = 1, E = 0, k = E;
function Vf(f) {
  k = f;
}
function zf() {
  return ++q;
}
function J(f) {
  var r = f.f;
  if ((r & C) !== 0)
    return !0;
  if (r & A && (f.f &= ~K), (r & Y) !== 0) {
    for (var l = (
      /** @type {Value[]} */
      f.deps
    ), e = l.length, u = 0; u < e; u++) {
      var t = l[u];
      if (J(
        /** @type {Derived} */
        t
      ) && P(
        /** @type {Derived} */
        t
      ), t.wv > f.wv)
        return !0;
    }
    (r & c) !== 0 && // During time traveling we don't want to reset the status so that
    // traversal of the graph in the other batches still happens
    y === null && w(f, O);
  }
  return !1;
}
function Q(f, r, l = !0) {
  var e = f.reactions;
  if (e !== null && !(m !== null && m.has(f)))
    for (var u = 0; u < e.length; u++) {
      var t = e[u];
      (t.f & A) !== 0 ? Q(
        /** @type {Derived} */
        t,
        r,
        !1
      ) : r === t && (l ? w(t, C) : (t.f & O) !== 0 && w(t, Y), hf(
        /** @type {Effect} */
        t
      ));
    }
}
function Tf(f) {
  var r = s, l = a, e = p, u = n, t = m, _ = cf, R = v, D = k, g = f.f;
  s = /** @type {null | Value[]} */
  null, a = 0, p = null, n = (g & (z | G)) === 0 ? f : null, m = null, M(f.ctx), v = !1, k = ++E, f.ac !== null && (j(() => {
    f.ac.abort(H);
  }), f.ac = null);
  try {
    f.f |= b;
    var d = (
      /** @type {Function} */
      f.fn
    ), ff = d();
    f.f |= U;
    var i = f.deps, B = mf?.is_fork;
    if (s !== null) {
      var o;
      if (B || S(f, a), i !== null && a > 0)
        for (i.length = a + s.length, o = 0; o < s.length; o++)
          i[a + o] = s[o];
      else
        f.deps = i = s;
      if (nf() && (f.f & c) !== 0)
        for (o = a; o < i.length; o++)
          (i[o].reactions ??= []).push(f);
    } else !B && i !== null && a < i.length && (S(f, a), i.length = a);
    if (vf() && p !== null && !v && i !== null && (f.f & (A | Y | C)) === 0)
      for (o = 0; o < /** @type {Source[]} */
      p.length; o++)
        Q(
          p[o],
          /** @type {Effect} */
          f
        );
    if (u !== null && u !== f) {
      if (E++, u.deps !== null)
        for (let h = 0; h < l; h += 1)
          u.deps[h].rv = E;
      if (r !== null)
        for (const h of r)
          h.rv = E;
      p !== null && (e === null ? e = p : e.push(.../** @type {Source[]} */
      p));
    }
    return (f.f & F) !== 0 && (f.f ^= F), ff;
  } catch (h) {
    return Ef(h);
  } finally {
    f.f ^= b, s = r, a = l, p = e, n = u, m = t, M(_), v = R, k = D;
  }
}
function Rf(f, r) {
  let l = r.reactions;
  if (l !== null) {
    var e = tf.call(l, f);
    if (e !== -1) {
      var u = l.length - 1;
      u === 0 ? l = r.reactions = null : (l[e] = l[u], l.pop());
    }
  }
  if (l === null && (r.f & A) !== 0 && // Destroying a child effect while updating a parent effect can cause a dependency to appear
  // to be unused, when in fact it is used by the currently-updating parent. Checking `new_deps`
  // allows us to skip the expensive work of disconnecting and immediately reconnecting it
  (s === null || !x.call(s, r))) {
    var t = (
      /** @type {Derived} */
      r
    );
    (t.f & c) !== 0 && (t.f ^= c, t.f &= ~K), t.v !== Z && Af(t), t.ac !== null && j(() => {
      t.ac.abort(H), t.ac = null, w(t, C);
    }), of(t), S(t, 0);
  }
}
function S(f, r) {
  var l = f.deps;
  if (l !== null)
    for (var e = r; e < l.length; e++)
      Rf(f, l[e]);
}
function Gf(f) {
  var r = f.f;
  if ((r & V) === 0) {
    w(f, O);
    var l = T, e = N;
    T = f, N = (r & (z | G)) === 0;
    try {
      (r & (_f | sf)) !== 0 ? lf(f) : uf(f), ef(f);
      var u = Tf(f);
      f.teardown = typeof u == "function" ? u : null, f.wv = q;
      var t;
      rf && pf && (f.f & C) !== 0 && f.deps;
    } finally {
      N = e, T = l;
    }
  }
}
function Kf(f) {
  var r = f.f, l = (r & A) !== 0;
  if (n !== null && !v) {
    var e = T !== null && (T.f & V) !== 0;
    if (!e && (m === null || !m.has(f))) {
      var u = n.deps;
      if ((n.f & b) !== 0)
        f.rv < E && (f.rv = E, s === null && u !== null && u[a] === f ? a++ : s === null ? s = [f] : s.push(f));
      else {
        n.deps ??= [], x.call(n.deps, f) || n.deps.push(f);
        var t = f.reactions;
        t === null ? f.reactions = [n] : x.call(t, n) || t.push(n);
      }
    }
  }
  if (L && I.has(f))
    return I.get(f);
  if (l) {
    var _ = (
      /** @type {Derived} */
      f
    );
    if (L) {
      var R = _.v;
      return ((_.f & O) === 0 && _.reactions !== null || $(_)) && (R = af(_)), I.set(_, R), R;
    }
    var D = (_.f & c) === 0 && !v && n !== null && (N || (n.f & c) !== 0), g = (_.f & U) === 0;
    J(_) && (D && (_.f |= c), P(_)), D && !g && (W(_), X(_));
  }
  if (y?.has(f))
    return y.get(f);
  if ((f.f & F) !== 0)
    throw f.v;
  return f.v;
}
function X(f) {
  if (f.f |= c, f.deps !== null)
    for (const r of f.deps)
      (r.reactions ??= []).push(f), (r.f & A) !== 0 && (r.f & c) === 0 && (W(
        /** @type {Derived} */
        r
      ), X(
        /** @type {Derived} */
        r
      ));
}
function $(f) {
  if (f.v === Z) return !0;
  if (f.deps === null) return !1;
  for (const r of f.deps)
    if (I.has(r) || (r.f & A) !== 0 && $(
      /** @type {Derived} */
      r
    ))
      return !0;
  return !1;
}
function Hf(f) {
  var r = v;
  try {
    return v = !0, f();
  } finally {
    v = r;
  }
}
export {
  T as active_effect,
  n as active_reaction,
  m as current_sources,
  Kf as get,
  zf as increment_write_version,
  L as is_destroying_effect,
  J as is_dirty,
  s as new_deps,
  Mf as push_reaction_value,
  S as remove_reactions,
  Bf as set_active_effect,
  Yf as set_active_reaction,
  Sf as set_is_destroying_effect,
  Uf as set_untracked_writes,
  Vf as set_update_version,
  a as skipped_deps,
  Hf as untrack,
  p as untracked_writes,
  v as untracking,
  Gf as update_effect,
  Tf as update_reaction,
  k as update_version,
  q as write_version
};
