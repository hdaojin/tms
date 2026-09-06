import { set_active_reaction as x, remove_reactions as I, active_reaction as a, untracking as k, active_effect as m, is_destroying_effect as N, update_effect as Y, get as B, set_is_destroying_effect as C } from "../runtime.js";
import { BRANCH_EFFECT as _, ROOT_EFFECT as E, HEAD_EFFECT as L, DESTROYING as R, DESTROYED as P, CLEAN as D, INERT as s, EFFECT as h, EFFECT_PRESERVED as p, BLOCK_EFFECT as w, EFFECT_TRANSPARENT as v, DERIVED as G, RENDER_EFFECT as F, MANAGED_EFFECT as H, DIRTY as b, CONNECTED as V, ASYNC as K, USER_EFFECT as M, STALE_REACTION as U } from "../constants.js";
import { effect_orphan as j, effect_in_unowned_derived as q, effect_in_teardown as z } from "../errors.js";
import { get_next_sibling as A } from "../dom/operations.js";
import { component_context as d } from "../context.js";
import { current_batch as J, collected_effects as g, Batch as T } from "./batch.js";
import { flatten as Q } from "./async.js";
import { without_reactive_context as W } from "../dom/elements/bindings/shared.js";
import { set_signal_status as O } from "./status.js";
function X(n) {
  m === null && (a === null && j(), q()), N && z();
}
function Z(n, t) {
  var r = t.last;
  r === null ? t.last = t.first = n : (r.next = n, n.prev = r, t.last = n);
}
function u(n, t) {
  var r = m;
  r !== null && (r.f & s) !== 0 && (n |= s);
  var e = {
    ctx: d,
    deps: null,
    nodes: null,
    f: n | b | V,
    first: null,
    fn: t,
    last: null,
    next: null,
    parent: r,
    b: r && r.b,
    prev: null,
    teardown: null,
    wv: 0,
    ac: null
  };
  J?.register_created_effect(e);
  var l = e;
  if ((n & h) !== 0)
    g !== null ? g.push(e) : T.ensure().schedule(e);
  else if (t !== null) {
    try {
      Y(e);
    } catch (o) {
      throw f(e), o;
    }
    l.deps === null && l.teardown === null && l.nodes === null && l.first === l.last && // either `null`, or a singular child
    (l.f & p) === 0 && (l = l.first, (n & w) !== 0 && (n & v) !== 0 && l !== null && (l.f |= v));
  }
  if (l !== null && (l.parent = r, r !== null && Z(l, r), a !== null && (a.f & G) !== 0 && (n & E) === 0)) {
    var i = (
      /** @type {Derived} */
      a
    );
    (i.effects ??= []).push(l);
  }
  return e;
}
function En() {
  return a !== null && !k;
}
function pn(n) {
  const t = u(F, null);
  return O(t, D), t.teardown = n, t;
}
function mn(n) {
  X();
  var t = (
    /** @type {Effect} */
    m.f
  ), r = !a && (t & _) !== 0 && d !== null && !d.i;
  if (r) {
    var e = (
      /** @type {ComponentContext} */
      d
    );
    (e.e ??= []).push(n);
  } else
    return $(n);
}
function $(n) {
  return u(h | M, n);
}
function hn(n) {
  T.ensure();
  const t = u(E | p, n);
  return (r = {}) => new Promise((e) => {
    r.outro ? ln(t, () => {
      f(t), e(void 0);
    }) : (f(t), e(void 0));
  });
}
function wn(n) {
  return u(h, n);
}
function Fn(n) {
  return u(K | p, n);
}
function Tn(n, t = 0) {
  return u(F | t, n);
}
function xn(n, t = [], r = [], e = []) {
  Q(e, t, r, (l) => {
    u(F, () => {
      n(...l.map(B));
    });
  });
}
function Cn(n, t = 0) {
  var r = u(w | t, n);
  return r;
}
function Rn(n, t = 0) {
  var r = u(H | t, n);
  return r;
}
function gn(n) {
  return u(_ | p, n);
}
function nn(n) {
  var t = n.teardown;
  if (t !== null) {
    const r = N, e = a;
    C(!0), x(null);
    try {
      t.call(null);
    } finally {
      C(r), x(e);
    }
  }
}
function rn(n, t = !1) {
  var r = n.first;
  for (n.first = n.last = null; r !== null; ) {
    const l = r.ac;
    l !== null && W(() => {
      l.abort(U);
    });
    var e = r.next;
    (r.f & E) !== 0 ? r.parent = null : f(r, t), r = e;
  }
}
function Nn(n) {
  for (var t = n.first; t !== null; ) {
    var r = t.next;
    (t.f & _) === 0 && f(t), t = r;
  }
}
function f(n, t = !0) {
  var r = !1;
  (t || (n.f & L) !== 0) && n.nodes !== null && n.nodes.end !== null && (tn(
    n.nodes.start,
    /** @type {TemplateNode} */
    n.nodes.end
  ), r = !0), n.f |= R, rn(n, t && !r), I(n, 0);
  var e = n.nodes && n.nodes.t;
  if (e !== null)
    for (const i of e)
      i.stop();
  nn(n), n.f ^= R, n.f |= P;
  var l = n.parent;
  l !== null && l.first !== null && en(n), n.next = n.prev = n.teardown = n.ctx = n.deps = n.fn = n.nodes = n.ac = n.b = null;
}
function tn(n, t) {
  for (; n !== null; ) {
    var r = n === t ? null : A(n);
    n.remove(), n = r;
  }
}
function en(n) {
  var t = n.parent, r = n.prev, e = n.next;
  r !== null && (r.next = e), e !== null && (e.prev = r), t !== null && (t.first === n && (t.first = e), t.last === n && (t.last = r));
}
function ln(n, t, r = !0) {
  var e = [];
  S(n, e, !0);
  var l = () => {
    r && f(n), t && t();
  }, i = e.length;
  if (i > 0) {
    var o = () => --i || l();
    for (var c of e)
      c.out(o);
  } else
    l();
}
function S(n, t, r) {
  if ((n.f & s) === 0) {
    n.f ^= s;
    var e = n.nodes && n.nodes.t;
    if (e !== null)
      for (const c of e)
        (c.is_global || r) && t.push(c);
    for (var l = n.first; l !== null; ) {
      var i = l.next;
      if ((l.f & E) === 0) {
        var o = (l.f & v) !== 0 || // If this is a branch effect without a block effect parent,
        // it means the parent block effect was pruned. In that case,
        // transparency information was transferred to the branch effect.
        (l.f & _) !== 0 && (n.f & w) !== 0;
        S(l, t, o ? r : !1);
      }
      l = i;
    }
  }
}
function Dn(n) {
  y(n, !0);
}
function y(n, t) {
  if ((n.f & s) !== 0) {
    n.f ^= s, (n.f & D) === 0 && (O(n, b), T.ensure().schedule(n));
    for (var r = n.first; r !== null; ) {
      var e = r.next, l = (r.f & v) !== 0 || (r.f & _) !== 0;
      y(r, l ? t : !1), r = e;
    }
    var i = n.nodes && n.nodes.t;
    if (i !== null)
      for (const o of i)
        (o.is_global || t) && o.in();
  }
}
function bn(n, t) {
  if (n.nodes)
    for (var r = n.nodes.start, e = n.nodes.end; r !== null; ) {
      var l = r === e ? null : A(r);
      t.append(r), r = l;
    }
}
export {
  Fn as async_effect,
  Cn as block,
  gn as branch,
  hn as component_root,
  $ as create_user_effect,
  Nn as destroy_block_effect_children,
  f as destroy_effect,
  rn as destroy_effect_children,
  wn as effect,
  En as effect_tracking,
  nn as execute_effect_teardown,
  Rn as managed,
  bn as move_effect,
  ln as pause_effect,
  tn as remove_effect_dom,
  Tn as render_effect,
  Dn as resume_effect,
  pn as teardown,
  xn as template_effect,
  en as unlink_effect,
  mn as user_effect,
  X as validate_effect
};
