/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { withNodeTree as d } from "../../elements/common/nodeTree.js";
import { isRegExp as x, isFileEntry as o, isBlobOrFile as f, isDirectoryEntry as E, isString as s, isArray as h, isFunction as a } from "../../utils/test.js";
import { arrayWrap as m } from "../../utils/array.js";
import "../../elements/components/Button/index.js";
import "../../elements/components/ElementPane/index.js";
import "../../elements/FilePondEntryList/components/Entry/index.js";
import { hasOwnProp as g } from "../../utils/object.js";
import y from "../../elements/components/SpringElement/index-svelte.js";
import W from "../../elements/components/Button/index-svelte.js";
import S from "../../elements/components/ElementPane/index-svelte.js";
function u(t) {
  return !t || !t.extensionState ? [] : Object.values(t.extensionState);
}
function w(t, e) {
  return u(t).find((n) => g(n, e));
}
function A(t, e) {
  return u(t).find((n) => n.actions?.includes(e));
}
function j(t, e) {
  return !!w(t, e);
}
function B(t, e) {
  return !!A(t, e);
}
function P(t, e) {
  return !!u(t).find(
    (n) => n.status && e.includes(n.status.type)
  );
}
function v(t, e) {
  return !!u(t).find(
    (n) => n.status && e.includes(n.status.code)
  );
}
function I(t, e) {
  const r = u(t);
  for (const n of r)
    if (n.status && e.includes(n.status.code))
      return n.status;
}
function L(t) {
  return {
    ...t,
    component: y,
    props: ({ enableAnimations: e, springDefaults: r }) => ({
      springDefaults: r,
      enableAnimations: e,
      ...t.props
    })
  };
}
function q(t) {
  const { key: e, class: r, part: n } = t || {};
  return {
    key: e,
    component: S,
    props: ({ visualRect: i }) => ({
      part: n,
      class: r,
      width: i.width,
      height: i.height
    })
  };
}
function z(t, e) {
  let r;
  return a(e) ? r = (...n) => {
    const i = e(...n);
    return c(i);
  } : e.props ? a(e.props) ? r = (...n) => {
    const i = e.props(...n);
    return c(i);
  } : r = c(e.props) : r = c(e), {
    key: t,
    component: W,
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
function T(t) {
  if (x(t))
    return (n) => o(n) && f(n.file) && t.test(n.file.type);
  const r = (s(t) ? t.split(",") : h(t) ? t : []).map((n) => {
    if (/^(dir|directory|folder)$/.test(n))
      return (i) => E(i);
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
function G(t) {
  const e = a(t) ? t : T(t);
  return l(({ entry: r }) => e(r));
}
function J(t) {
  const e = m(t);
  return l(
    ({ entry: r }) => e.some((n) => B(r, n))
  );
}
function K(...t) {
  return l(
    ({ entry: e }) => !P(e, t)
  );
}
export {
  z as createButton,
  L as createDefaultSpringElement,
  T as createEntryMatcher,
  q as createSpringPane,
  c as getAsButtonProps,
  u as getEntryExtensionsAsArray,
  A as getExtensionByAction,
  w as getExtensionByProp,
  I as getExtensionStatusWithCode,
  B as hasExtensionWithAction,
  j as hasExtensionWithProp,
  v as hasExtensionWithStatusCode,
  P as hasExtensionWithStatusType,
  J as whenEntryHasAction,
  G as whenEntryIs,
  K as whenEntryNotHasStatus
};
