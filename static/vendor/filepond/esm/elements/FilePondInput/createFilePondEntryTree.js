/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createEntryTree as b } from "../../core/entryTree.js";
import { isFileEntry as l, isNumber as F, isString as a, isFile as f, isObject as c, isDataTransfer as u, isDirectoryEntry as x, isBlobOrFile as P, isCanvas as S } from "../../utils/test.js";
import { copyFilePropsToObject as m } from "../../utils/file.js";
import { getFilenameFromURL as h } from "../../utils/url.js";
import { stringMatchesAny as O } from "../../utils/string.js";
import { EMPTY_ARRAY as p } from "../../utils/array.js";
function U(e) {
  const { beforeInsertEntries: i, getIgnoredEntryPatterns: t = () => p } = e || {};
  return b({
    // allows limiting the total entries added
    beforeInsertEntries: i,
    // formats the entry so all entries in the dataset follow the same data structure
    beforeOnboardEntry(r) {
      const n = { ignoredEntryPatterns: t() };
      return E(r, n) ? d(r, n) : !1;
    },
    // makes modifications to the props the entry is updated with
    beforeUpdateEntryWithProps(r, n, o) {
      if (l(r) && o && m(n.file, n), n.extensionState) {
        const g = Object.values(
          n.extensionState
        );
        for (const { status: s } of g)
          s && (s.values = s.values ?? null, s.progress = F(s.progress) ? s.progress : null);
      }
    }
  });
}
function v(e) {
  return a(e) || P(e) || S(e) || u(e);
}
function E(e, i) {
  const { ignoredEntryPatterns: t = p } = i || {};
  if (a(e) || l(e)) {
    const r = a(e) ? h(e) ?? "" : e.name ?? (f(e?.src) ? e.src.name : "");
    return !O(r, t);
  }
  return !0;
}
function d(e, i) {
  const t = v(e) ? { src: e } : { ...e };
  if (t.state = c(t.state) ? t.state : {}, t.extensionState = c(t.extensionState) ? t.extensionState : {}, t.origin = t.origin ?? "api", t.containerId = t.containerId ?? null, u(t.src))
    return t;
  if (t.path = t.path ?? t.src?.path ?? null, x(t)) {
    const { entries: n } = t;
    return t.entries = n.filter((o) => E(o, i)).map((o) => d(o, i)), t;
  }
  const r = t;
  return r.file = r.file ?? void 0, f(r.src) && (r.file = r.src), f(r.file) && m(r.file, r), r;
}
export {
  U as createFilePondEntryTree
};
