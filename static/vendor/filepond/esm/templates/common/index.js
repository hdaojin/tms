/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { withNodeTree as d } from "../../elements/common/nodeTree.js";
import { isRegExp as E, isFileEntry as o, isBlobOrFile as f, isDirectoryEntry as x, isString as s, isArray as h, isFunction as a } from "../../utils/test.js";
import { arrayWrap as m } from "../../utils/array.js";
import "../../elements/components/Button/index.js";
import "../../elements/components/ElementPane/index.js";
import "../../elements/FilePondEntryList/components/Entry/index.js";
import { EMPTY_OBJECT as g, hasOwnProp as y } from "../../utils/object.js";
import W from "../../elements/components/SpringElement/index-svelte.js";
import S from "../../elements/components/Button/index-svelte.js";
import w from "../../elements/components/ElementPane/index-svelte.js";
function u(t) {
  return !t || !t.extensionState ? [] : Object.values(t.extensionState);
}
function A(t, e) {
  return u(t).find((n) => y(n, e));
}
function B(t, e) {
  return u(t).find((n) => n.actions?.includes(e));
}
function v(t, e) {
  return !!A(t, e);
}
function P(t, e) {
  return !!B(t, e);
}
function T(t, e) {
  return !!u(t).find(
    (n) => n.status && e.includes(n.status.type)
  );
}
function I(t, e) {
  return !!u(t).find(
    (n) => n.status && e.includes(n.status.code)
  );
}
function J(t, e) {
  const r = u(t);
  for (const n of r)
    if (n.status && e.includes(n.status.code))
      return n.status;
}
function L(t) {
  return {
    ...t,
    component: W,
    props: ({ reduceMotion: e, springOptions: r }) => ({
      springOptions: r,
      reduceMotion: e,
      ...t.props
    })
  };
}
function Y(t) {
  const { key: e, class: r, part: n } = t || {};
  return {
    key: e,
    component: w,
    data: ({ visualRect: i } = g) => ({ visualRect: i }),
    props: ({ visualRect: i }) => ({
      part: n,
      class: r,
      width: i.width,
      height: i.height
    })
  };
}
function _(t, e) {
  let r;
  return a(e) ? r = (...n) => {
    const i = e(...n);
    return c(i);
  } : e.props ? a(e.props) ? r = (...n) => {
    const i = e.props(...n);
    return c(i);
  } : r = c(e.props) : r = c(e), {
    key: t,
    component: S,
    props: r
  };
}
function c(t) {
  const { icon: e, label: r, title: n } = t;
  return {
    ...t,
    label: s(r) ? r : s(n) ? n : s(r) ? r : e,
    title: s(n) ? n : s(r) ? r : e,
    icon: e
  };
}
function l(t) {
  return d({
    if: {
      test: t,
      then: {
        // this will hold appended children
      }
    }
  });
}
function b(t) {
  if (E(t))
    return (n) => o(n) && f(n.file) && t.test(n.file.type);
  const r = (s(t) ? t.split(",") : h(t) ? t : []).map((n) => {
    if (/^(dir|directory|folder)$/.test(n))
      return (i) => x(i);
    if (n === "file")
      return (i) => o(i);
    if (n.startsWith("."))
      return (i) => o(i) && f(i.file) && i.file.name.endsWith(n);
    if (n.endsWith("*") || /^(audio|video|image|text)$/.test(n)) {
      const i = n.split("/")[0];
      return (p) => o(p) && f(p.file) && p.file.type.toLowerCase().startsWith(i);
    }
    return (i) => o(i) && f(i.file) && i.file.type === n;
  });
  return r.length === 1 ? r[0] : (n) => r.some((i) => i(n));
}
function q(t) {
  const e = a(t) ? t : b(t);
  return l(({ entry: r }) => e(r));
}
function z(t) {
  const e = m(t);
  return l(
    ({ entry: r }) => e.some((n) => P(r, n))
  );
}
function G(...t) {
  return l(
    ({ entry: e }) => !T(e, t)
  );
}
export {
  _ as createButton,
  L as createDefaultSpringElement,
  b as createEntryMatcher,
  Y as createSpringPane,
  c as getAsButtonProps,
  u as getEntryExtensionsAsArray,
  B as getExtensionByAction,
  A as getExtensionByProp,
  J as getExtensionStatusWithCode,
  P as hasExtensionWithAction,
  v as hasExtensionWithProp,
  I as hasExtensionWithStatusCode,
  T as hasExtensionWithStatusType,
  z as whenEntryHasAction,
  q as whenEntryIs,
  G as whenEntryNotHasStatus
};
