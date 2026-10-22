import { state as h, source as d, set as u, increment as a } from "../internal/client/reactivity/sources.js";
import { update_version as f, get as i } from "../internal/client/runtime.js";
class M extends Map {
  /** @type {Map<K, Source<number>>} */
  #e = /* @__PURE__ */ new Map();
  #s = h(0);
  #r = h(0);
  #u = f || -1;
  /**
   * @param {Iterable<readonly [K, V]> | null | undefined} [value]
   */
  constructor(e) {
    if (super(), e) {
      for (var [s, r] of e)
        super.set(s, r);
      this.#r.v = super.size;
    }
  }
  /**
   * If the source is being created inside the same reaction as the SvelteMap instance,
   * we use `state` so that it will not be a dependency of the reaction. Otherwise we
   * use `source` so it will be.
   *
   * @template T
   * @param {T} value
   * @returns {Source<T>}
   */
  #t(e) {
    return f === this.#u ? h(e) : d(e);
  }
  /** @param {K} key */
  has(e) {
    var s = this.#e, r = s.get(e);
    if (r === void 0)
      if (super.has(e))
        r = this.#t(0), s.set(e, r);
      else
        return i(this.#s), !1;
    return i(r), !0;
  }
  /**
   * @param {(value: V, key: K, map: Map<K, V>) => void} callbackfn
   * @param {any} [this_arg]
   */
  forEach(e, s) {
    this.#i(), super.forEach(e, s);
  }
  /** @param {K} key */
  get(e) {
    var s = this.#e, r = s.get(e);
    if (r === void 0)
      if (super.has(e))
        r = this.#t(0), s.set(e, r);
      else {
        i(this.#s);
        return;
      }
    return i(r), super.get(e);
  }
  /**
   * @param {K} key
   * @param {V} value
   * */
  getOrInsert(e, s) {
    return super.has(e) || this.set(e, s), /** @type {V} */
    this.get(e);
  }
  /**
   * @param {K} key
   * @param {(key: K) => V} callbackFn
   */
  getOrInsertComputed(e, s) {
    return super.has(e) || this.set(e, s(e)), /** @type {V} */
    this.get(e);
  }
  /**
   * @param {K} key
   * @param {V} value
   * */
  set(e, s) {
    var r = this.#e, t = r.get(e), p = super.get(e), v = super.set(e, s), n = this.#s;
    if (t === void 0)
      t = this.#t(0), r.set(e, t), u(this.#r, super.size), a(n);
    else if (p !== s) {
      a(t);
      var o = n.reactions === null ? null : new Set(n.reactions), l = o === null || !t.reactions?.every(
        (c) => (
          /** @type {NonNullable<typeof v_reactions>} */
          o.has(c)
        )
      );
      l && a(n);
    }
    return v;
  }
  /** @param {K} key */
  delete(e) {
    var s = this.#e, r = s.get(e), t = super.delete(e);
    return r !== void 0 && (s.delete(e), u(r, -1)), t && (u(this.#r, super.size), a(this.#s)), t;
  }
  clear() {
    if (super.size !== 0) {
      super.clear();
      var e = this.#e;
      u(this.#r, 0);
      for (var s of e.values())
        u(s, -1);
      a(this.#s), e.clear();
    }
  }
  #i() {
    i(this.#s);
    var e = this.#e;
    if (this.#r.v !== e.size) {
      for (var s of super.keys())
        if (!e.has(s)) {
          var r = this.#t(0);
          e.set(s, r);
        }
    }
    for ([, r] of this.#e)
      i(r);
  }
  keys() {
    return i(this.#s), super.keys();
  }
  values() {
    return this.#i(), super.values();
  }
  entries() {
    return this.#i(), super.entries();
  }
  [Symbol.iterator]() {
    return this.entries();
  }
  get size() {
    return i(this.#r), super.size;
  }
}
export {
  M as SvelteMap
};
