import { is_promise as k } from "../../../shared/utils.js";
import { block as w } from "../../reactivity/effects.js";
import { internal_set as m, source as p } from "../../reactivity/sources.js";
import { UNINITIALIZED as E } from "../../../../constants.js";
import { queue_micro_task as T } from "../task.js";
import { current_batch as b, Batch as d, is_flushing_sync as g, flushSync as x } from "../../reactivity/batch.js";
import { capture as A, unset_context as B } from "../../reactivity/async.js";
import { BranchManager as C } from "./branches.js";
const D = 0, y = 1, H = 2;
function j(I, N, h, t, s) {
  var f = (
    /** @type {V} */
    E
  ), o = p(f), i = p(f), a = new C(I);
  w(() => {
    var c = (
      /** @type {Batch} */
      b
    ), n = N(), l = !1;
    if (k(n)) {
      var _ = A(), v = !1;
      const r = (e) => {
        if (!l) {
          v = !0, _(!1), b === c && c.deactivate(), d.ensure();
          try {
            e();
          } finally {
            B(!1), g || x();
          }
        }
      };
      n.then(
        (e) => {
          r(() => {
            m(o, e), a.ensure(y, t && ((u) => t(u, o)));
          });
        },
        (e) => {
          r(() => {
            if (m(i, e), a.ensure(H, s && ((u) => s(u, i))), !s)
              throw i.v;
          });
        }
      ), T(() => {
        v || r(() => {
          a.ensure(D, h);
        });
      });
    } else
      m(o, n), a.ensure(y, t && ((r) => t(r, o)));
    return () => {
      l = !0;
    };
  });
}
export {
  j as await_block
};
