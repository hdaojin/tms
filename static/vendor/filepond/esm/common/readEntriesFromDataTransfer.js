/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { arrayRemoveFalsy as g, EMPTY_ARRAY as f } from "../utils/array.js";
import { noop as E } from "../utils/placeholder.js";
import { stringMatchesAny as l } from "../utils/string.js";
import { isFileSystemDirectoryEntry as d, isFileSystemFileEntry as h, isFunction as y } from "../utils/test.js";
import { eachTree as A, mapTreeAsync as P } from "../utils/tree.js";
import { idleCallbackPromise as T } from "../utils/window.js";
async function G(e, n) {
  const { onprogress: o = E, signal: i } = n ?? {}, { items: s } = e ?? {};
  if (!s)
    return [];
  let t = 0, r = 0;
  const a = u(s), m = await p(a, n);
  if (i?.aborted)
    throw i.reason;
  return A(m, (c) => {
    y(c) && t++;
  }), o({ loaded: r, total: t }), await P(
    m,
    async (c) => {
      if (y(c)) {
        if (i?.aborted)
          throw i.reason;
        const F = await c();
        return r++, o({ loaded: r, total: t }), F;
      }
      return c;
    },
    "entries"
  );
}
async function p(e, n) {
  const { signal: o, ignoredEntryPatterns: i = f } = n ?? {};
  let s = [];
  for (const t of e) {
    if (!t)
      continue;
    if (o?.aborted)
      throw o.reason;
    let r;
    if (d(t) && !l(t.name, i))
      r = {
        name: t.name,
        path: t.fullPath,
        entries: await p(
          await D(t, { ignoredEntryPatterns: i }),
          n
        )
      };
    else if (h(t))
      r = async () => {
        const a = await I(t);
        return a.path = t.fullPath, a;
      };
    else
      continue;
    s.push(r);
  }
  return s;
}
function u(e) {
  return Array.from(e).map(R);
}
function b(e) {
  return Array.from(e).map(k);
}
function R(e) {
  return e.webkitGetAsEntry();
}
function k(e) {
  return e.getAsFile();
}
async function D(e, n) {
  const { ignoredEntryPatterns: o = f } = n, i = e.createReader(), s = [];
  for (; ; ) {
    const t = await new Promise((r, a) => {
      i.readEntries(r, a);
    });
    if (!t.length)
      break;
    for (const r of t)
      l(r.name, o) || s.push(r);
  }
  return s;
}
async function I(e) {
  return await T(), w(e);
}
async function w(e) {
  return new Promise((n) => e.file(n));
}
function L(e) {
  const n = u(e.items);
  return n.some(d) || n.length > 10;
}
async function W(e, n) {
  const { ignoredEntryPatterns: o = f } = n || {};
  let i = u(e.items);
  if (g(i).length === 0)
    return b(e.items);
  const s = [], t = [];
  for (const r of i)
    if (h(r)) {
      if (l(r.name, o))
        continue;
      t.push(w(r));
    }
  return s.push(...await Promise.all(t)), s;
}
export {
  u as dataTransferItemsToEntries,
  b as dataTransferItemsToFiles,
  W as dataTransferToFiles,
  R as getAsEntry,
  k as getAsFile,
  D as readDirectory,
  G as readEntriesFromDataTransfer,
  L as shouldLoadWithIdleCallback
};
