import ff from "../../../../esm-env/false.js";
import { index_of as rf, includes as g } from "../shared/utils.js";
import { destroy_block_effect_children as tf, destroy_effect_children as ef, execute_effect_teardown as lf, effect_tracking as uf } from "./reactivity/effects.js";
import { CONNECTED as p, REACTION_RAN as B, ERROR_VALUE as x, DERIVED as h, DIRTY as w, MAYBE_DIRTY as L, DESTROYED as U, CLEAN as D, BLOCK_EFFECT as nf, MANAGED_EFFECT as sf, BRANCH_EFFECT as V, ROOT_EFFECT as z, REACTION_IS_UPDATING as N, STALE_REACTION as G } from "./constants.js";
import { old_values as R } from "./reactivity/sources.js";
import { update_derived as M, unfreeze_derived_effects as P, freeze_derived_effects as of, execute_derived as _f } from "./reactivity/deriveds.js";
import { tracing_mode_flag as af } from "../flags/index.js";
import { UNINITIALIZED as H } from "../../constants.js";
import { set_component_context as S, is_runes as pf, component_context as vf } from "./context.js";
import { batch_values as y, current_batch as cf, schedule_effect as mf, flushSync as hf } from "./reactivity/batch.js";
import { handle_error as Ef } from "./error-handling.js";
import { without_reactive_context as K } from "./dom/elements/bindings/shared.js";
import { set_signal_status as k, update_derived_status as Tf } from "./reactivity/status.js";
let C = !1, F = !1;
function Lf(f) {
  F = f;
}
let n = null, a = !1;
function Sf(f) {
  n = f;
}
let E = null;
function Yf(f) {
  E = f;
}
let v = null;
function Bf(f) {
  n !== null && ((n.f & N) !== 0 || (n.f & h) !== 0) && (v ??= /* @__PURE__ */ new Set()).add(f);
}
let o = null, _ = 0, i = null;
function Uf(f) {
  i = f;
}
let Z = 1, m = 0, I = m;
function Vf(f) {
  I = f;
}
function zf() {
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
    y === null && k(f, D);
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
function kf(f) {
  var r = o, l = _, t = i, u = n, e = v, s = vf, T = a, A = I, O = f.f;
  o = /** @type {null | Value[]} */
  null, _ = 0, i = null, n = (O & (V | z)) === 0 ? f : null, v = null, S(f.ctx), a = !1, I = ++m, f.ac !== null && (K(() => {
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
    return Y(f), Ef(c);
  } finally {
    f.f ^= N, o = r, _ = l, i = t, n = u, v = e, S(s), a = T, I = A;
  }
}
function Y(f) {
  var r = f.deps, l = cf?.is_fork;
  if (o !== null) {
    var t;
    if (l || b(f, _), r !== null && _ > 0)
      for (r.length = _ + o.length, t = 0; t < o.length; t++)
        r[_ + t] = o[t];
    else
      f.deps = r = o;
    if (uf() && (f.f & p) !== 0)
      for (t = _; t < r.length; t++)
        (r[t].reactions ??= []).push(f);
  } else !l && r !== null && _ < r.length && (b(f, _), r.length = _);
  return r;
}
function wf(f, r) {
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
  (o === null || !g.call(o, r))) {
    var e = (
      /** @type {Derived} */
      r
    );
    (e.f & p) !== 0 && (e.f ^= p), e.v !== H && Tf(e), e.ac !== null && K(() => {
      e.ac.abort(G), e.ac = null, k(e, w);
    }), of(e), b(e, 0);
  }
}
function b(f, r) {
  var l = f.deps;
  if (l !== null)
    for (var t = r; t < l.length; t++)
      wf(f, l[t]);
}
function Gf(f) {
  var r = f.f;
  if ((r & U) === 0) {
    k(f, D);
    var l = E, t = C;
    E = f, C = (r & (V | z)) === 0;
    try {
      (r & (nf | sf)) !== 0 ? tf(f) : ef(f), lf(f);
      var u = kf(f);
      f.teardown = typeof u == "function" ? u : null, f.wv = Z;
      var e;
      ff && af && (f.f & w) !== 0 && f.deps;
    } finally {
      C = t, E = l;
    }
  }
}
async function Mf() {
  await Promise.resolve(), hf();
}
function Pf(f) {
  var r = f.f, l = (r & h) !== 0;
  if (n !== null && !a) {
    var t = E !== null && (E.f & U) !== 0;
    if (!t && (v === null || !v.has(f))) {
      var u = n.deps;
      if ((n.f & N) !== 0)
        f.rv < m && (f.rv = m, o === null && u !== null && u[_] === f ? _++ : o === null ? o = [f] : o.push(f));
      else {
        n.deps ??= [], g.call(n.deps, f) || n.deps.push(f);
        var e = f.reactions;
        e === null ? f.reactions = [n] : g.call(e, n) || e.push(n);
      }
    }
  }
  if (F && R.has(f))
    return R.get(f);
  if (l) {
    var s = (
      /** @type {Derived} */
      f
    );
    if (F) {
      var T = s.v;
      return ((s.f & D) === 0 && s.reactions !== null || Q(s)) && (T = _f(s)), R.set(s, T), T;
    }
    var A = (s.f & p) === 0 && !a && n !== null && (C || (n.f & p) !== 0), O = (s.f & B) === 0;
    j(s) && (A && (s.f |= p), M(s)), A && !O && (P(s), J(s));
  }
  if (y?.has(f))
    return y.get(f);
  if ((f.f & x) !== 0)
    throw f.v;
  return f.v;
}
function J(f) {
  if (f.f |= p, f.deps !== null)
    for (const r of f.deps)
      (r.reactions ??= []).push(f), (r.f & h) !== 0 && (r.f & p) === 0 && (P(
        /** @type {Derived} */
        r
      ), J(
        /** @type {Derived} */
        r
      ));
}
function Q(f) {
  if (f.v === H) return !0;
  if (f.deps === null) return !1;
  for (const r of f.deps)
    if (R.has(r) || (r.f & h) !== 0 && Q(
      /** @type {Derived} */
      r
    ))
      return !0;
  return !1;
}
function Hf(f) {
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
  Pf as get,
  zf as increment_write_version,
  F as is_destroying_effect,
  j as is_dirty,
  o as new_deps,
  Bf as push_reaction_value,
  b as remove_reactions,
  Yf as set_active_effect,
  Sf as set_active_reaction,
  Lf as set_is_destroying_effect,
  Uf as set_untracked_writes,
  Vf as set_update_version,
  _ as skipped_deps,
  Mf as tick,
  Hf as untrack,
  i as untracked_writes,
  a as untracking,
  Gf as update_effect,
  kf as update_reaction,
  I as update_version,
  Z as write_version
};
