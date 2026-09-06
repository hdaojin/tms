import { PROPS_IS_UPDATED as E, PROPS_IS_BINDABLE as R, PROPS_IS_IMMUTABLE as L, PROPS_IS_LAZY_INITIAL as T } from "../../../constants.js";
import { get_descriptor as h, is_function as a } from "../../shared/utils.js";
import { set as B } from "./sources.js";
import { derived as O, derived_safe_equal as Y } from "./deriveds.js";
import { get as _, is_destroying_effect as j, active_effect as K, untrack as M } from "../runtime.js";
import { props_invalid_value as N } from "../errors.js";
import { DESTROYED as U, STATE_SYMBOL as I, LEGACY_PROPS as x } from "../constants.js";
import { proxy as $ } from "../proxy.js";
import { capture_store_binding as q } from "./store.js";
const z = {
  get(r, e) {
    if (!r.exclude.has(e))
      return r.props[e];
  },
  set(r, e) {
    return !1;
  },
  getOwnPropertyDescriptor(r, e) {
    if (!r.exclude.has(e) && e in r.props)
      return {
        enumerable: !0,
        configurable: !0,
        value: r.props[e]
      };
  },
  has(r, e) {
    return r.exclude.has(e) ? !1 : e in r.props;
  },
  ownKeys(r) {
    return Reflect.ownKeys(r.props).filter((e) => !r.exclude.has(e));
  }
};
// @__NO_SIDE_EFFECTS__
function k(r, e, t) {
  return new Proxy({ props: r, exclude: e }, z);
}
const C = {
  get(r, e) {
    let t = r.props.length;
    for (; t--; ) {
      let n = r.props[t];
      if (a(n) && (n = n()), typeof n == "object" && n !== null && e in n) return n[e];
    }
  },
  set(r, e, t) {
    let n = r.props.length;
    for (; n--; ) {
      let i = r.props[n];
      a(i) && (i = i());
      const u = h(i, e);
      if (u && u.set)
        return u.set(t), !0;
    }
    return !1;
  },
  getOwnPropertyDescriptor(r, e) {
    let t = r.props.length;
    for (; t--; ) {
      let n = r.props[t];
      if (a(n) && (n = n()), typeof n == "object" && n !== null && e in n) {
        const i = h(n, e);
        return i && !i.configurable && (i.configurable = !0), i;
      }
    }
  },
  has(r, e) {
    if (e === I || e === x) return !1;
    for (let t of r.props)
      if (a(t) && (t = t()), t != null && e in t) return !0;
    return !1;
  },
  ownKeys(r) {
    const e = [];
    for (let t of r.props)
      if (a(t) && (t = t()), !!t) {
        for (const n in t)
          e.includes(n) || e.push(n);
        for (const n of Object.getOwnPropertySymbols(t))
          e.includes(n) || e.push(n);
      }
    return e;
  }
};
function rr(...r) {
  return new Proxy({ props: r }, C);
}
function er(r, e, t, n) {
  var i = !0, u = (t & R) !== 0, P = (t & T) !== 0, c = (
    /** @type {V} */
    n
  ), v = !0, g = (
    /** @type {Derived<V> | undefined} */
    void 0
  ), S = () => P && i ? (g ??= O(
    /** @type {() => V} */
    n
  ), _(g)) : (v && (v = !1, c = P ? M(
    /** @type {() => V} */
    n
  ) : (
    /** @type {V} */
    n
  )), c);
  let o;
  if (u) {
    var y = I in r || x in r;
    o = h(r, e)?.set ?? (y && e in r ? (f) => r[e] = f : void 0);
  }
  var s, b = !1;
  u ? [s, b] = q(() => (
    /** @type {V} */
    r[e]
  )) : s = /** @type {V} */
  r[e], s === void 0 && n !== void 0 && (s = S(), o && (N(), o(s)));
  var l;
  if (l = () => {
    var f = (
      /** @type {V} */
      r[e]
    );
    return f === void 0 ? S() : (v = !0, f);
  }, (t & E) === 0)
    return l;
  if (o) {
    var A = r.$$legacy;
    return (
      /** @type {() => V} */
      (function(f, d) {
        return arguments.length > 0 ? ((!d || A || b) && o(d ? l() : f), f) : l();
      })
    );
  }
  var m = !1, p = ((t & L) !== 0 ? O : Y)(() => (m = !1, l()));
  u && _(p);
  var D = (
    /** @type {Effect} */
    K
  );
  return (
    /** @type {() => V} */
    (function(f, d) {
      if (arguments.length > 0) {
        const w = d ? _(p) : u ? $(f) : f;
        return B(p, w), m = !0, c !== void 0 && (c = w), f;
      }
      return j && m || (D.f & U) !== 0 ? p.v : _(p);
    })
  );
}
export {
  er as prop,
  k as rest_props,
  rr as spread_props
};
