/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { stringReplaceVariables as A } from "../elements/common/string.js";
import { getAsElement as E } from "../utils/dom.js";
import { upperCaseFirstLetter as S } from "../utils/string.js";
import { isString as v } from "../utils/test.js";
import { createExtension as x } from "./common/createExtension.js";
const h = x({
  name: "SourceDescriptionView",
  type: "view",
  props: {
    // uses the locale object for translations
    locale: void 0,
    // maxFiles is used to determine plurality in the label
    maxFiles: void 0,
    // allowed keys, we can extend this list if we want to build more complex labels, this filters out for example the "paste" action
    allowedSourceActions: ["browse", "drop", "select"],
    // prevent adding entries
    preventAddEntries: void 0
  },
  factory: ({ props: l, didSetProps: a }, { on: p }) => {
    let r, n = [], o;
    a(({ element: e }) => {
      e && (r = E(e), i());
    });
    function u(e) {
      return `description${e.sort().map(S).join("")}`;
    }
    function i() {
      const { locale: e, maxFiles: t, allowedSourceActions: f, preventAddEntries: b } = l;
      if (!r || !n.length)
        return;
      const s = u(
        n.filter((y) => f.includes(y))
      ), w = {
        maxFilesUnit: "unitFiles",
        maxFiles: t
      }, c = (e ? A(
        e[s],
        w,
        e
      ) || "" : s).replaceAll(
        "[",
        `<button type="button" data-browse${b ? " disabled" : ""}>`
      ).replaceAll("]", "</button>");
      o !== c && (o = c, r.innerHTML = o);
    }
    function d(e) {
      n = Array.from(
        new Set(
          Object.values(e).filter(
            (t) => t?.source && v(t?.source?.type)
          ).map((t) => t?.source?.type)
        )
      ), r && i();
    }
    const m = p("updateExtensionState", d);
    return {
      destroy() {
        m?.();
      }
    };
  }
});
export {
  h as SourceDescriptionView
};
