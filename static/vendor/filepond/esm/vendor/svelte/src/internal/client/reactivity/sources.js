import { increment_write_version as Y, is_dirty as b, update_effect as x, push_reaction_value as I, active_reaction as o, untracking as N, current_sources as w, is_destroying_effect as O, active_effect as c, untracked_writes as C, set_untracked_writes as S } from "../runtime.js";
import { equals as L, safe_equals as M } from "./equality.js";
import { DERIVED as E, DIRTY as v, EAGER_EFFECT as p, MAYBE_DIRTY as T, CLEAN as R, BLOCK_EFFECT as y, ASYNC as z, BRANCH_EFFECT as G, ROOT_EFFECT as H } from "../constants.js";
import { state_unsafe_mutation as K } from "../errors.js";
import { proxy as V } from "../proxy.js";
import { Batch as j, batch_values as A, schedule_effect as J, legacy_updates as P, eager_block_effects as F } from "./batch.js";
import { is_runes as Q } from "../context.js";
import { execute_derived as U } from "./deriveds.js";
import { update_derived_status as W, set_signal_status as g } from "./status.js";
let a = /* @__PURE__ */ new Set();
const m = /* @__PURE__ */ new Map();
let q = !1;
function B(e, t) {
  var f = {
    f: 0,
    // TODO ideally we could skip this altogether, but it causes type errors
    v: e,
    reactions: null,
    equals: L,
    rv: 0,
    wv: 0
  };
  return f;
}
// @__NO_SIDE_EFFECTS__
function ue(e, t) {
  const f = B(e);
  return I(f), f;
}
// @__NO_SIDE_EFFECTS__
function _e(e, t = !1, f = !0) {
  const n = B(e);
  return t || (n.equals = M), n;
}
function X(e, t, f = !1) {
  o !== null && // since we are untracking the function inside `$inspect.with` we need to add this check
  // to ensure we error if state is set inside an inspect effect
  (!N || (o.f & p) !== 0) && Q() && (o.f & (E | y | z | p)) !== 0 && (w === null || !w.has(e)) && K();
  let n = f ? V(t) : t;
  return Z(e, n, P);
}
var r = null, d = 0;
function Z(e, t, f = null) {
  if (!e.equals(t)) {
    O ? m.set(e, t) : m.has(e) || m.set(e, e.v);
    var n = j.ensure();
    if (n.capture(e, t), (e.f & E) !== 0) {
      const i = (
        /** @type {Derived} */
        e
      );
      (e.f & v) !== 0 && U(i), A === null && W(i);
    }
    e.wv = Y(), r = null, d = 0, D(e, v, f), r = null, c !== null && (c.f & R) !== 0 && (c.f & (G | H)) === 0 && (C === null ? S([e]) : C.push(e)), !n.is_fork && a.size > 0 && !q && $();
  }
  return t;
}
function $() {
  q = !1;
  for (const e of a) {
    (e.f & R) !== 0 && g(e, T);
    let t;
    try {
      t = b(e);
    } catch {
      t = !0;
    }
    t && x(e);
  }
  a.clear();
}
function oe(e) {
  X(e, e.v + 1);
}
function D(e, t, f) {
  var n = e.reactions;
  if (n !== null) {
    var i = n.length;
    if (d += i, d > 1e5 && r === null && (r = /* @__PURE__ */ new Set()), r !== null) {
      if (r.has(e)) return;
      r.add(e);
    }
    for (var u = 0; u < i; u++) {
      var l = n[u], s = l.f, h = (s & v) === 0;
      if (h && g(l, t), (s & p) !== 0)
        a.add(
          /** @type {Effect} */
          l
        );
      else if ((s & E) !== 0) {
        var k = (
          /** @type {Derived} */
          l
        );
        A?.delete(k), D(k, T, f);
      } else if (h) {
        var _ = (
          /** @type {Effect} */
          l
        );
        (s & y) !== 0 && F !== null && F.add(_), f !== null ? f.push(_) : J(_);
      }
    }
  }
}
export {
  a as eager_effects,
  $ as flush_eager_effects,
  oe as increment,
  Z as internal_set,
  _e as mutable_source,
  m as old_values,
  X as set,
  B as source,
  ue as state
};
