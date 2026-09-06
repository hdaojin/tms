import { DESTROYED as g } from "../constants.js";
import { set_component_context as b, component_context as D } from "../context.js";
import { invoke_error_boundary as s } from "../error-handling.js";
import { active_effect as f, set_active_effect as x, set_active_reaction as y, active_reaction as E } from "../runtime.js";
import { current_batch as u } from "./batch.js";
import { derived as P, async_derived as O } from "./deriveds.js";
function A(e, i, t, n) {
  const p = P;
  var o = e.filter((r) => !r.settled), l = i.map(p);
  if (t.length === 0 && o.length === 0) {
    n(l);
    return;
  }
  var a = (
    /** @type {Effect} */
    f
  ), v = R(), c = o.length === 1 ? o[0].promise : o.length > 1 ? Promise.all(o.map((r) => r.promise)) : null;
  function m(r) {
    if ((a.f & g) === 0) {
      v();
      try {
        n([...l, ...r]);
      } catch (k) {
        s(k, a);
      }
      h();
    }
  }
  var _ = S();
  if (t.length === 0) {
    c.then(() => m([])).finally(_);
    return;
  }
  function d() {
    Promise.all(t.map((r) => O(r))).then(m).catch((r) => s(r, a)).finally(_);
  }
  c ? c.then(() => {
    v(), d(), h();
  }) : d();
}
function R() {
  var e = (
    /** @type {Effect} */
    f
  ), i = E, t = D, n = (
    /** @type {Batch} */
    u
  );
  return function(o = !0) {
    x(e), y(i), b(t), o && (e.f & g) === 0 && (n?.activate(), n?.apply());
  };
}
function h(e = !0) {
  x(null), y(null), b(null), e && u?.deactivate();
}
function S() {
  var e = (
    /** @type {Effect} */
    f
  ), i = e.b, t = (
    /** @type {Batch} */
    u
  ), n = !!i?.is_rendered();
  return i?.update_pending_count(1, t), t.increment(n, e), () => {
    i?.update_pending_count(-1, t), t.decrement(n, e);
  };
}
export {
  R as capture,
  A as flatten,
  S as increment_pending,
  h as unset_context
};
