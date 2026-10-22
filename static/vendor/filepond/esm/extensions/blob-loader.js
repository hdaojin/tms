/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as u } from "./common/createExtension.js";
import { isFileEntry as b, isBlob as F, isFile as g } from "../utils/test.js";
import { blobToFile as B } from "../utils/file.js";
import { Status as i } from "../common/status.js";
import { getFilename as E, getExtension as L, getBasename as h } from "../common/entry.js";
const D = u({
  name: "BlobLoader",
  type: "loader",
  props: {
    mimeTypeMap: void 0,
    getBasename: h,
    getExtension: L,
    getFilename: E
  },
  factory: ({ props: s }, { on: a, updateEntry: c, pushTask: l, setEntryExtensionStatus: t, getEntryExtensionStatus: m }) => {
    function p(o) {
      o = t(o, {
        type: i.System,
        code: "LOAD_BUSY",
        progress: 1 / 0
      });
      const r = o.src;
      try {
        const { getFilename: e } = s, f = B(r, e(o, r, s));
        c(o, { file: f });
      } catch (e) {
        throw t(o, {
          type: i.Error,
          code: "LOAD_ERROR",
          values: { error: e }
        }), e;
      }
      t(o, {
        type: i.Success,
        code: "LOAD_COMPLETE"
      });
    }
    function d(o) {
      m(o)?.type === "error" || !b(o) || !F(o.src) || g(o.file) || l(o.id, p);
    }
    const n = a("updateEntry", d);
    return {
      destroy: () => {
        n();
      }
    };
  }
});
export {
  D as BlobLoader
};
