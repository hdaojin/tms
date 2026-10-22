/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { xhr as T, getResponseHeaderValue as z, getResponseHeaders as D, getFilenameFromResponseHeaders as V } from "../utils/xhr.js";
import { urlToFilename as $ } from "../utils/url.js";
import { isFileEntry as C, isBlobOrFile as G, isString as L, isNumber as j, isDataURL as F } from "../utils/test.js";
import { blobToFile as J, getExtensionFromMimeType as K } from "../utils/file.js";
import { didAbort as A } from "../utils/abort.js";
import { passthrough as M } from "../utils/placeholder.js";
import { createExtension as N } from "./common/createExtension.js";
import { Status as p } from "../common/status.js";
const X = ({ value: f }) => f, ce = N({
  name: "URLLoader",
  type: "loader",
  props: {
    getBasename: () => "Untitled",
    mimeTypeMap: void 0,
    parallel: 2,
    fetchMetadata: !0,
    useWebWorkers: !0,
    workersURL: void 0,
    actionLoad: "load",
    actionAbort: "abort",
    resolveRequest: {},
    resolveResponse: {}
  },
  factory: ({ extensionName: f, props: m }, k) => {
    const {
      on: w,
      removeEntries: O,
      updateEntry: b,
      pushTask: R,
      abortTask: B,
      getEntryExtensionStatus: q,
      getEntryExtensionState: x,
      setEntryExtensionStatus: h,
      createProgressHandler: _
    } = k;
    function g(e, t) {
      const { src: a } = e, { response: o } = t, u = D(t), i = a, n = V(u);
      if (n)
        return n;
      if (F(i)) {
        const { getBasename: r, mimeTypeMap: s } = m;
        return `${r(e, o)}${K(o.type, s)}`;
      }
      return $(i);
    }
    function U(e, t) {
      throw h(e, {
        type: p.Error,
        code: "LOAD_ERROR",
        values: { error: t }
      }), t;
    }
    function S(e) {
      if (L(e) && e.length)
        return !0;
      throw "FilePondEntry has invalid src property";
    }
    async function H(e) {
      h(e, {
        code: "LOAD_QUEUED",
        type: p.System,
        progress: 1 / 0
      });
    }
    async function I(e, { signal: t }) {
      const { src: a } = e;
      h(e, {
        type: p.System,
        code: "LOAD_BUSY",
        progress: 1 / 0
      });
      try {
        if (!S(a))
          return;
        const {
          resolveRequest: { metadata: o = M },
          useWebWorkers: u,
          workersURL: i
        } = m, n = await o({
          url: a,
          options: {
            method: "HEAD"
          },
          entry: e
        }), r = await T(n.url, {
          ...n.options,
          signal: t,
          useWebWorkers: u,
          workersURL: i
        }), { contentType: s, contentLength: d, lastModified: l } = D(r), c = {
          name: g(e, r)
        };
        s && (c.type = s), d && (c.size = parseInt(d, 10)), l && (c.lastModified = new Date(l).getTime()), b(e, {
          ...c,
          extensionState: {
            [f]: {
              fetchedMetadata: !0
            }
          }
        });
      } catch (o) {
        if (A(t, o))
          return;
        U(e, o);
      }
    }
    async function v(e, { signal: t }) {
      const { src: a } = e;
      e = h(e, {
        type: p.System,
        code: "LOAD_BUSY",
        progress: 1 / 0
      });
      try {
        if (!S(a))
          return;
        const {
          resolveRequest: { load: o = M },
          resolveResponse: { load: u = X },
          useWebWorkers: i,
          workersURL: n
        } = m, r = await o({
          url: a,
          options: {
            method: "GET"
          },
          entry: e
        }), s = await T(r.url, {
          ...r.options,
          responseType: "arraybuffer",
          signal: t,
          useWebWorkers: i,
          workersURL: n,
          onprogress: _(e, { code: "LOAD_BUSY" })
        }), { response: d } = s, l = z(
          "content-type",
          s.getAllResponseHeaders()
        ), c = new Blob([d], { type: l }), y = g(e, s), E = u({
          response: s,
          value: J(c, y),
          entry: e
        });
        b(e, {
          file: E,
          extensionState: {
            [f]: {
              status: {
                type: p.Success,
                code: "LOAD_COMPLETE"
              }
            }
          }
        });
      } catch (o) {
        if (A(t, o)) {
          O(e);
          return;
        }
        U(e, o);
      }
    }
    function W(e) {
      if (!C(e) || G(e.file))
        return;
      const t = q(e);
      if (t?.type === "error")
        return;
      const { fetchedMetadata: a = !1 } = x(e), { actionLoad: o, actionAbort: u, fetchMetadata: i, parallel: n } = m, { src: r, name: s, size: d } = e, l = e.state[o], c = e.state[u];
      if (!L(r))
        return;
      if (c)
        return B(e.id, v);
      if (l === !1)
        return;
      const E = L(s) && j(d), Y = i && !F(r);
      if (!a && !E && Y) {
        R(e.id, I);
        return;
      }
      const P = t?.code === "LOAD_BUSY";
      if (!(t?.code === "LOAD_QUEUED") && !P) {
        R(e.id, H);
        return;
      }
      R(e.id, v, { parallel: n });
    }
    const Q = w("updateEntry", W);
    return {
      destroy: () => {
        Q();
      }
    };
  }
});
export {
  ce as URLLoader
};
