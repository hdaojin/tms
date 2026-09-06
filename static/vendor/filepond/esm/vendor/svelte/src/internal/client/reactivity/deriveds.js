import { DESTROYED as D, INERT as x, WAS_MARKED as N, STALE_REACTION as b, EFFECT_PRESERVED as S, DERIVED as O, DIRTY as j, REACTION_RAN as q, ERROR_VALUE as d, CLEAN as L } from "../constants.js";
import { increment_write_version as k, update_effect as C, set_active_effect as y, update_reaction as P, remove_reactions as V, active_effect as s, push_reaction_value as z, is_destroying_effect as A, active_reaction as F } from "../runtime.js";
import { without_reactive_context as U } from "../dom/elements/bindings/shared.js";
import { equals as Y, safe_equals as B } from "./equality.js";
import { async_derived_orphan as K } from "../errors.js";
import { derived_inert as M } from "../warnings.js";
import { destroy_effect as W, destroy_effect_children as Z, async_effect as G, teardown as H, effect_tracking as J } from "./effects.js";
import { source as Q, internal_set as R } from "./sources.js";
import { noop as X, deferred as $ } from "../../shared/utils.js";
import { component_context as ee } from "../context.js";
import { UNINITIALIZED as E } from "../../../constants.js";
import { current_batch as l, previous_batch as te, batch_values as g } from "./batch.js";
import { unset_context as w, increment_pending as ne } from "./async.js";
import { set_signal_status as re, update_derived_status as fe } from "./status.js";
// @__NO_SIDE_EFFECTS__
function I(t) {
  var e = O | j;
  return s !== null && (s.f |= S), {
    ctx: ee,
    deps: null,
    effects: null,
    equals: Y,
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
  c === null && K();
  var u = (
    /** @type {Promise<V>} */
    /** @type {unknown} */
    void 0
  ), i = Q(
    /** @type {V} */
    E
  ), T = !F, _ = /* @__PURE__ */ new Set();
  return G(() => {
    var o = (
      /** @type {Effect} */
      s
    ), n = $();
    u = n.promise;
    try {
      Promise.resolve(t()).then(n.resolve, (r) => {
        r !== b && n.reject(r);
      }).finally(w);
    } catch (r) {
      n.reject(r), w();
    }
    var a = (
      /** @type {Batch} */
      l
    );
    if (T) {
      if ((o.f & q) !== 0)
        var m = ne();
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
      m?.(), _.delete(n), v !== p && (a.activate(), v ? (i.f |= d, R(i, v)) : ((i.f & d) !== 0 && (i.f ^= d), R(i, r)), a.deactivate());
    };
    n.promise.then(h, (r) => h(null, r || "unknown"));
  }), H(() => {
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
  const e = /* @__PURE__ */ I(t);
  return z(e), e;
}
// @__NO_SIDE_EFFECTS__
function be(t) {
  const e = /* @__PURE__ */ I(t);
  return e.equals = B, e;
}
function oe(t) {
  var e = t.effects;
  if (e !== null) {
    t.effects = null;
    for (var f = 0; f < e.length; f += 1)
      W(
        /** @type {Effect} */
        e[f]
      );
  }
}
function ae(t) {
  var e, f = s, c = t.parent;
  if (!A && c !== null && t.v !== E && // if it was never evaluated before, it's guaranteed to fail downstream, so we try to execute instead
  (c.f & (D | x)) !== 0)
    return M(), t.v;
  y(c);
  try {
    t.f &= ~N, oe(t), e = P(t);
  } finally {
    y(f);
  }
  return e;
}
function Ae(t) {
  var e = ae(t);
  if (!t.equals(e) && (t.wv = k(), (!l?.is_fork || t.deps === null) && (l !== null ? (l.capture(t, e, !0), te?.capture(t, e, !0)) : t.v = e, t.deps === null))) {
    re(t, L);
    return;
  }
  A || (g !== null ? (J() || l?.is_fork) && g.set(t, e) : fe(t));
}
function Ie(t) {
  if (t.effects !== null)
    for (const e of t.effects)
      (e.teardown || e.ac) && (e.teardown?.(), e.ac !== null && U(() => {
        e.ac.abort(b), e.ac = null;
      }), e.fn !== null && (e.teardown = X), V(e, 0), Z(e));
}
function Te(t) {
  if (t.effects !== null)
    for (const e of t.effects)
      e.teardown && e.fn !== null && C(e);
}
export {
  p as OBSOLETE,
  ge as async_derived,
  I as derived,
  be as derived_safe_equal,
  oe as destroy_derived_effects,
  ae as execute_derived,
  Ie as freeze_derived_effects,
  Te as unfreeze_derived_effects,
  Ae as update_derived,
  we as user_derived
};
