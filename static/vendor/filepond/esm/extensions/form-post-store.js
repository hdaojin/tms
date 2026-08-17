/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createStoreExtension as H } from "./common/createStoreExtension.js";
import { blobToFile as P } from "../utils/file.js";
import { isFileEntry as B, isFile as g } from "../utils/test.js";
import { passthrough as p } from "../utils/placeholder.js";
import { xhr as m, getResponseHeaders as E, getFilenameFromResponseHeaders as w } from "../utils/xhr.js";
const k = H({
  name: "FormPostStore",
  props: {
    url: "",
    name: "entry",
    fetchMetadata: !0,
    resolveRequest: {},
    resolveResponse: {},
    getBasename: () => "Untitled"
  },
  factory: ({ props: c }, F) => {
    const { updateEntry: S } = F;
    function T(e) {
      const t = E(e), s = w(t);
      if (s)
        return s;
    }
    return {
      storeEntry: async (e, { onprogress: t, signal: s }) => {
        const {
          name: r,
          url: n,
          valueKey: a,
          resolveRequest: { store: i = p },
          resolveResponse: { store: d = ({ value: R }) => R }
        } = c;
        if (!B(e) || !g(e.file))
          return;
        if (g(e.file) && e.state[a] != null)
          return e.state[a];
        const l = await i({
          url: n,
          options: {
            method: "POST",
            formData: [[r, e.file, e.file.name]]
          },
          entry: e
        }), u = await m(l.url, {
          ...l.options,
          signal: s,
          onprogress: t
        });
        return d({
          request: l,
          response: u,
          value: u.response,
          entry: e
        });
      },
      restoreEntry: async (e, t, { onprogress: s, signal: r }) => {
        const {
          url: n,
          fetchMetadata: a,
          getBasename: i,
          resolveRequest: {
            metadata: d = p,
            restore: l = p
          },
          resolveResponse: {
            metadata: u = ({ value: o }) => o,
            restore: R = ({ value: o }) => o
          }
        } = c;
        if (a) {
          const o = await d({
            url: n,
            options: {
              method: "HEAD",
              queryString: {
                id: e
              }
            },
            entry: t
          }), q = await m(o.url, {
            ...o.options,
            signal: r
          }), { contentType: y, contentLength: M, lastModified: D } = E(q), x = u({
            request: o,
            response: q,
            value: {
              name: T(q),
              type: y,
              size: parseInt(M, 10),
              lastModified: new Date(D).getTime()
            },
            entry: t
          });
          S(t, x);
        }
        const v = await l({
          url: n,
          options: {
            method: "GET",
            queryString: {
              id: e
            }
          },
          entry: t
        }), f = await m(v.url, {
          ...v.options,
          responseType: "blob",
          signal: r,
          onprogress: s
        }), { response: h } = f, b = P(
          h,
          // use entry name if defined
          t.name || // else read from response headers
          w(E(f)) || // else fall back
          i(t, h)
        );
        return R({
          request: v,
          response: f,
          value: b,
          entry: t
        });
      },
      releaseEntry: async (e, t, s) => {
        const {
          url: r,
          resolveRequest: { release: n = p }
        } = c, { signal: a } = s ?? {}, i = await n({
          url: r,
          options: {
            method: "DELETE",
            queryString: {
              id: e
            }
          },
          entry: t
        });
        return await m(i.url, {
          ...i.options,
          signal: a
        }), !0;
      }
    };
  }
});
export {
  k as FormPostStore
};
