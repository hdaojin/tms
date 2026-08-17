/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { isObject as c, isArray as E } from "../../utils/test.js";
import { arrayInsertAtIndex as I } from "../../utils/array.js";
import { warn as w } from "../../common/console.js";
import { FileInputSource as V } from "../../extensions/file-input-source.js";
import { DataTransferLoader as _ } from "../../extensions/data-transfer-loader.js";
import { ValueCallbackStore as T } from "../../extensions/value-callback-store.js";
import { FileExtensionValidator as F } from "../../extensions/file-extension-validator.js";
import { FileMimeTypeValidator as L } from "../../extensions/file-mime-type-validator.js";
import { EntryListView as b } from "../../extensions/entry-list-view.js";
import { SourceListView as g } from "../../extensions/source-list-view.js";
import { SourceDescriptionView as v } from "../../extensions/source-description-view.js";
import { hasOwnProp as O } from "../../utils/object.js";
const p = [
  "source",
  "loader",
  "validator",
  "transform",
  "resource",
  "view",
  "store"
];
function h(t) {
  return p.includes(t);
}
const x = p.map((t) => ({ type: t })), [
  A,
  D,
  N,
  P,
  $,
  j,
  k
] = x;
function S(t) {
  return E(t) ? t[0] : c(t) && O(t, "insert") ? t.insert : t;
}
function a(t) {
  return S(t).name;
}
function u(t) {
  return S(t).type;
}
function B(t) {
  if (!c(t))
    return;
  const { insert: r, options: e, ...f } = t;
  return f;
}
function X(t = []) {
  let r = [
    V,
    A,
    _,
    D,
    F,
    L,
    N,
    P,
    $,
    j,
    b,
    g,
    v,
    k,
    T
  ];
  for (const e of t) {
    let f = a(e), m = u(e), i = r.findIndex((o) => a(o) === f);
    if (i > -1) {
      r[i] = e;
      continue;
    }
    let n, d = 1, s = B(e), l = !1;
    if (s ? (l = !!s.before, d = l ? 0 : 1, n = s.before || s.after) : n = m, i = s && !h(n) ? r.findIndex((o) => a(o) === n) : l ? r.findIndex((o) => u(o) === n) : r.findLastIndex(
      (o) => u(o) === n
    ), i === -1) {
      w(`No valid insertion index found for extension "${f}" with type "${m}"`);
      continue;
    }
    const y = c(e) ? (
      //  @ts-ignore
      [e.insert, e.options]
    ) : e;
    r = I(r, i + d, y);
  }
  return r.filter(
    (e) => !x.includes(
      e
    )
  );
}
export {
  X as createFilePondExtensionSet
};
