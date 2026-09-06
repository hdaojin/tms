import { ERROR_VALUE as o, REACTION_RAN as r, EFFECT as u, DESTROYED as E, BOUNDARY_EFFECT as a } from "./constants.js";
import { active_reaction as l, active_effect as _ } from "./runtime.js";
function m(i) {
  var n = _;
  if (n === null)
    return l.f |= o, i;
  if ((n.f & r) === 0 && (n.f & u) === 0)
    throw i;
  R(i, n);
}
function R(i, n) {
  if (!(n !== null && (n.f & E) !== 0)) {
    for (; n !== null; ) {
      if ((n.f & a) !== 0) {
        if ((n.f & r) === 0)
          throw i;
        try {
          n.b.error(i);
          return;
        } catch (t) {
          i = t;
        }
      }
      n = n.parent;
    }
    throw i;
  }
}
export {
  m as handle_error,
  R as invoke_error_boundary
};
