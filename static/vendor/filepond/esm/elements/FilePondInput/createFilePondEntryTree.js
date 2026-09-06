/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createEntryTree as E } from "../../core/entryTree.js";
import { isFileEntry as f, isNumber as b, isString as s, isFile as o, isObject as a, isDataTransfer as l, isDirectoryEntry as S, isBlobOrFile as g, isCanvas as F } from "../../utils/test.js";
import { copyFilePropsToObject as c } from "../../utils/file.js";
import { getFilenameFromURL as x } from "../../utils/url.js";
function j(t) {
  const { beforeInsertEntries: e } = t || {};
  return E({
    // allows limiting the total entries added
    beforeInsertEntries: e,
    // formats the entry so all entries in the dataset follow the same data structure
    beforeOnboardEntry(r) {
      return u(r) ? m(r) : !1;
    },
    // makes modifications to the props the entry is updated with
    beforeUpdateEntryWithProps(r, i, d) {
      if (f(r) && d && c(i.file, i), i.extensionState) {
        const p = Object.values(
          i.extensionState
        );
        for (const { status: n } of p)
          n && (n.values = n.values ?? null, n.progress = b(n.progress) ? n.progress : null);
      }
    }
  });
}
function h(t) {
  return s(t) || g(t) || F(t) || l(t);
}
function u(t) {
  if (s(t) || f(t)) {
    const e = s(t) ? x(t) ?? "" : t.name ?? (o(t?.src) ? t.src.name : "");
    return ![
      /\.git/,
      /thumbs\.db/,
      /\.DS_Store/,
      /desktop\.ini/,
      /^__MACOSX/,
      /node_modules/
    ].find((r) => r.test(e));
  }
  return !0;
}
function m(t) {
  const e = h(t) ? { src: t } : { ...t };
  if (e.state = a(e.state) ? e.state : {}, e.extensionState = a(e.extensionState) ? e.extensionState : {}, e.origin = e.origin ?? "api", e.containerId = e.containerId ?? null, l(e.src))
    return e;
  if (e.path = e.path ?? e.src?.path ?? null, S(e)) {
    const { entries: i } = e;
    return e.entries = i.filter(u).map(m), e;
  }
  const r = e;
  return r.file = r.file ?? void 0, o(r.src) && (r.file = r.src), o(r.file) && c(r.file, r), r;
}
export {
  j as createFilePondEntryTree
};
