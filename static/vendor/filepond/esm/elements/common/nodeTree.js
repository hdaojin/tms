/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { arrayRemoveFalsy as w, arrayInsertAtIndex as a, arrayWrap as m } from "../../utils/array.js";
import { isArray as c, isFunction as y } from "../../utils/test.js";
import { hasOwnProp as d } from "../../utils/object.js";
function t(n) {
  function u(r) {
    if (n) {
      const i = h(n, r, (f) => f);
      return t(i);
    }
    return t(void 0);
  }
  return {
    unwrap() {
      return n;
    },
    find: u,
    remove(r) {
      return n ? (h(n, r, (i, f) => {
        const o = f.indexOf(i);
        return f.splice(o, 1), i;
      }), t(n)) : t(void 0);
    },
    replace(r, ...i) {
      if (!n)
        return t(void 0);
      const f = i.map(e);
      return h(n, r, (o, p) => {
        const g = p.indexOf(o);
        return p.splice(g, 1, ...f), o;
      }), t(n);
    },
    update(r, i) {
      if (!n)
        return t(void 0);
      const f = u(r);
      return !f || !e(f) ? t(void 0) : (i(e(f)), f);
    },
    append(...r) {
      if (n) {
        let i = x(n);
        s(n, i, w(r));
      }
      return t(n);
    },
    prepend(...r) {
      return t(n ? s(n, 0, r) : void 0);
    },
    insert(r, ...i) {
      return t(n ? s(n, r, i) : void 0);
    }
  };
}
function e(n) {
  return y(n.unwrap) ? n.unwrap() : n;
}
function x(n) {
  if (c(n))
    return n.length;
  if (c(n.children))
    return n.children.length;
  if (n.if) {
    if (c(n.if.then))
      return n.if.then.length;
    if (c(n.if.then.children))
      return n.if.then.children.length;
  }
  return 0;
}
function s(n, u, r) {
  const i = r.map(e);
  return c(n) ? n.splice(u, 0, ...i) : l(n) ? Object.keys(n.if.then).length ? n.if.then.children ? c(n.if.then.children) && (n.if.then.children = a(
    // @ts-ignore
    n.if.then.children,
    u,
    ...i
  )) : n.if.then.children = i : n.if.then = i : n.children ? c(n.children) && (n.children = a(n.children, u, ...i)) : n.children = i, i;
}
function h(n, u, r) {
  if (!c(n))
    return n.key === u ? n : void 0;
  const i = [];
  for (const f of n) {
    if (f.key === u)
      return r(f, n);
    const o = T(f);
    o.length && i.push(o);
  }
  for (const f of i) {
    const o = h(f, u, r);
    if (o)
      return o;
  }
}
function T(n) {
  return l(n) ? w([n.if.then, n.elseif?.then, n.else]) : N(n) && n.item ? m(n.item) : n.children ? m(n.children) : [];
}
function l(n) {
  return !!(n && d(n, "if"));
}
function I(n) {
  return !!n;
}
function N(n) {
  return !!(n && d(n, "component"));
}
function b(n) {
  return !!(n && d(n, "tag"));
}
function F(n) {
  return !b(n) && !N(n) && !l(n);
}
export {
  N as isComponentNode,
  b as isElementNode,
  l as isSwitchNode,
  I as isTemplateNode,
  F as isTextNode,
  t as withNodeTree
};
