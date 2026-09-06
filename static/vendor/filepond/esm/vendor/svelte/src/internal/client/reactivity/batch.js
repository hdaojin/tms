import { DIRTY as v, MAYBE_DIRTY as F, CLEAN as m, INERT as k, EFFECT as j, BLOCK_EFFECT as w, ERROR_VALUE as P, ASYNC as C, DESTROYED as A, EAGER_EFFECT as Q, RENDER_EFFECT as W, MANAGED_EFFECT as X, REACTION_RAN as $, ROOT_EFFECT as B, BRANCH_EFFECT as I, DERIVED as y } from "../constants.js";
import { deferred as ee, includes as te } from "../../shared/utils.js";
import { is_dirty as H, update_effect as M, active_effect as re, active_reaction as V } from "../runtime.js";
import { effect_update_depth_exceeded as ie } from "../errors.js";
import { queue_micro_task as q } from "../dom/task.js";
import se from "../../../../../esm-env/false.js";
import { invoke_error_boundary as ne } from "../error-handling.js";
import { old_values as O } from "./sources.js";
import { unlink_effect as le } from "./effects.js";
import { defer_effect as fe } from "./utils.js";
import { UNINITIALIZED as oe } from "../../../constants.js";
import { set_signal_status as p } from "./status.js";
import { OBSOLETE as ue } from "./deriveds.js";
let S = null, E = null, a = null, G = null, R = null, x = null, D = !1, T = null, N = null;
var U = 0;
let he = 1;
class L {
  id = he++;
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
   * The root effects that need to be flushed
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
  #s = /* @__PURE__ */ new Set();
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
  #r = /* @__PURE__ */ new Map();
  /**
   * Inverse of #skipped_branches which we need to tell prior batches to unskip them when committing
   * @type {Set<Effect>}
   */
  #v = /* @__PURE__ */ new Set();
  is_fork = !1;
  #o = !1;
  constructor() {
    E === null ? S = E = this : (E.#f = this, this.#n = E), E = this;
  }
  #g() {
    if (this.is_fork) return !0;
    for (const r of this.#i.keys()) {
      for (var e = r, t = !1; e.parent !== null; ) {
        if (this.#r.has(e)) {
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
    this.#r.has(e) || this.#r.set(e, { d: [], m: [] }), this.#v.delete(e);
  }
  /**
   * Remove an effect from the #skipped_branches map and reschedule
   * any tracked dirty/maybe_dirty child effects
   * @param {Effect} effect
   * @param {(e: Effect) => void} callback
   */
  unskip_effect(e, t = (r) => this.schedule(r)) {
    var r = this.#r.get(e);
    if (r) {
      this.#r.delete(e);
      for (var i of r.d)
        p(i, v), t(i);
      for (i of r.m)
        p(i, F), t(i);
    }
    this.#v.add(e);
  }
  #u() {
    this.#a = !0, U++ > 1e3 && (this.#h(), ae());
    for (const f of this.#s)
      this.#t.delete(f), p(f, v), this.schedule(f);
    for (const f of this.#t)
      p(f, F), this.schedule(f);
    const e = this.#e;
    this.#e = [], this.apply();
    var t = T = [], r = [], i = N = [];
    for (const f of e)
      try {
        this.#E(f, t, r);
      } catch (c) {
        throw J(f), this.#g() || this.discard(), c;
      }
    if (a = null, i.length > 0) {
      var l = L.ensure();
      for (const f of i)
        l.schedule(f);
    }
    if (T = null, N = null, this.#g()) {
      this.#l(r), this.#l(t);
      for (const [f, c] of this.#r)
        Z(f, c);
      i.length > 0 && /** @type {unknown} */
      a.#u();
      return;
    }
    const h = this.#w();
    if (h) {
      this.#l(r), this.#l(t), h.#k(this);
      return;
    }
    this.#s.clear(), this.#t.clear();
    for (const f of this.#c) f(this);
    this.#c.clear(), G = this, z(r), z(t), G = null, this.#p?.resolve();
    var u = (
      /** @type {Batch | null} */
      /** @type {unknown} */
      a
    );
    if (this.#_ === 0 && (this.#e.length === 0 || u !== null) && this.#h(), this.#e.length > 0)
      if (u !== null) {
        const f = u;
        f.#e.push(...this.#e.filter((c) => !f.#e.includes(c)));
      } else
        u = this;
    u !== null && (O.clear(), u.#u());
  }
  /**
   * Traverse the effect tree, executing effects or stashing
   * them for later execution as appropriate
   * @param {Effect} root
   * @param {Effect[]} effects
   * @param {Effect[]} render_effects
   */
  #E(e, t, r) {
    e.f ^= m;
    for (var i = e.first; i !== null; ) {
      var l = i.f, h = (l & (I | B)) !== 0, u = h && (l & m) !== 0, f = u || (l & k) !== 0 || this.#r.has(i);
      if (!f && i.fn !== null) {
        h ? i.f ^= m : (l & j) !== 0 ? t.push(i) : H(i) && ((l & w) !== 0 && this.#t.add(i), M(i));
        var c = i.first;
        if (c !== null) {
          i = c;
          continue;
        }
      }
      for (; i !== null; ) {
        var b = i.next;
        if (b !== null) {
          i = b;
          break;
        }
        i = i.parent;
      }
    }
  }
  #w() {
    for (var e = this.#n; e !== null; ) {
      if (!e.is_fork) {
        for (const [t, [, r]] of this.current)
          if (e.current.has(t) && !r)
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
    for (const [r, i] of e.current)
      !this.previous.has(r) && e.previous.has(r) && this.previous.set(r, e.previous.get(r)), this.current.set(r, i);
    for (const [r, i] of e.async_deriveds) {
      const l = this.async_deriveds.get(r);
      l && i.promise.then(l.resolve).catch(l.reject);
    }
    e.async_deriveds.clear(), this.transfer_effects(e.#s, e.#t);
    const t = (r) => {
      var i = r.reactions;
      if (i !== null && !((r.f & y) !== 0 && (r.f & (v | F)) === 0))
        for (const u of i) {
          var l = u.f;
          if ((l & y) !== 0)
            t(
              /** @type {Derived} */
              u
            );
          else {
            var h = (
              /** @type {Effect} */
              u
            );
            l & (C | w) && !this.async_deriveds.has(h) && (this.#t.delete(h), p(h, v), this.schedule(h));
          }
        }
    };
    for (const r of this.current.keys())
      t(r);
    this.oncommit(() => e.discard()), e.#h(), a = this, this.#u();
  }
  /**
   * @param {Effect[]} effects
   */
  #l(e) {
    for (var t = 0; t < e.length; t += 1)
      fe(e[t], this.#s, this.#t);
  }
  /**
   * Associate a change to a given source with the current
   * batch, noting its previous and current values
   * @param {Value} source
   * @param {any} value
   * @param {boolean} [is_derived]
   */
  capture(e, t, r = !1) {
    e.v !== oe && !this.previous.has(e) && this.previous.set(e, e.v), (e.f & P) === 0 && (this.current.set(e, [t, r]), R?.set(e, t)), this.is_fork || (e.v = t);
  }
  activate() {
    a = this;
  }
  deactivate() {
    a = null, R = null;
  }
  flush() {
    try {
      D = !0, a = this, this.#u();
    } finally {
      U = 0, x = null, T = null, N = null, D = !1, a = null, R = null, O.clear();
    }
  }
  discard() {
    for (const e of this.#d) e(this);
    this.#d.clear();
    for (const e of this.async_deriveds.values())
      e.reject(ue);
    this.#h(), this.#p?.resolve();
  }
  /**
   * @param {Effect} effect
   */
  register_created_effect(e) {
    this.#m.push(e);
  }
  #y() {
    for (let n = S; n !== null; n = n.#f) {
      var e = n.id < this.id, t = [];
      for (const [o, [d, _]] of this.current) {
        if (n.current.has(o)) {
          var r = (
            /** @type {[any, boolean]} */
            n.current.get(o)[0]
          );
          if (e && d !== r)
            n.current.set(o, [d, _]);
          else
            continue;
        }
        t.push(o);
      }
      if (e)
        for (const [o, d] of this.async_deriveds) {
          const _ = n.async_deriveds.get(o);
          _ && d.promise.then(_.resolve).catch(_.reject);
        }
      var i = [...n.current.keys()].filter(
        (o) => !/** @type {[any, boolean]} */
        n.current.get(o)[1]
      );
      if (!(!n.#a || i.length === 0)) {
        var l = i.filter((o) => !this.current.has(o));
        if (l.length === 0)
          e && n.discard();
        else if (t.length > 0) {
          if (e)
            for (const o of this.#v)
              n.unskip_effect(o, (d) => {
                (d.f & (w | C)) !== 0 ? n.schedule(d) : n.#l([d]);
              });
          n.activate();
          var h = /* @__PURE__ */ new Set(), u = /* @__PURE__ */ new Map();
          for (var f of t)
            K(f, l, h, u);
          u = /* @__PURE__ */ new Map();
          var c = [...n.current].filter(([o, d]) => {
            const _ = this.current.get(o);
            return _ ? _[0] !== d[0] || _[1] !== d[1] : !0;
          }).map(([o]) => o);
          if (c.length > 0)
            for (const o of this.#m)
              (o.f & (A | k | Q)) === 0 && Y(o, c, u) && ((o.f & (C | w)) !== 0 ? (p(o, v), n.schedule(o)) : n.#s.add(o));
          if (n.#e.length > 0 && !n.#o) {
            n.apply();
            for (var b of n.#e)
              n.#E(b, [], []);
            n.#e = [];
          }
          n.deactivate();
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
      let r = this.#i.get(t) ?? 0;
      this.#i.set(t, r + 1);
    }
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  decrement(e, t) {
    if (this.#_ -= 1, e) {
      let r = this.#i.get(t) ?? 0;
      r === 1 ? this.#i.delete(t) : this.#i.set(t, r - 1);
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
    for (const r of e)
      this.#s.add(r);
    for (const r of t)
      this.#t.add(r);
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
    if (a === null) {
      const e = a = new L();
      D || q(() => {
        e.#a || e.flush();
      });
    }
    return a;
  }
  apply() {
    {
      R = null;
      return;
    }
  }
  /**
   *
   * @param {Effect} effect
   */
  schedule(e) {
    if (x = e, e.b?.is_pending && (e.f & (j | W | X)) !== 0 && (e.f & $) === 0) {
      e.b.defer_effect(e);
      return;
    }
    for (var t = e; t.parent !== null; ) {
      t = t.parent;
      var r = t.f;
      if (T !== null && t === re && (V === null || (V.f & y) === 0))
        return;
      if ((r & (B | I)) !== 0) {
        if ((r & m) === 0)
          return;
        t.f ^= m;
      }
    }
    this.#e.push(t);
  }
  #h() {
    if (this.linked) {
      var e = this.#n, t = this.#f;
      e === null ? S = t : e.#f = t, t === null ? E = e : t.#n = e, this.linked = !1;
    }
  }
}
function ae() {
  try {
    ie();
  } catch (s) {
    ne(s, x);
  }
}
let g = null;
function z(s) {
  var e = s.length;
  if (e !== 0) {
    for (var t = 0; t < e; ) {
      var r = s[t++];
      if ((r.f & (A | k)) === 0 && H(r) && (g = /* @__PURE__ */ new Set(), M(r), r.deps === null && r.first === null && r.nodes === null && r.teardown === null && r.ac === null && le(r), g?.size > 0)) {
        O.clear();
        for (const i of g) {
          if ((i.f & (A | k)) !== 0) continue;
          const l = [i];
          let h = i.parent;
          for (; h !== null; )
            g.has(h) && (g.delete(h), l.push(h)), h = h.parent;
          for (let u = l.length - 1; u >= 0; u--) {
            const f = l[u];
            (f.f & (A | k)) === 0 && M(f);
          }
        }
        g.clear();
      }
    }
    g = null;
  }
}
function K(s, e, t, r) {
  if (!t.has(s) && (t.add(s), s.reactions !== null))
    for (const i of s.reactions) {
      const l = i.f;
      (l & y) !== 0 ? K(
        /** @type {Derived} */
        i,
        e,
        t,
        r
      ) : (l & (C | w)) !== 0 && (l & v) === 0 && Y(i, e, r) && (p(i, v), ce(
        /** @type {Effect} */
        i
      ));
    }
}
function Y(s, e, t) {
  const r = t.get(s);
  if (r !== void 0) return r;
  if (s.deps !== null)
    for (const i of s.deps) {
      if (te.call(e, i))
        return !0;
      if ((i.f & y) !== 0 && Y(
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
  return t.set(s, !1), !1;
}
function ce(s) {
  a.schedule(s);
}
function Z(s, e) {
  if (!((s.f & I) !== 0 && (s.f & m) !== 0)) {
    (s.f & v) !== 0 ? e.d.push(s) : (s.f & F) !== 0 && e.m.push(s), p(s, m);
    for (var t = s.first; t !== null; )
      Z(t, e), t = t.next;
  }
}
function J(s) {
  p(s, m);
  for (var e = s.first; e !== null; )
    J(e), e = e.next;
}
export {
  L as Batch,
  R as batch_values,
  T as collected_effects,
  a as current_batch,
  g as eager_block_effects,
  N as legacy_updates,
  G as previous_batch,
  ce as schedule_effect
};
