/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createTransformExtension as x } from "./common/createTransformExtension.js";
import { isString as m } from "../utils/test.js";
import { sanitizeFilename as p, getFilenameWithoutExtension as u, getExtensionFromFilename as y, updateFilename as F } from "../utils/file.js";
const b = x({
  name: "FileNameTransform",
  props: {
    actionTransform: "renameFile",
    sanitizeName: p,
    renameEntry: (t, o) => {
    }
  },
  factory: ({ props: t, extensionName: o }) => ({
    transformEntry: async (n) => {
      const { renameEntry: c, sanitizeName: f, actionTransform: i } = t, { name: a = "" } = n, l = u(a) ?? "", N = y(a) ?? "", r = [...n.extensionState[o].history ?? []], s = (m(n.state[i]) ? n.state[i] : null) || await c(n, {
        basename: l,
        extension: N,
        history: [...r]
      });
      if (!m(s))
        return;
      const e = f(s);
      if (!e.length || e === n.file.name)
        return;
      const E = [...r, n.file.name];
      return {
        file: F(n.file, e),
        history: E
      };
    }
  })
});
export {
  b as FileNameTransform
};
