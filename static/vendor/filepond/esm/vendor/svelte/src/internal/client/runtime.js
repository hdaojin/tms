import ff from "../../../../esm-env/false.js";
import { index_of as rf, includes as g } from "../shared/utils.js";
import { destroy_block_effect_children as tf, destroy_effect_children as ef, execute_effect_teardown as lf, effect_tracking as uf } from "./reactivity/effects.js";
import { CONNECTED as p, REACTION_RAN as B, ERROR_VALUE as x, DERIVED as h, DIRTY as w, MAYBE_DIRTY as L, DESTROYED as U, CLEAN as D, BLOCK_EFFECT as nf, MANAGED_EFFECT as sf, BRANCH_EFFECT as V, ROOT_EFFECT as z, REACTION_IS_UPDATING as N, STALE_REACTION as G } from "./constants.js";
import { old_values as R } from "./reactivity/sources.js";
import { update_derived as M, unfreeze_derived_effects as H, freeze_derived_effects as _f, execute_derived as of } from "./reactivity/deriveds.js";
import { tracing_mode_flag as af } from "../flags/index.js";
import { UNINITIALIZED as K } from "../../constants.js";
import { set_component_context as S, is_runes as pf, component_context as vf } from "./context.js";
import { batch_values as F, current_batch as cf, schedule_effect as mf } from "./reactivity/batch.js";
import { handle_error as hf } from "./error-handling.js";
import { without_reactive_context as P } from "./dom/elements/bindings/shared.js";
import { set_signal_status as k, update_derived_status as Ef } from "./reactivity/status.js";
let C = !1, b = !1;
function yf(f) {
  b = f;
}
let n = null, a = !1;
function Lf(f) {
  n = f;
}
let E = null;
function Sf(f) {
  E = f;
}
let v = null;
function Yf(f) {
  n !== null && ((n.f & N) !== 0 || (n.f & h) !== 0) && (v ??= /* @__PURE__ */ new Set()).add(f);
}
let _ = null, o = 0, i = null;
function Bf(f) {
  i = f;
}
let Z = 1, m = 0, I = m;
function Uf(f) {
  I = f;
}
function Vf() {
  return ++Z;
}
function j(f) {
  var r = f.f;
  if ((r & w) !== 0)
    return !0;
  if ((r & L) !== 0) {
    for (var l = (
      /** @type {Value[]} */
      f.deps
    ), t = l.length, u = 0; u < t; u++) {
      var e = l[u];
      if (j(
        /** @type {Derived} */
        e
      ) && M(
        /** @type {Derived} */
        e
      ), e.wv > f.wv)
        return !0;
    }
    (r & p) !== 0 && // During time traveling we don't want to reset the status so that
    // traversal of the graph in the other batches still happens
    F === null && k(f, D);
  }
  return !1;
}
function q(f, r, l = !0) {
  var t = f.reactions;
  if (t !== null && !(v !== null && v.has(f)))
    for (var u = 0; u < t.length; u++) {
      var e = t[u];
      (e.f & h) !== 0 ? q(
        /** @type {Derived} */
        e,
        r,
        !1
      ) : r === e && (l ? k(e, w) : (e.f & D) !== 0 && k(e, L), mf(
        /** @type {Effect} */
        e
      ));
    }
}
function Tf(f) {
  var r = _, l = o, t = i, u = n, e = v, s = vf, T = a, A = I, O = f.f;
  _ = /** @type {null | Value[]} */
  null, o = 0, i = null, n = (O & (V | z)) === 0 ? f : null, v = null, S(f.ctx), a = !1, I = ++m, f.ac !== null && (P(() => {
    f.ac.abort(G);
  }), f.ac = null);
  try {
    f.f |= N;
    var W = (
      /** @type {Function} */
      f.fn
    ), X = W();
    f.f |= B;
    var $ = Y(f);
    if (pf() && i !== null && !a && $ !== null && (f.f & (h | L | w)) === 0)
      for (var d = 0; d < /** @type {Source[]} */
      i.length; d++)
        q(
          i[d],
          /** @type {Effect} */
          f
        );
    if (u !== null && u !== f) {
      if (m++, u.deps !== null)
        for (let c = 0; c < l; c += 1)
          u.deps[c].rv = m;
      if (r !== null)
        for (const c of r)
          c.rv = m;
      i !== null && (t === null ? t = i : t.push(.../** @type {Source[]} */
      i));
    }
    return (f.f & x) !== 0 && (f.f ^= x), X;
  } catch (c) {
    return Y(f), hf(c);
  } finally {
    f.f ^= N, _ = r, o = l, i = t, n = u, v = e, S(s), a = T, I = A;
  }
}
function Y(f) {
  var r = f.deps, l = cf?.is_fork;
  if (_ !== null) {
    var t;
    if (l || y(f, o), r !== null && o > 0)
      for (r.length = o + _.length, t = 0; t < _.length; t++)
        r[o + t] = _[t];
    else
      f.deps = r = _;
    if (uf() && (f.f & p) !== 0)
      for (t = o; t < r.length; t++)
        (r[t].reactions ??= []).push(f);
  } else !l && r !== null && o < r.length && (y(f, o), r.length = o);
  return r;
}
function kf(f, r) {
  let l = r.reactions;
  if (l !== null) {
    var t = rf.call(l, f);
    if (t !== -1) {
      var u = l.length - 1;
      u === 0 ? l = r.reactions = null : (l[t] = l[u], l.pop());
    }
  }
  if (l === null && (r.f & h) !== 0 && // Destroying a child effect while updating a parent effect can cause a dependency to appear
  // to be unused, when in fact it is used by the currently-updating parent. Checking `new_deps`
  // allows us to skip the expensive work of disconnecting and immediately reconnecting it
  (_ === null || !g.call(_, r))) {
    var e = (
      /** @type {Derived} */
      r
    );
    (e.f & p) !== 0 && (e.f ^= p), e.v !== K && Ef(e), e.ac !== null && P(() => {
      e.ac.abort(G), e.ac = null, k(e, w);
    }), _f(e), y(e, 0);
  }
}
function y(f, r) {
  var l = f.deps;
  if (l !== null)
    for (var t = r; t < l.length; t++)
      kf(f, l[t]);
}
function zf(f) {
  var r = f.f;
  if ((r & U) === 0) {
    k(f, D);
    var l = E, t = C;
    E = f, C = (r & (V | z)) === 0;
    try {
      (r & (nf | sf)) !== 0 ? tf(f) : ef(f), lf(f);
      var u = Tf(f);
      f.teardown = typeof u == "function" ? u : null, f.wv = Z;
      var e;
      ff && af && (f.f & w) !== 0 && f.deps;
    } finally {
      C = t, E = l;
    }
  }
}
function Gf(f) {
  var r = f.f, l = (r & h) !== 0;
  if (n !== null && !a) {
    var t = E !== null && (E.f & U) !== 0;
    if (!t && (v === null || !v.has(f))) {
      var u = n.deps;
      if ((n.f & N) !== 0)
        f.rv < m && (f.rv = m, _ === null && u !== null && u[o] === f ? o++ : _ === null ? _ = [f] : _.push(f));
      else {
        n.deps ??= [], g.call(n.deps, f) || n.deps.push(f);
        var e = f.reactions;
        e === null ? f.reactions = [n] : g.call(e, n) || e.push(n);
      }
    }
  }
  if (b && R.has(f))
    return R.get(f);
  if (l) {
    var s = (
      /** @type {Derived} */
      f
    );
    if (b) {
      var T = s.v;
      return ((s.f & D) === 0 && s.reactions !== null || Q(s)) && (T = of(s)), R.set(s, T), T;
    }
    var A = (s.f & p) === 0 && !a && n !== null && (C || (n.f & p) !== 0), O = (s.f & B) === 0;
    j(s) && (A && (s.f |= p), M(s)), A && !O && (H(s), J(s));
  }
  if (F?.has(f))
    return F.get(f);
  if ((f.f & x) !== 0)
    throw f.v;
  return f.v;
}
function J(f) {
  if (f.f |= p, f.deps !== null)
    for (const r of f.deps)
      (r.reactions ??= []).push(f), (r.f & h) !== 0 && (r.f & p) === 0 && (H(
        /** @type {Derived} */
        r
      ), J(
        /** @type {Derived} */
        r
      ));
}
function Q(f) {
  if (f.v === K) return !0;
  if (f.deps === null) return !1;
  for (const r of f.deps)
    if (R.has(r) || (r.f & h) !== 0 && Q(
      /** @type {Derived} */
      r
    ))
      return !0;
  return !1;
}
function Mf(f) {
  var r = a;
  try {
    return a = !0, f();
  } finally {
    a = r;
  }
}
export {
  E as active_effect,
  n as active_reaction,
  v as current_sources,
  Gf as get,
  Vf as increment_write_version,
  b as is_destroying_effect,
  j as is_dirty,
  _ as new_deps,
  Yf as push_reaction_value,
  y as remove_reactions,
  Sf as set_active_effect,
  Lf as set_active_reaction,
  yf as set_is_destroying_effect,
  Bf as set_untracked_writes,
  Uf as set_update_version,
  o as skipped_deps,
  Mf as untrack,
  i as untracked_writes,
  a as untracking,
  zf as update_effect,
  Tf as update_reaction,
  I as update_version,
  Z as write_version
};
