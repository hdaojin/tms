import { DIRTY as _, MAYBE_DIRTY as w, DESTROYED as k, ROOT_EFFECT as B, BRANCH_EFFECT as M, CLEAN as v, INERT as b, EFFECT as V, BLOCK_EFFECT as y, ERROR_VALUE as P, ASYNC as F, EAGER_EFFECT as Q, RENDER_EFFECT as W, MANAGED_EFFECT as X, REACTION_RAN as $, DERIVED as S } from "../constants.js";
import { deferred as ee, includes as te } from "../../shared/utils.js";
import { is_dirty as H, update_effect as O } from "../runtime.js";
import { effect_update_depth_exceeded as se } from "../errors.js";
import { queue_micro_task as q, flush_tasks as ie } from "../dom/task.js";
import re from "../../../../../esm-env/false.js";
import { invoke_error_boundary as ne } from "../error-handling.js";
import { old_values as x } from "./sources.js";
import { unlink_effect as le } from "./effects.js";
import { defer_effect as fe } from "./utils.js";
import { UNINITIALIZED as oe } from "../../../constants.js";
import { set_signal_status as p } from "./status.js";
import { OBSOLETE as he } from "./deriveds.js";
let A = null, g = null, u = null, G = null, T = null, L = null, C = !1, D = !1, N = null, I = null;
var U = 0;
let ue = 1;
class Y {
  id = ue++;
  /** True as soon as `#process` was called */
  #a = !1;
  linked = !0;
  /** @type {Batch | null} */
  #n = null;
  /** @type {Batch | null} */
  #f = null;
  /** @type {Map<Effect, ReturnType<typeof deferred<any>>>} */
  async_deriveds = /* @__PURE__ */ new Map();
  /**
   * The current values of any signals that are updated in this batch.
   * Tuple format: [value, is_derived] (note: is_derived is false for deriveds, too, if they were overridden via assignment)
   * They keys of this map are identical to `this.#previous`
   * @type {Map<Value, [any, boolean]>}
   */
  current = /* @__PURE__ */ new Map();
  /**
   * The values of any signals (sources and deriveds) that are updated in this batch _before_ those updates took place.
   * They keys of this map are identical to `this.#current`
   * @type {Map<Value, any>}
   */
  previous = /* @__PURE__ */ new Map();
  /**
   * When the batch is committed (and the DOM is updated), we need to remove old branches
   * and append new ones by calling the functions added inside (if/each/key/etc) blocks
   * @type {Set<(batch: Batch) => void>}
   */
  #c = /* @__PURE__ */ new Set();
  /**
   * If a fork is discarded, we need to destroy any effects that are no longer needed
   * @type {Set<(batch: Batch) => void>}
   */
  #d = /* @__PURE__ */ new Set();
  /**
   * The number of async effects that are currently in flight
   */
  #_ = 0;
  /**
   * Async effects that are currently in flight, _not_ inside a pending boundary
   * @type {Map<Effect, number>}
   */
  #i = /* @__PURE__ */ new Map();
  /**
   * A deferred that resolves when the batch is committed, used with `settled()`
   * TODO replace with Promise.withResolvers once supported widely enough
   * @type {{ promise: Promise<void>, resolve: (value?: any) => void, reject: (reason: unknown) => void } | null}
   */
  #p = null;
  /**
   * Effects that were scheduled in this batch but not yet 'resolved' into the
   * root effects that need to be flushed. Resolving — the upwards traversal that
   * marks the path to each effect on the shared effect tree (see #resolve) — is
   * deferred until the batch is processed, so that the markers are created and
   * consumed within a single traversal. Scheduling into other batches (which can
   * happen concurrently, e.g. while a batch is committed) can therefore never
   * observe (and be confused by) this batch's markers.
   * May contain duplicates — deduplication happens during resolving
   * @type {Effect[]}
   */
  #e = [];
  /**
   * Effects created while this batch was active.
   * @type {Effect[]}
   */
  #m = [];
  /**
   * Deferred effects (which run after async work has completed) that are DIRTY
   * @type {Set<Effect>}
   */
  #r = /* @__PURE__ */ new Set();
  /**
   * Deferred effects that are MAYBE_DIRTY
   * @type {Set<Effect>}
   */
  #t = /* @__PURE__ */ new Set();
  /**
   * A map of branches that still exist, but will be destroyed when this batch
   * is committed — we skip over these during `process`.
   * The value contains child effects that were dirty/maybe_dirty before being reset,
   * so they can be rescheduled if the branch survives.
   * @type {Map<Effect, { d: Effect[], m: Effect[] }>}
   */
  #s = /* @__PURE__ */ new Map();
  /**
   * Inverse of #skipped_branches which we need to tell prior batches to unskip them when committing
   * @type {Set<Effect>}
   */
  #v = /* @__PURE__ */ new Set();
  is_fork = !1;
  #o = !1;
  constructor() {
    g === null ? A = g = this : (g.#f = this, this.#n = g), g = this;
  }
  #g() {
    if (this.is_fork) return !0;
    for (const s of this.#i.keys()) {
      for (var e = s, t = !1; e.parent !== null; ) {
        if (this.#s.has(e)) {
          t = !0;
          break;
        }
        e = e.parent;
      }
      if (!t)
        return !0;
    }
    return !1;
  }
  /**
   * Add an effect to the #skipped_branches map and reset its children
   * @param {Effect} effect
   */
  skip_effect(e) {
    this.#s.has(e) || this.#s.set(e, { d: [], m: [] }), this.#v.delete(e);
  }
  /**
   * Remove an effect from the #skipped_branches map and reschedule
   * any tracked dirty/maybe_dirty child effects
   * @param {Effect} effect
   * @param {(e: Effect) => void} callback
   */
  unskip_effect(e, t = (s) => this.schedule(s)) {
    var s = this.#s.get(e);
    if (s) {
      this.#s.delete(e);
      for (var i of s.d)
        p(i, _), t(i);
      for (i of s.m)
        p(i, w), t(i);
    }
    this.#v.add(e);
  }
  /**
   * Convert the effects that were scheduled in this batch into the root effects
   * that need to be traversed, marking the path to each effect (by clearing the
   * `CLEAN` flag on ancestor branches) so that the traversal can find them.
   * This happens right before traversal rather than at scheduling time, so that
   * the markers left on the (shared) effect tree are created and consumed within
   * a single traversal — scheduling into other batches can never observe them
   * @returns {Effect[]}
   */
  #E() {
    var e = [];
    for (const l of this.#e)
      if (!((l.f & k) !== 0 || (l.f & (_ | w)) === 0)) {
        for (var t = l, s = !1; t.parent !== null; ) {
          t = t.parent;
          var i = t.f;
          if ((i & (B | M)) !== 0) {
            if ((i & v) === 0) {
              s = !0;
              break;
            }
            t.f ^= v;
          }
        }
        s || e.push(t);
      }
    return this.#e = [], e;
  }
  #h() {
    this.#a = !0;
    for (const r of this.#r)
      this.#t.delete(r), p(r, _), this.schedule(r);
    for (const r of this.#t)
      p(r, w), this.schedule(r);
    this.apply();
    for (var e = N = [], t = [], s = I = []; this.#e.length > 0; ) {
      U++ > 1e3 && (this.#u(), ae());
      for (const r of this.#E())
        try {
          this.#w(r, e, t);
        } catch (c) {
          throw J(r), this.#g() || this.discard(), c;
        }
    }
    if (u = null, s.length > 0) {
      var i = Y.ensure();
      for (const r of s)
        i.schedule(r);
    }
    if (N = null, I = null, this.#g()) {
      this.#l(t), this.#l(e);
      for (const [r, c] of this.#s)
        Z(r, c);
      s.length > 0 && /** @type {unknown} */
      u.#h();
      return;
    }
    const l = this.#y();
    if (l) {
      this.#l(t), this.#l(e), l.#k(this);
      return;
    }
    this.#r.clear(), this.#t.clear();
    for (const r of this.#c) r(this);
    this.#c.clear(), G = this, z(t), z(e), G = null, this.#p?.resolve();
    var o = (
      /** @type {Batch | null} */
      /** @type {unknown} */
      u
    );
    if (this.#_ === 0 && (this.#e.length === 0 || o !== null) && this.#u(), this.#e.length > 0)
      if (o !== null) {
        for (const r of this.#e)
          o.#e.push(r);
        this.#e = [];
      } else
        o = this;
    o !== null && (x.clear(), o.#h());
  }
  /**
   * Traverse the effect tree, executing effects or stashing
   * them for later execution as appropriate
   * @param {Effect} root
   * @param {Effect[]} effects
   * @param {Effect[]} render_effects
   */
  #w(e, t, s) {
    e.f ^= v;
    for (var i = e.first; i !== null; ) {
      var l = i.f, o = (l & (M | B)) !== 0, r = o && (l & v) !== 0, c = r || (l & b) !== 0 || this.#s.has(i);
      if (!c && i.fn !== null) {
        o ? i.f ^= v : (l & V) !== 0 ? t.push(i) : H(i) && ((l & y) !== 0 && this.#t.add(i), O(i));
        var E = i.first;
        if (E !== null) {
          i = E;
          continue;
        }
      }
      for (; i !== null; ) {
        var R = i.next;
        if (R !== null) {
          i = R;
          break;
        }
        i = i.parent;
      }
    }
  }
  #y() {
    for (var e = this.#n; e !== null; ) {
      if (!e.is_fork) {
        for (const [t, [, s]] of this.current)
          if (e.current.has(t) && !s)
            return e;
      }
      e = e.#n;
    }
    return null;
  }
  /**
   * @param {Batch} batch
   */
  #k(e) {
    for (const [s, i] of e.current)
      !this.previous.has(s) && e.previous.has(s) && this.previous.set(s, e.previous.get(s)), this.current.set(s, i);
    for (const [s, i] of e.async_deriveds) {
      const l = this.async_deriveds.get(s);
      l && i.promise.then(l.resolve).catch(l.reject);
    }
    e.async_deriveds.clear(), this.transfer_effects(e.#r, e.#t);
    const t = (s) => {
      var i = s.reactions;
      if (i !== null && !((s.f & S) !== 0 && (s.f & (_ | w)) === 0))
        for (const r of i) {
          var l = r.f;
          if ((l & S) !== 0)
            t(
              /** @type {Derived} */
              r
            );
          else {
            var o = (
              /** @type {Effect} */
              r
            );
            l & (F | y) && !this.async_deriveds.has(o) && (this.#t.delete(o), p(o, _), this.schedule(o));
          }
        }
    };
    for (const s of this.current.keys())
      t(s);
    this.oncommit(() => e.discard()), e.#u(), u = this, this.#h();
  }
  /**
   * @param {Effect[]} effects
   */
  #l(e) {
    for (var t = 0; t < e.length; t += 1)
      fe(e[t], this.#r, this.#t);
  }
  /**
   * Associate a change to a given source with the current
   * batch, noting its previous and current values
   * @param {Value} source
   * @param {any} value
   * @param {boolean} [is_derived]
   */
  capture(e, t, s = !1) {
    e.v !== oe && !this.previous.has(e) && this.previous.set(e, e.v), (e.f & P) === 0 && (this.current.set(e, [t, s]), T?.set(e, t)), this.is_fork || (e.v = t);
  }
  activate() {
    u = this;
  }
  deactivate() {
    u = null, T = null;
  }
  flush() {
    try {
      D = !0, u = this, this.#h();
    } finally {
      U = 0, L = null, N = null, I = null, D = !1, u = null, T = null, x.clear();
    }
  }
  discard() {
    for (const e of this.#d) e(this);
    this.#d.clear();
    for (const e of this.async_deriveds.values())
      e.reject(he);
    this.#u(), this.#p?.resolve();
  }
  /**
   * @param {Effect} effect
   */
  register_created_effect(e) {
    this.#m.push(e);
  }
  #b() {
    for (let f = A; f !== null; f = f.#f) {
      var e = f.id < this.id, t = [];
      for (const [h, [a, d]] of this.current) {
        if (f.current.has(h)) {
          var s = (
            /** @type {[any, boolean]} */
            f.current.get(h)[0]
          );
          if (e && a !== s)
            f.current.set(h, [a, d]);
          else
            continue;
        }
        t.push(h);
      }
      if (e)
        for (const [h, a] of this.async_deriveds) {
          const d = f.async_deriveds.get(h);
          d && a.promise.then(d.resolve).catch(d.reject);
        }
      var i = [...f.current.keys()].filter(
        (h) => !/** @type {[any, boolean]} */
        f.current.get(h)[1]
      );
      if (!(!f.#a || i.length === 0)) {
        var l = i.filter((h) => !this.current.has(h));
        if (l.length === 0)
          e && f.discard();
        else if (t.length > 0) {
          if (e)
            for (const h of this.#v)
              f.unskip_effect(h, (a) => {
                (a.f & (y | F)) !== 0 ? f.schedule(a) : f.#l([a]);
              });
          f.activate();
          var o = /* @__PURE__ */ new Set(), r = /* @__PURE__ */ new Map();
          for (var c of t)
            K(c, l, o, r);
          r = /* @__PURE__ */ new Map();
          var E = [...f.current].filter(([h, a]) => {
            const d = this.current.get(h);
            return d ? d[0] !== a[0] || d[1] !== a[1] : !0;
          }).map(([h]) => h);
          if (E.length > 0)
            for (const h of this.#m)
              (h.f & (k | b | Q)) === 0 && j(h, E, r) && ((h.f & (F | y)) !== 0 ? (p(h, _), f.schedule(h)) : f.#r.add(h));
          if (f.#e.length > 0 && !f.#o) {
            f.apply();
            for (var R of f.#E())
              f.#w(R, [], []);
          }
          f.deactivate();
        }
      }
    }
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  increment(e, t) {
    if (this.#_ += 1, e) {
      let s = this.#i.get(t) ?? 0;
      this.#i.set(t, s + 1);
    }
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  decrement(e, t) {
    if (this.#_ -= 1, e) {
      let s = this.#i.get(t) ?? 0;
      s === 1 ? this.#i.delete(t) : this.#i.set(t, s - 1);
    }
    this.#o || (this.#o = !0, q(() => {
      this.#o = !1, this.linked && this.flush();
    }));
  }
  /**
   * @param {Set<Effect>} dirty_effects
   * @param {Set<Effect>} maybe_dirty_effects
   */
  transfer_effects(e, t) {
    for (const s of e)
      this.#r.add(s);
    for (const s of t)
      this.#t.add(s);
    e.clear(), t.clear();
  }
  /** @param {(batch: Batch) => void} fn */
  oncommit(e) {
    this.#c.add(e);
  }
  /** @param {(batch: Batch) => void} fn */
  ondiscard(e) {
    this.#d.add(e);
  }
  settled() {
    return (this.#p ??= ee()).promise;
  }
  static ensure() {
    if (u === null) {
      const e = u = new Y();
      !D && !C && q(() => {
        e.#a || e.flush();
      });
    }
    return u;
  }
  apply() {
    {
      T = null;
      return;
    }
  }
  /**
   *
   * @param {Effect} effect
   */
  schedule(e) {
    if (L = e, e.b?.is_pending && (e.f & (V | W | X)) !== 0 && (e.f & $) === 0) {
      e.b.defer_effect(e);
      return;
    }
    this.#e.push(e);
  }
  #u() {
    if (this.linked) {
      var e = this.#n, t = this.#f;
      e === null ? A = t : e.#f = t, t === null ? g = e : t.#n = e, this.linked = !1;
    }
  }
}
function Fe(n) {
  var e = C;
  C = !0;
  try {
    for (var t; ; ) {
      if (ie(), u === null)
        return (
          /** @type {T} */
          t
        );
      u.flush();
    }
  } finally {
    C = e;
  }
}
function ae() {
  try {
    se();
  } catch (n) {
    ne(n, L);
  }
}
let m = null;
function z(n) {
  var e = n.length;
  if (e !== 0) {
    for (var t = 0; t < e; ) {
      var s = n[t++];
      if ((s.f & (k | b)) === 0 && H(s) && (m = /* @__PURE__ */ new Set(), O(s), s.deps === null && s.first === null && s.nodes === null && s.teardown === null && s.ac === null && le(s), m?.size > 0)) {
        x.clear();
        for (const i of m) {
          if ((i.f & (k | b)) !== 0) continue;
          const l = [i];
          let o = i.parent;
          for (; o !== null; )
            m.has(o) && (m.delete(o), l.push(o)), o = o.parent;
          for (let r = l.length - 1; r >= 0; r--) {
            const c = l[r];
            (c.f & (k | b)) === 0 && O(c);
          }
        }
        m.clear();
      }
    }
    m = null;
  }
}
function K(n, e, t, s) {
  if (!t.has(n) && (t.add(n), n.reactions !== null))
    for (const i of n.reactions) {
      const l = i.f;
      (l & S) !== 0 ? K(
        /** @type {Derived} */
        i,
        e,
        t,
        s
      ) : (l & (F | y)) !== 0 && (l & _) === 0 && j(i, e, s) && (p(i, _), ce(
        /** @type {Effect} */
        i
      ));
    }
}
function j(n, e, t) {
  const s = t.get(n);
  if (s !== void 0) return s;
  if (n.deps !== null)
    for (const i of n.deps) {
      if (te.call(e, i))
        return !0;
      if ((i.f & S) !== 0 && j(
        /** @type {Derived} */
        i,
        e,
        t
      ))
        return t.set(
          /** @type {Derived} */
          i,
          !0
        ), !0;
    }
  return t.set(n, !1), !1;
}
function ce(n) {
  u.schedule(n);
}
function Z(n, e) {
  if (!((n.f & M) !== 0 && (n.f & v) !== 0)) {
    (n.f & _) !== 0 ? e.d.push(n) : (n.f & w) !== 0 && e.m.push(n), p(n, v);
    for (var t = n.first; t !== null; )
      Z(t, e), t = t.next;
  }
}
function J(n) {
  p(n, v);
  for (var e = n.first; e !== null; )
    J(e), e = e.next;
}
export {
  Y as Batch,
  T as batch_values,
  N as collected_effects,
  u as current_batch,
  m as eager_block_effects,
  Fe as flushSync,
  C as is_flushing_sync,
  I as legacy_updates,
  G as previous_batch,
  ce as schedule_effect
};
