/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtension as v } from "./common/createExtension.js";
import { isFileEntry as F, isFile as b, isCanvas as g } from "../utils/test.js";
import { canvasToBlob as h } from "../utils/canvasToBlob.js";
import { Status as s } from "../common/status.js";
import { blobToFile as C } from "../utils/file.js";
import { getFilename as L, getExtension as S, getBasename as T } from "../common/entry.js";
const U = v({
  name: "CanvasLoader",
  type: "loader",
  props: {
    parallel: 1,
    type: void 0,
    quality: void 0,
    mimeTypeMap: void 0,
    getBasename: T,
    getExtension: S,
    getFilename: L
  },
  factory: ({ props: e }, l) => {
    const { on: c, updateEntry: p, pushTask: m, setEntryExtensionStatus: a, getEntryExtensionStatus: d } = l;
    async function u(t) {
      t = a(t, {
        type: s.System,
        code: "LOAD_BUSY",
        progress: 1 / 0
      });
      try {
        const { type: o, quality: i, getFilename: n } = e, r = await h(t.src, {
          type: o,
          quality: i
        }), y = C(r, n(t, r, e));
        t = p(t, { file: y });
      } catch (o) {
        throw a(t, {
          type: s.Error,
          code: "LOAD_ERROR",
          values: { error: o }
        }), o;
      }
      a(t, {
        type: s.Success,
        code: "LOAD_COMPLETE"
      });
    }
    function E(t) {
      const { parallel: o } = e;
      d(t)?.type === "error" || !F(t) || b(t.file) || !g(t.src) || m(t.id, u, { parallel: o });
    }
    const f = c("updateEntry", E);
    return {
      destroy: () => {
        f();
      }
    };
  }
});
export {
  U as CanvasLoader
};
