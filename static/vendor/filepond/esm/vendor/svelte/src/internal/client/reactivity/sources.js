import { increment_write_version as O, active_effect as s, is_dirty as g, update_effect as q, push_reaction_value as B, active_reaction as o, untracking as S, current_sources as h, is_destroying_effect as Y, untracked_writes as C, set_untracked_writes as b } from "../runtime.js";
import { equals as x, safe_equals as M } from "./equality.js";
import { DERIVED as E, DIRTY as m, EAGER_EFFECT as v, WAS_MARKED as T, CONNECTED as G, REACTION_IS_UPDATING as K, MAYBE_DIRTY as A, CLEAN as w, BLOCK_EFFECT as F, ASYNC as L, BRANCH_EFFECT as z, ROOT_EFFECT as H } from "../constants.js";
import { state_unsafe_mutation as P } from "../errors.js";
import { proxy as U } from "../proxy.js";
import { Batch as V, batch_values as R, schedule_effect as W, legacy_updates as j, eager_block_effects as k } from "./batch.js";
import { is_runes as J } from "../context.js";
import { execute_derived as Q } from "./deriveds.js";
import { update_derived_status as X, set_signal_status as D } from "./status.js";
let l = /* @__PURE__ */ new Set();
const c = /* @__PURE__ */ new Map();
let N = !1;
function I(e, t) {
  var f = {
    f: 0,
    // TODO ideally we could skip this altogether, but it causes type errors
    v: e,
    reactions: null,
    equals: x,
    rv: 0,
    wv: 0
  };
  return f;
}
// @__NO_SIDE_EFFECTS__
function ue(e, t) {
  const f = I(e);
  return B(f), f;
}
// @__NO_SIDE_EFFECTS__
function oe(e, t = !1, f = !0) {
  const r = I(e);
  return t || (r.equals = M), r;
}
function Z(e, t, f = !1) {
  o !== null && // since we are untracking the function inside `$inspect.with` we need to add this check
  // to ensure we error if state is set inside an inspect effect
  (!S || (o.f & v) !== 0) && J() && (o.f & (E | F | L | v)) !== 0 && (h === null || !h.has(e)) && P();
  let r = f ? U(t) : t;
  return $(e, r, j);
}
function $(e, t, f = null) {
  if (!e.equals(t)) {
    Y ? c.set(e, t) : c.has(e) || c.set(e, e.v);
    var r = V.ensure();
    if (r.capture(e, t), (e.f & E) !== 0) {
      const a = (
        /** @type {Derived} */
        e
      );
      (e.f & m) !== 0 && Q(a), R === null && X(a);
    }
    e.wv = O(), y(e, m, f), s !== null && (s.f & w) !== 0 && (s.f & (z | H)) === 0 && (C === null ? b([e]) : C.push(e)), !r.is_fork && l.size > 0 && !N && ee();
  }
  return t;
}
function ee() {
  N = !1;
  for (const e of l) {
    (e.f & w) !== 0 && D(e, A);
    let t;
    try {
      t = g(e);
    } catch {
      t = !0;
    }
    t && q(e);
  }
  l.clear();
}
function ce(e) {
  Z(e, e.v + 1);
}
function y(e, t, f) {
  var r = e.reactions;
  if (r !== null)
    for (var a = r.length, _ = 0; _ < a; _++) {
      var n = r[_], i = n.f, p = (i & m) === 0;
      if (p && D(n, t), (i & v) !== 0)
        l.add(
          /** @type {Effect} */
          n
        );
      else if ((i & E) !== 0) {
        var d = (
          /** @type {Derived} */
          n
        );
        R?.delete(d), (i & T) === 0 && (i & G && (s === null || (s.f & K) === 0) && (n.f |= T), y(d, A, f));
      } else if (p) {
        var u = (
          /** @type {Effect} */
          n
        );
        (i & F) !== 0 && k !== null && k.add(u), f !== null ? f.push(u) : W(u);
      }
    }
}
export {
  l as eager_effects,
  ee as flush_eager_effects,
  ce as increment,
  $ as internal_set,
  oe as mutable_source,
  c as old_values,
  Z as set,
  I as source,
  ue as state
};
