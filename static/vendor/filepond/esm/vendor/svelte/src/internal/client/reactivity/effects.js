import { set_active_reaction as C, remove_reactions as I, active_reaction as a, untracking as P, active_effect as m, is_destroying_effect as N, update_effect as Y, get as B, set_is_destroying_effect as R } from "../runtime.js";
import { BRANCH_EFFECT as _, ROOT_EFFECT as E, HEAD_EFFECT as L, DESTROYING as g, DESTROYED as G, CLEAN as b, INERT as s, EFFECT as h, EFFECT_PRESERVED as p, BLOCK_EFFECT as w, EFFECT_TRANSPARENT as v, DERIVED as H, MANAGED_EFFECT as U, RENDER_EFFECT as F, DIRTY as A, CONNECTED as V, ASYNC as K, USER_EFFECT as M, STALE_REACTION as j, PAUSED as T } from "../constants.js";
import { invoke_error_boundary as q } from "../error-handling.js";
import { effect_orphan as z, effect_in_unowned_derived as J, effect_in_teardown as Q } from "../errors.js";
import { get_next_sibling as S } from "../dom/operations.js";
import { component_context as d } from "../context.js";
import { current_batch as W, collected_effects as D, Batch as x } from "./batch.js";
import { flatten as X } from "./async.js";
import { without_reactive_context as Z } from "../dom/elements/bindings/shared.js";
import { set_signal_status as y } from "./status.js";
function $(n) {
  m === null && (a === null && z(), J()), N && Q();
}
function nn(n, t) {
  var r = t.last;
  r === null ? t.last = t.first = n : (r.next = n, n.prev = r, t.last = n);
}
function o(n, t) {
  var r = m;
  r !== null && (r.f & s) !== 0 && (n |= s);
  var l = {
    ctx: d,
    deps: null,
    nodes: null,
    f: n | A | V,
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
  W?.register_created_effect(l);
  var e = l;
  if ((n & h) !== 0)
    D !== null ? D.push(l) : x.ensure().schedule(l);
  else if (t !== null) {
    try {
      Y(l);
    } catch (u) {
      throw f(l), u;
    }
    e.deps === null && e.teardown === null && e.nodes === null && e.first === e.last && // either `null`, or a singular child
    (e.f & p) === 0 && (e = e.first, (n & w) !== 0 && (n & v) !== 0 && e !== null && (e.f |= v));
  }
  if (e !== null && (e.parent = r, r !== null && nn(e, r), a !== null && (a.f & H) !== 0 && (n & E) === 0)) {
    var i = (
      /** @type {Derived} */
      a
    );
    (i.effects ??= []).push(e);
  }
  return l;
}
function hn() {
  return a !== null && !P;
}
function wn(n) {
  const t = o(F, null);
  return y(t, b), t.teardown = n, t;
}
function Fn(n) {
  $();
  var t = (
    /** @type {Effect} */
    m.f
  ), r = !a && (t & _) !== 0 && d !== null && !d.i;
  if (r) {
    var l = (
      /** @type {ComponentContext} */
      d
    );
    (l.e ??= []).push(n);
  } else
    return rn(n);
}
function rn(n) {
  return o(h | M, n);
}
function Tn(n) {
  x.ensure();
  const t = o(E | p, n);
  return (r = {}) => new Promise((l) => {
    r.outro ? un(t, () => {
      f(t), l(void 0);
    }) : (f(t), l(void 0));
  });
}
function xn(n) {
  return o(h, n);
}
function Cn(n) {
  return o(K | p, n);
}
function Rn(n, t = 0) {
  return o(F | t, n);
}
function gn(n, t = [], r = [], l = []) {
  X(l, t, r, (e) => {
    o(F, () => {
      n(...e.map(B));
    });
  });
}
function Dn(n, t = 0) {
  var r = o(w | t, n);
  return r;
}
function Nn(n, t = 0) {
  var r = o(U | t, n);
  return r;
}
function bn(n) {
  return o(_ | p, n);
}
function tn(n) {
  var t = n.teardown;
  if (t !== null) {
    const r = N, l = a;
    R(!0), C(null);
    try {
      t.call(null);
    } catch (e) {
      q(e, n.parent);
    } finally {
      R(r), C(l);
    }
  }
}
function en(n, t = !1) {
  var r = n.first;
  for (n.first = n.last = null; r !== null; ) {
    const e = r.ac;
    e !== null && Z(() => {
      e.abort(j);
    });
    var l = r.next;
    (r.f & E) !== 0 ? r.parent = null : f(r, t), r = l;
  }
}
function An(n) {
  for (var t = n.first; t !== null; ) {
    var r = t.next;
    (t.f & _) === 0 && f(t), t = r;
  }
}
function f(n, t = !0) {
  var r = !1;
  (t || (n.f & L) !== 0) && n.nodes !== null && n.nodes.end !== null && (ln(
    n.nodes.start,
    /** @type {TemplateNode} */
    n.nodes.end
  ), r = !0), n.f |= g, en(n, t && !r), I(n, 0);
  var l = n.nodes && n.nodes.t;
  if (l !== null)
    for (const i of l)
      i.stop();
  tn(n), n.f ^= g, n.f |= G;
  var e = n.parent;
  e !== null && e.first !== null && on(n), n.next = n.prev = n.teardown = n.ctx = n.deps = n.fn = n.nodes = n.ac = n.b = null;
}
function ln(n, t) {
  for (; n !== null; ) {
    var r = n === t ? null : S(n);
    n.remove(), n = r;
  }
}
function on(n) {
  var t = n.parent, r = n.prev, l = n.next;
  r !== null && (r.next = l), l !== null && (l.prev = r), t !== null && (t.first === n && (t.first = l), t.last === n && (t.last = r));
}
function un(n, t, r = !0) {
  var l = [];
  n.f |= T, O(n, l, !0);
  var e = () => {
    r && f(n), t && t();
  }, i = l.length;
  if (i > 0) {
    var u = () => --i || e();
    for (var c of l)
      c.out(u);
  } else
    e();
}
function O(n, t, r) {
  if ((n.f & s) === 0) {
    n.f ^= s;
    var l = n.nodes && n.nodes.t;
    if (l !== null)
      for (const c of l)
        (c.is_global || r) && t.push(c);
    for (var e = n.first; e !== null; ) {
      var i = e.next;
      if ((e.f & E) === 0) {
        var u = (e.f & v) !== 0 || // If this is a branch effect without a block effect parent,
        // it means the parent block effect was pruned. In that case,
        // transparency information was transferred to the branch effect.
        (e.f & _) !== 0 && (n.f & w) !== 0;
        O(e, t, u ? r : !1);
      }
      e = i;
    }
  }
}
function Sn(n) {
  n.f &= ~T, k(n, !0);
}
function k(n, t) {
  if ((n.f & T) === 0 && (n.f & s) !== 0) {
    n.f ^= s, (n.f & b) === 0 && (y(n, A), x.ensure().schedule(n));
    for (var r = n.first; r !== null; ) {
      var l = r.next, e = (r.f & v) !== 0 || (r.f & _) !== 0;
      k(r, e ? t : !1), r = l;
    }
    var i = n.nodes && n.nodes.t;
    if (i !== null)
      for (const u of i)
        (u.is_global || t) && u.in();
  }
}
function yn(n, t) {
  if (n.nodes)
    for (var r = n.nodes.start, l = n.nodes.end; r !== null; ) {
      var e = r === l ? null : S(r);
      t.append(r), r = e;
    }
}
export {
  Cn as async_effect,
  Dn as block,
  bn as branch,
  Tn as component_root,
  rn as create_user_effect,
  An as destroy_block_effect_children,
  f as destroy_effect,
  en as destroy_effect_children,
  xn as effect,
  hn as effect_tracking,
  tn as execute_effect_teardown,
  Nn as managed,
  yn as move_effect,
  un as pause_effect,
  ln as remove_effect_dom,
  Rn as render_effect,
  Sn as resume_effect,
  wn as teardown,
  gn as template_effect,
  on as unlink_effect,
  Fn as user_effect,
  $ as validate_effect
};
