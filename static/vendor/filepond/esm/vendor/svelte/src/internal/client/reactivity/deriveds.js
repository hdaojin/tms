import { DESTROYED as A, INERT as D, STALE_REACTION as b, EFFECT_PRESERVED as N, DERIVED as O, DIRTY as S, REACTION_RAN as j, ERROR_VALUE as d, CLEAN as q } from "../constants.js";
import { increment_write_version as L, update_effect as k, set_active_effect as y, update_reaction as C, remove_reactions as P, active_effect as s, push_reaction_value as V, is_destroying_effect as I, active_reaction as z } from "../runtime.js";
import { without_reactive_context as F } from "../dom/elements/bindings/shared.js";
import { equals as U, safe_equals as Y } from "./equality.js";
import { async_derived_orphan as B } from "../errors.js";
import { derived_inert as Z } from "../warnings.js";
import { destroy_effect as G, destroy_effect_children as H, async_effect as J, teardown as K, effect_tracking as M } from "./effects.js";
import { source as Q, internal_set as g } from "./sources.js";
import { noop as W, deferred as X } from "../../shared/utils.js";
import { component_context as $ } from "../context.js";
import { UNINITIALIZED as E } from "../../../constants.js";
import { current_batch as l, previous_batch as ee, batch_values as w } from "./batch.js";
import { unset_context as R, increment_pending as te } from "./async.js";
import { set_signal_status as ne, update_derived_status as re } from "./status.js";
// @__NO_SIDE_EFFECTS__
function T(t) {
  var e = O | S;
  return s !== null && (s.f |= N), {
    ctx: $,
    deps: null,
    effects: null,
    equals: U,
    f: e,
    fn: t,
    reactions: null,
    rv: 0,
    v: (
      /** @type {V} */
      E
    ),
    wv: 0,
    parent: s,
    ac: null
  };
}
const p = /* @__PURE__ */ Symbol("obsolete");
// @__NO_SIDE_EFFECTS__
function ge(t, e, f) {
  let c = (
    /** @type {Effect | null} */
    s
  );
  c === null && B();
  var u = (
    /** @type {Promise<V>} */
    /** @type {unknown} */
    void 0
  ), i = Q(
    /** @type {V} */
    E
  ), x = !z, _ = /* @__PURE__ */ new Set();
  return J(() => {
    var o = (
      /** @type {Effect} */
      s
    ), n = X();
    u = n.promise;
    try {
      Promise.resolve(t()).then(n.resolve, (r) => {
        r !== b && n.reject(r);
      }).finally(R);
    } catch (r) {
      n.reject(r), R();
    }
    var a = (
      /** @type {Batch} */
      l
    );
    if (x) {
      if ((o.f & j) !== 0)
        var m = te();
      if (
        // boundary can be null if the async derived is inside an $effect.root not connected to the component render tree
        c.b?.is_rendered()
      )
        a.async_deriveds.get(o)?.reject(p);
      else
        for (const r of _.values())
          r.reject(p);
      _.add(n), a.async_deriveds.set(o, n);
    }
    const h = (r, v = void 0) => {
      m?.(), _.delete(n), v !== p && (a.activate(), v ? (i.f |= d, g(i, v)) : ((i.f & d) !== 0 && (i.f ^= d), g(i, r)), a.deactivate());
    };
    n.promise.then(h, (r) => h(null, r || "unknown"));
  }), K(() => {
    for (const o of _)
      o.reject(p);
  }), new Promise((o) => {
    function n(a) {
      function m() {
        a === u ? o(i) : n(u);
      }
      a.then(m, m);
    }
    n(u);
  });
}
// @__NO_SIDE_EFFECTS__
function we(t) {
  const e = /* @__PURE__ */ T(t);
  return V(e), e;
}
// @__NO_SIDE_EFFECTS__
function Re(t) {
  const e = /* @__PURE__ */ T(t);
  return e.equals = Y, e;
}
function fe(t) {
  var e = t.effects;
  if (e !== null) {
    t.effects = null;
    for (var f = 0; f < e.length; f += 1)
      G(
        /** @type {Effect} */
        e[f]
      );
  }
}
function oe(t) {
  var e, f = s, c = t.parent;
  if (!I && c !== null && t.v !== E && // if it was never evaluated before, it's guaranteed to fail downstream, so we try to execute instead
  (c.f & (A | D)) !== 0)
    return Z(), t.v;
  y(c);
  try {
    fe(t), e = C(t);
  } finally {
    y(f);
  }
  return e;
}
function be(t) {
  var e = oe(t);
  if (!t.equals(e) && (t.wv = L(), (!l?.is_fork || t.deps === null) && (l !== null ? (l.capture(t, e, !0), ee?.capture(t, e, !0)) : t.v = e, t.deps === null))) {
    ne(t, q);
    return;
  }
  I || (w !== null ? (M() || l?.is_fork) && w.set(t, e) : re(t));
}
function Ie(t) {
  if (t.effects !== null)
    for (const e of t.effects)
      (e.teardown || e.ac) && (e.teardown?.(), e.ac !== null && F(() => {
        e.ac.abort(b), e.ac = null;
      }), e.fn !== null && (e.teardown = W), P(e, 0), H(e));
}
function Te(t) {
  if (t.effects !== null)
    for (const e of t.effects)
      e.teardown && e.fn !== null && k(e);
}
export {
  p as OBSOLETE,
  ge as async_derived,
  T as derived,
  Re as derived_safe_equal,
  fe as destroy_derived_effects,
  oe as execute_derived,
  Ie as freeze_derived_effects,
  Te as unfreeze_derived_effects,
  be as update_derived,
  we as user_derived
};
