import { DIRTY as d, MAYBE_DIRTY as s, CLEAN as a } from "../constants.js";
import { set_signal_status as m } from "./status.js";
function n(i, o, r) {
  (i.f & d) !== 0 ? o.add(i) : (i.f & s) !== 0 && r.add(i), m(i, a);
}
export {
  n as defer_effect
};
