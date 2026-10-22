import { ERROR_VALUE as E, REACTION_RAN as o, EFFECT as u, DESTROYED as r, BOUNDARY_EFFECT as a, DESTROYING as l } from "./constants.js";
import { active_reaction as R, active_effect as _ } from "./runtime.js";
function f(i) {
  var n = _;
  if (n === null)
    return R.f |= E, i;
  if ((n.f & o) === 0 && (n.f & u) === 0)
    throw i;
  h(i, n);
}
function h(i, n) {
  if (!(n !== null && (n.f & r) !== 0)) {
    for (; n !== null; ) {
      if ((n.f & a) !== 0 && (n.f & (r | l)) === 0) {
        if ((n.f & o) === 0)
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
  f as handle_error,
  h as invoke_error_boundary
};
