import { get as g, active_effect as E, update_version as O, set_active_reaction as j, set_update_version as D, active_reaction as L } from "./runtime.js";
import { object_prototype as S, array_prototype as A, get_descriptor as x, get_prototype_of as B, is_array as K } from "../shared/utils.js";
import { state as d, set as l, increment as P } from "./reactivity/sources.js";
import { STATE_SYMBOL as _, COMPONENT_SYMBOL as Y } from "./constants.js";
import { UNINITIALIZED as u } from "../../constants.js";
import { state_prototype_fixed as C, state_descriptors_fixed as U } from "./errors.js";
function b(f) {
  if (typeof f != "object" || f === null || _ in f || Y in f)
    return f;
  const y = B(f);
  if (y !== S && y !== A)
    return f;
  var s = /* @__PURE__ */ new Map(), w = K(f), m = d(0), N = O, v = (t) => {
    if (O === N)
      return t();
    var e = L, r = O;
    j(null), D(N);
    var n = t();
    return j(e), D(r), n;
  };
  return w && s.set("length", d(
    /** @type {any[]} */
    f.length
  )), new Proxy(
    /** @type {any} */
    f,
    {
      defineProperty(t, e, r) {
        (!("value" in r) || r.configurable === !1 || r.enumerable === !1 || r.writable === !1) && U();
        var n = s.get(e);
        return n === void 0 ? v(() => {
          var i = d(r.value);
          return s.set(e, i), i;
        }) : l(n, r.value, !0), !0;
      },
      deleteProperty(t, e) {
        var r = s.get(e);
        if (r === void 0) {
          if (e in t) {
            const n = v(() => d(u));
            s.set(e, n), P(m);
          }
        } else
          l(r, u), P(m);
        return !0;
      },
      get(t, e, r) {
        if (e === _)
          return f;
        var n = s.get(e), i = e in t;
        if (n === void 0 && (!i || x(t, e)?.writable) && (n = v(() => {
          var o = b(i ? t[e] : u), c = d(o);
          return c;
        }), s.set(e, n)), n !== void 0) {
          var a = g(n);
          return a === u ? void 0 : a;
        }
        return Reflect.get(t, e, r);
      },
      getOwnPropertyDescriptor(t, e) {
        this.has?.(t, e);
        var r = Reflect.getOwnPropertyDescriptor(t, e), n = s.get(e);
        if (n !== void 0) {
          var i = g(n);
          if (i === u)
            return;
          if (r && "value" in r)
            r.value = i;
          else
            return {
              enumerable: !0,
              configurable: !0,
              value: i,
              writable: !0
            };
        }
        return r;
      },
      has(t, e) {
        if (e === _)
          return !0;
        var r = s.get(e), n = r !== void 0 && r.v !== u || Reflect.has(t, e);
        if (r !== void 0 || E !== null && (!n || x(t, e)?.writable)) {
          r === void 0 && (r = v(() => {
            var a = n ? b(t[e]) : u, o = d(a);
            return o;
          }), s.set(e, r));
          var i = g(r);
          if (i === u)
            return !1;
        }
        return n;
      },
      set(t, e, r, n) {
        var i = s.get(e), a = e in t;
        if (w && e === "length")
          for (var o = r; o < /** @type {Source<number>} */
          i.v; o += 1) {
            var c = s.get(o + "");
            c !== void 0 ? l(c, u) : o in t && (c = v(() => d(u)), s.set(o + "", c));
          }
        if (i === void 0)
          (!a || x(t, e)?.writable) && (i = v(() => d(void 0)), l(i, b(r)), s.set(e, i));
        else {
          a = i.v !== u;
          var T = v(() => b(r));
          l(i, T);
        }
        var I = Reflect.getOwnPropertyDescriptor(t, e);
        if (I?.set && I.set.call(n, r), !a) {
          if (w && typeof e == "string") {
            var R = (
              /** @type {Source<number>} */
              s.get("length")
            ), h = Number(e);
            Number.isInteger(h) && h >= R.v && l(R, h + 1);
          }
          P(m);
        }
        return !0;
      },
      ownKeys(t) {
        g(m);
        var e = Reflect.ownKeys(t).filter((i) => {
          var a = s.get(i);
          return a === void 0 || a.v !== u;
        });
        for (var [r, n] of s)
          n.v !== u && !(r in t) && e.push(r);
        return e;
      },
      setPrototypeOf() {
        C();
      }
    }
  );
}
function M(f) {
  try {
    if (f !== null && typeof f == "object" && _ in f)
      return f[_];
  } catch {
  }
  return f;
}
function H(f, y) {
  return Object.is(M(f), M(y));
}
export {
  M as get_proxied_value,
  H as is,
  b as proxy
};
