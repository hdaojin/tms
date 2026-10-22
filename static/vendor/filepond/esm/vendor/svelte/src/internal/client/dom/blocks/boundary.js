import { BOUNDARY_EFFECT as d, EFFECT_TRANSPARENT as y, EFFECT_PRESERVED as b } from "../../constants.js";
import { set_component_context as m, component_context as k } from "../../context.js";
import { invoke_error_boundary as f } from "../../error-handling.js";
import { block as E, branch as o, pause_effect as l, move_effect as F, destroy_effect as u } from "../../reactivity/effects.js";
import { active_effect as c, set_active_effect as g, set_active_reaction as v, active_reaction as x, get as R } from "../../runtime.js";
import { svelte_boundary_reset_noop as S } from "../../warnings.js";
import { create_text as T } from "../operations.js";
import { queue_micro_task as _ } from "../task.js";
import { svelte_boundary_reset_onerror as w } from "../../errors.js";
import { current_batch as h, Batch as D } from "../../reactivity/batch.js";
import { internal_set as A, source as B } from "../../reactivity/sources.js";
import { createSubscriber as C } from "../../../../reactivity/create-subscriber.js";
import { defer_effect as N } from "../../reactivity/utils.js";
var q = y | b;
function Q(p, t, e, r) {
  new P(p, t, e, r);
}
class P {
  /** @type {Boundary | null} */
  parent;
  is_pending = !1;
  /**
   * API-level transformError transform function. Transforms errors before they reach the `failed` snippet.
   * Inherited from parent boundary, or defaults to identity.
   * @type {(error: unknown) => unknown}
   */
  transform_error;
  /** @type {TemplateNode} */
  #s;
  /** @type {TemplateNode | null} */
  #k = null;
  /** @type {BoundaryProps} */
  #n;
  /** @type {((anchor: Node) => void)} */
  #a;
  /** @type {Effect} */
  #t;
  /** @type {Effect | null} */
  #i = null;
  /** @type {Effect | null} */
  #e = null;
  /** @type {Effect | null} */
  #r = null;
  /** @type {DocumentFragment | null} */
  #h = null;
  #c = 0;
  #f = 0;
  #l = !1;
  /** @type {Set<Effect>} */
  #p = /* @__PURE__ */ new Set();
  /** @type {Set<Effect>} */
  #d = /* @__PURE__ */ new Set();
  /**
   * A source containing the number of pending async deriveds/expressions.
   * Only created if `$effect.pending()` is used inside the boundary,
   * otherwise updating the source results in needless `Batch.ensure()`
   * calls followed by no-op flushes
   * @type {Source<number> | null}
   */
  #o = null;
  #b = C(() => (this.#o = B(this.#c), () => {
    this.#o = null;
  }));
  /**
   * @param {TemplateNode} node
   * @param {BoundaryProps} props
   * @param {((anchor: Node) => void)} children
   * @param {((error: unknown) => unknown) | undefined} [transform_error]
   */
  constructor(t, e, r, i) {
    this.#s = t, this.#n = e, this.#a = (s) => {
      var n = (
        /** @type {Effect} */
        c
      );
      n.b = this, n.f |= d, r(s);
    }, this.parent = /** @type {Effect} */
    c.b, this.transform_error = i ?? this.parent?.transform_error ?? ((s) => s), this.#t = E(() => {
      this.#g();
    }, q);
  }
  #E() {
    try {
      this.#i = o(() => this.#a(this.#s));
    } catch (t) {
      this.error(t);
    }
  }
  /**
   * @param {unknown} error The deserialized error from the server's hydration comment
   */
  #F(t) {
    const e = this.#n.failed, { reset: r, invoke_onerror: i } = this.#m(t);
    _(i), e && (this.#r = o(() => {
      e(
        this.#s,
        () => t,
        () => r
      );
    }));
  }
  /**
   * Creates the `reset` function for a failed boundary, along with a function
   * that invokes `onerror` with it (if provided)
   * @param {unknown} error
   * @returns {{ reset: () => void, invoke_onerror: () => void }}
   */
  #m(t) {
    var e = !1, r = !1;
    const i = () => {
      if (e) {
        S();
        return;
      }
      e = !0, r && w(), this.#r !== null && l(this.#r, () => {
        this.#r = null;
      }), this.#u(() => {
        this.#g();
      });
    };
    return { reset: i, invoke_onerror: () => {
      try {
        r = !0, this.#n.onerror?.(t, i), r = !1;
      } catch (n) {
        f(n, this.#t && this.#t.parent);
      }
    } };
  }
  #x() {
    const t = this.#n.pending;
    t && (this.is_pending = !0, this.#e = o(() => t(this.#s)), _(() => {
      var e = this.#h = document.createDocumentFragment(), r = T(), i = !1;
      if (e.append(r), this.#i = this.#u(() => {
        try {
          return o(() => this.#a(r));
        } catch (s) {
          try {
            this.error(s), i = !0;
          } catch (n) {
            f(n, this.#t.parent);
          }
          return null;
        }
      }), this.#i === null) {
        this.#h = null, i && this.#_(
          /** @type {Batch} */
          h
        );
        return;
      }
      this.#f === 0 && (this.#s.before(e), this.#h = null, l(
        /** @type {Effect} */
        this.#e,
        () => {
          this.#e = null;
        }
      ), this.#_(
        /** @type {Batch} */
        h
      ));
    }));
  }
  #g() {
    try {
      if (this.is_pending = this.has_pending_snippet(), this.#f = 0, this.#c = 0, this.#i = o(() => {
        this.#a(this.#s);
      }), this.#f > 0) {
        var t = this.#h = document.createDocumentFragment();
        F(this.#i, t);
        const e = (
          /** @type {(anchor: Node) => void} */
          this.#n.pending
        );
        this.#e = o(() => e(this.#s));
      } else
        this.#_(
          /** @type {Batch} */
          h
        );
    } catch (e) {
      this.error(e);
    }
  }
  /**
   * @param {Batch} batch
   */
  #_(t) {
    this.is_pending = !1, t.transfer_effects(this.#p, this.#d);
  }
  /**
   * Defer an effect inside a pending boundary until the boundary resolves
   * @param {Effect} effect
   */
  defer_effect(t) {
    N(t, this.#p, this.#d);
  }
  /**
   * Returns `false` if the effect exists inside a boundary whose pending snippet is shown
   * @returns {boolean}
   */
  is_rendered() {
    return !this.is_pending && (!this.parent || this.parent.is_rendered());
  }
  has_pending_snippet() {
    return !!this.#n.pending;
  }
  /**
   * @template T
   * @param {() => T} fn
   */
  #u(t) {
    var e = c, r = x, i = k;
    g(this.#t), v(this.#t), m(this.#t.ctx);
    try {
      return D.ensure(), t();
    } finally {
      g(e), v(r), m(i);
    }
  }
  /**
   * Updates the pending count associated with the currently visible pending snippet,
   * if any, such that we can replace the snippet with content once work is done
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  #v(t, e) {
    if (!this.has_pending_snippet()) {
      this.parent && this.parent.#v(t, e);
      return;
    }
    this.#f += t, this.#f === 0 && (this.#_(e), this.#e && l(this.#e, () => {
      this.#e = null;
    }), this.#h && (this.#s.before(this.#h), this.#h = null));
  }
  /**
   * Update the source that powers `$effect.pending()` inside this boundary,
   * and controls when the current `pending` snippet (if any) is removed.
   * Do not call from inside the class
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  update_pending_count(t, e) {
    this.#v(t, e), this.#c += t, !(!this.#o || this.#l) && (this.#l = !0, _(() => {
      this.#l = !1, this.#o && A(this.#o, this.#c);
    }));
  }
  get_effect_pending() {
    return this.#b(), R(
      /** @type {Source<number>} */
      this.#o
    );
  }
  /** @param {unknown} error */
  error(t) {
    if (!this.#n.onerror && !this.#n.failed)
      throw t;
    h?.is_fork ? (this.#i && h.skip_effect(this.#i), this.#e && h.skip_effect(this.#e), this.#r && h.skip_effect(this.#r), h.oncommit(() => {
      this.#y(t);
    })) : this.#y(t);
  }
  /**
   * @param {unknown} error
   */
  #y(t) {
    this.#i && (u(this.#i), this.#i = null), this.#e && (u(this.#e), this.#e = null), this.#r && (u(this.#r), this.#r = null);
    let e = this.#n.failed;
    const r = (i) => {
      const { reset: s, invoke_onerror: n } = this.#m(i);
      n(), e && (this.#r = this.#u(() => {
        try {
          return o(() => {
            var a = (
              /** @type {Effect} */
              c
            );
            a.b = this, a.f |= d, e(
              this.#s,
              () => i,
              () => s
            );
          });
        } catch (a) {
          return f(
            a,
            /** @type {Effect} */
            this.#t.parent
          ), null;
        }
      }));
    };
    _(() => {
      var i;
      try {
        i = this.transform_error(t);
      } catch (s) {
        f(s, this.#t && this.#t.parent);
        return;
      }
      i !== null && typeof i == "object" && typeof /** @type {any} */
      i.then == "function" ? i.then(
        r,
        /** @param {unknown} e */
        (s) => f(s, this.#t && this.#t.parent)
      ) : r(i);
    });
  }
}
export {
  P as Boundary,
  Q as boundary
};
