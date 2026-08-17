/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { stringReplaceVariables as w } from "../elements/common/string.js";
import { getAsElement as A } from "../utils/dom.js";
import { upperCaseFirstLetter as E } from "../utils/string.js";
import { isString as S } from "../utils/test.js";
import { createExtension as v } from "./common/createExtension.js";
const U = v({
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
  factory: ({ props: s, didSetProps: c }, { on: l }) => {
    let r, o = [];
    c(({ element: e }) => {
      e && (r = A(e), n());
    });
    function a(e) {
      return `description${e.sort().map(E).join("")}`;
    }
    function n() {
      const { locale: e, maxFiles: t, allowedSourceActions: d, preventAddEntries: m } = s;
      if (!r || !o.length)
        return;
      const i = a(
        o.filter((y) => d.includes(y))
      ), f = {
        maxFilesUnit: "unitFiles",
        maxFiles: t
      }, b = e ? w(
        e[i],
        f,
        e
      ) || "" : i;
      r.innerHTML = b.replaceAll(
        "[",
        `<button type="button" data-browse${m ? " disabled" : ""}>`
      ).replaceAll("]", "</button>");
    }
    function p(e) {
      o = Array.from(
        new Set(
          Object.values(e).filter(
            (t) => t?.source && S(t?.source?.type)
          ).map((t) => t?.source?.type)
        )
      ), r && n();
    }
    const u = l("updateExtensionState", p);
    return {
      destroy() {
        u?.();
      }
    };
  }
});
export {
  U as SourceDescriptionView
};
