import { BOUNDARY_EFFECT as d, EFFECT_TRANSPARENT as y, EFFECT_PRESERVED as b } from "../../constants.js";
import { set_component_context as m, component_context as k } from "../../context.js";
import { handle_error as E, invoke_error_boundary as a } from "../../error-handling.js";
import { block as F, branch as n, pause_effect as l, move_effect as x, destroy_effect as u } from "../../reactivity/effects.js";
import { active_effect as _, set_active_effect as g, set_active_reaction as v, active_reaction as R, get as S } from "../../runtime.js";
import { svelte_boundary_reset_noop as T } from "../../warnings.js";
import { create_text as w } from "../operations.js";
import { queue_micro_task as c } from "../task.js";
import { svelte_boundary_reset_onerror as D } from "../../errors.js";
import { current_batch as h, Batch as A } from "../../reactivity/batch.js";
import { internal_set as B, source as C } from "../../reactivity/sources.js";
import { createSubscriber as N } from "../../../../reactivity/create-subscriber.js";
import { defer_effect as q } from "../../reactivity/utils.js";
var P = y | b;
function W(p, t, e, r) {
  new j(p, t, e, r);
}
class j {
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
  #r;
  /** @type {TemplateNode | null} */
  #k = null;
  /** @type {BoundaryProps} */
  #s;
  /** @type {((anchor: Node) => void)} */
  #a;
  /** @type {Effect} */
  #e;
  /** @type {Effect | null} */
  #n = null;
  /** @type {Effect | null} */
  #t = null;
  /** @type {Effect | null} */
  #i = null;
  /** @type {DocumentFragment | null} */
  #h = null;
  #_ = 0;
  #f = 0;
  #c = !1;
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
  #b = N(() => (this.#o = C(this.#_), () => {
    this.#o = null;
  }));
  /**
   * @param {TemplateNode} node
   * @param {BoundaryProps} props
   * @param {((anchor: Node) => void)} children
   * @param {((error: unknown) => unknown) | undefined} [transform_error]
   */
  constructor(t, e, r, i) {
    this.#r = t, this.#s = e, this.#a = (s) => {
      var o = (
        /** @type {Effect} */
        _
      );
      o.b = this, o.f |= d, r(s);
    }, this.parent = /** @type {Effect} */
    _.b, this.transform_error = i ?? this.parent?.transform_error ?? ((s) => s), this.#e = F(() => {
      this.#g();
    }, P);
  }
  #E() {
    try {
      this.#n = n(() => this.#a(this.#r));
    } catch (t) {
      this.error(t);
    }
  }
  /**
   * @param {unknown} error The deserialized error from the server's hydration comment
   */
  #F(t) {
    const e = this.#s.failed, { reset: r, invoke_onerror: i } = this.#m(t);
    c(i), e && (this.#i = n(() => {
      e(
        this.#r,
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
        T();
        return;
      }
      e = !0, r && D(), this.#i !== null && l(this.#i, () => {
        this.#i = null;
      }), this.#u(() => {
        this.#g();
      });
    };
    return { reset: i, invoke_onerror: () => {
      try {
        r = !0, this.#s.onerror?.(t, i), r = !1;
      } catch (o) {
        a(o, this.#e && this.#e.parent);
      }
    } };
  }
  #x() {
    const t = this.#s.pending;
    t && (this.is_pending = !0, this.#t = n(() => t(this.#r)), c(() => {
      var e = this.#h = document.createDocumentFragment(), r = w();
      e.append(r), this.#n = this.#u(() => n(() => this.#a(r))), this.#f === 0 && (this.#r.before(e), this.#h = null, l(
        /** @type {Effect} */
        this.#t,
        () => {
          this.#t = null;
        }
      ), this.#l(
        /** @type {Batch} */
        h
      ));
    }));
  }
  #g() {
    try {
      if (this.is_pending = this.has_pending_snippet(), this.#f = 0, this.#_ = 0, this.#n = n(() => {
        this.#a(this.#r);
      }), this.#f > 0) {
        var t = this.#h = document.createDocumentFragment();
        x(this.#n, t);
        const e = (
          /** @type {(anchor: Node) => void} */
          this.#s.pending
        );
        this.#t = n(() => e(this.#r));
      } else
        this.#l(
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
  #l(t) {
    this.is_pending = !1, t.transfer_effects(this.#p, this.#d);
  }
  /**
   * Defer an effect inside a pending boundary until the boundary resolves
   * @param {Effect} effect
   */
  defer_effect(t) {
    q(t, this.#p, this.#d);
  }
  /**
   * Returns `false` if the effect exists inside a boundary whose pending snippet is shown
   * @returns {boolean}
   */
  is_rendered() {
    return !this.is_pending && (!this.parent || this.parent.is_rendered());
  }
  has_pending_snippet() {
    return !!this.#s.pending;
  }
  /**
   * @template T
   * @param {() => T} fn
   */
  #u(t) {
    var e = _, r = R, i = k;
    g(this.#e), v(this.#e), m(this.#e.ctx);
    try {
      return A.ensure(), t();
    } catch (s) {
      return E(s), null;
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
    this.#f += t, this.#f === 0 && (this.#l(e), this.#t && l(this.#t, () => {
      this.#t = null;
    }), this.#h && (this.#r.before(this.#h), this.#h = null));
  }
  /**
   * Update the source that powers `$effect.pending()` inside this boundary,
   * and controls when the current `pending` snippet (if any) is removed.
   * Do not call from inside the class
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  update_pending_count(t, e) {
    this.#v(t, e), this.#_ += t, !(!this.#o || this.#c) && (this.#c = !0, c(() => {
      this.#c = !1, this.#o && B(this.#o, this.#_);
    }));
  }
  get_effect_pending() {
    return this.#b(), S(
      /** @type {Source<number>} */
      this.#o
    );
  }
  /** @param {unknown} error */
  error(t) {
    if (!this.#s.onerror && !this.#s.failed)
      throw t;
    h?.is_fork ? (this.#n && h.skip_effect(this.#n), this.#t && h.skip_effect(this.#t), this.#i && h.skip_effect(this.#i), h.oncommit(() => {
      this.#y(t);
    })) : this.#y(t);
  }
  /**
   * @param {unknown} error
   */
  #y(t) {
    this.#n && (u(this.#n), this.#n = null), this.#t && (u(this.#t), this.#t = null), this.#i && (u(this.#i), this.#i = null);
    let e = this.#s.failed;
    const r = (i) => {
      const { reset: s, invoke_onerror: o } = this.#m(i);
      o(), e && (this.#i = this.#u(() => {
        try {
          return n(() => {
            var f = (
              /** @type {Effect} */
              _
            );
            f.b = this, f.f |= d, e(
              this.#r,
              () => i,
              () => s
            );
          });
        } catch (f) {
          return a(
            f,
            /** @type {Effect} */
            this.#e.parent
          ), null;
        }
      }));
    };
    c(() => {
      var i;
      try {
        i = this.transform_error(t);
      } catch (s) {
        a(s, this.#e && this.#e.parent);
        return;
      }
      i !== null && typeof i == "object" && typeof /** @type {any} */
      i.then == "function" ? i.then(
        r,
        /** @param {unknown} e */
        (s) => a(s, this.#e && this.#e.parent)
      ) : r(i);
    });
  }
}
export {
  j as Boundary,
  W as boundary
};
