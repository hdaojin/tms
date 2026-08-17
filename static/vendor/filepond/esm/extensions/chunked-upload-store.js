/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createStoreExtension as H } from "./common/createStoreExtension.js";
import { isString as g, isFileEntry as I, isFile as K, isNumber as z } from "../utils/test.js";
import { didAbort as x } from "../utils/abort.js";
import { naturalFileSizeToBytes as L } from "../utils/file.js";
import { passthrough as k, noop as $ } from "../utils/placeholder.js";
import { sleep as J } from "../utils/sleep.js";
import { createProgressEvent as N, xhr as S, getResponseHeaders as j } from "../utils/xhr.js";
import { warn as G } from "../common/console.js";
const oe = H({
  name: "ChunkedUploadStore",
  props: {
    url: "",
    chunkSize: 1 / 0,
    retryDelays: [500, 1e3, 3e3],
    parallelChunks: 2,
    resume: !1,
    resolveRequest: {},
    resolveResponse: {}
  },
  factory: ({ props: v, didSetProps: U }, { updateEntry: P }) => {
    let R = 1 / 0;
    U(({ chunkSize: e }) => {
      if (R = g(e) ? L(e) : e || 1 / 0, R <= 1024) {
        G("Chunk size has to be more than 1 kilobyte");
        return;
      }
    });
    function E(e, r) {
      const { valueKey: s } = v;
      P(e, {
        state: {
          [s]: r
        }
      });
    }
    function b(e) {
      const r = [], s = Math.floor(e.size / R);
      for (let a = 0; a <= s; a++) {
        const u = a * R || 0, l = e.slice(
          u,
          Math.min(u + R, e.size),
          "application/offset+octet-stream"
        );
        r.push({
          index: a,
          offset: u,
          size: l.size,
          data: l
        });
      }
      return r;
    }
    async function F(e, r, s) {
      const {
        url: a,
        resolveRequest: { create: u = k },
        resolveResponse: { create: l = ({ value: i }) => i }
      } = v, { signal: n } = r ?? {}, c = await u({
        url: a,
        options: {
          method: "POST",
          headers: {
            uploadLength: e.size
          }
        },
        entry: s
      }), o = await S(c.url, {
        ...c.options,
        signal: n
      }), t = l({
        request: c,
        response: o,
        value: o.response,
        entry: s
      });
      if (!g(t) || !t.length)
        throw new Error("No server id returned");
      return t;
    }
    async function O(e, r, s) {
      const {
        url: a,
        resolveRequest: { status: u = k },
        resolveResponse: { status: l = ({ value: d }) => d }
      } = v, { signal: n } = r ?? {}, c = await u({
        url: a,
        options: {
          method: "HEAD",
          queryString: {
            id: e
          }
        },
        entry: s
      }), o = await S(c.url, {
        ...c.options,
        signal: n
      }), { uploadOffset: t } = j(o), i = l({
        request: c,
        response: o,
        value: {
          id: e,
          offset: g(t) && t.length ? parseInt(t, 10) : Number.NaN
        },
        entry: s
      }), m = z(i.offset) && !Number.isNaN(i.offset), p = Array.isArray(i.chunks);
      if (!m && !p)
        throw new Error("No upload status returned");
      return i;
    }
    async function T(e, r, { uploadName: s, uploadLength: a }, u, l) {
      const {
        url: n,
        retryDelays: c,
        resolveRequest: { chunk: o = k },
        resolveResponse: { chunk: t = ({ value: p }) => p }
      } = v, { onprogress: i, signal: m } = u ?? {};
      for (const p of [...c, void 0])
        try {
          const d = await o({
            url: n,
            options: {
              method: "PATCH",
              headers: {
                uploadOffset: e.offset,
                uploadName: s,
                uploadLength: a
              },
              data: e.data,
              queryString: {
                contentType: "application/offset+octet-stream",
                id: r
              }
            },
            entry: l,
            chunk: e
          }), y = await S(d.url, {
            ...d.options,
            onprogress: i,
            signal: m
          });
          return t({
            request: d,
            response: y,
            value: {
              index: e.index,
              offset: e.offset,
              size: e.size
            },
            entry: l,
            id: r,
            chunk: e
          });
        } catch (d) {
          if (x(m, d))
            throw d;
          if (z(p))
            await J(p);
          else
            throw d;
        }
      throw new Error("Chunk upload failed");
    }
    async function A(e, r, { uploadName: s, uploadLength: a }, u, l) {
      const { parallelChunks: n } = v, { onprogress: c = $, signal: o } = u ?? {}, t = [], i = parseInt(a, 10), m = e.reduce((f, h) => f + h.size, 0);
      let p = Math.max(0, i - m);
      const d = /* @__PURE__ */ new Map(), y = () => {
        const f = Array.from(d.values()).reduce(
          (q, C) => q + C,
          0
        ), h = Math.min(p + f, i);
        c(N(!0, h, i));
      }, B = (f, h) => {
        h.lengthComputable && (d.set(f.index, Math.min(h.loaded, f.size)), y());
      };
      if (o?.aborted)
        throw o.reason;
      let w = [];
      const D = (f, h) => {
        const q = h.then((C) => {
          d.delete(f.index), p += f.size, t.push(C), y();
        }).finally(() => {
          w = w.filter((C) => C !== q);
        });
        w.push(q);
      };
      y();
      for (const f of e) {
        if (o?.aborted)
          throw o.reason;
        const h = T(
          f,
          r,
          {
            uploadName: s,
            uploadLength: a
          },
          {
            onprogress: (q) => B(f, q),
            signal: o
          },
          l
        );
        D(f, h), !(w.length < n) && await Promise.race(w);
      }
      return await Promise.all(w), t.sort((f, h) => f.index - h.index);
    }
    async function M(e, r, s, a) {
      const {
        url: u,
        resolveRequest: { complete: l },
        resolveResponse: { complete: n = ({ value: m }) => m }
      } = v, { signal: c } = s ?? {};
      if (!l)
        return e;
      const o = await l({
        url: u,
        options: {
          method: "POST",
          data: JSON.stringify({ chunks: r }),
          queryString: {
            id: e
          }
        },
        entry: a,
        id: e,
        chunks: r
      }), t = await S(o.url, {
        ...o.options,
        signal: c
      }), i = n({
        request: o,
        response: t,
        value: g(t.response) && t.response.length ? t.response : e,
        entry: a,
        id: e,
        chunks: r
      });
      if (!g(i) || !i.length)
        throw new Error("No server id returned");
      return i;
    }
    return {
      storeEntry: async (e, { onprogress: r, signal: s }) => {
        if (!I(e) || !K(e.file))
          return;
        const a = b(e.file), { resume: u, valueKey: l } = v;
        let n = e.state[l], c = 0, o = [];
        if (r(N()), !n)
          n = await F(e.file, { signal: s }, e), E(e, n);
        else
          try {
            const t = await O(n, { signal: s }, e);
            c = t.offset ?? 0, o = t.chunks ?? [];
          } catch (t) {
            throw x(s, t) && E(e, n), t;
          }
        try {
          const t = await A(
            // get chunks that still need to be uploaded
            a.filter((i) => !o.some(
              (p) => p.index === i.index || p.offset === i.offset
            ) && i.offset >= c),
            // need to add them to this transfer
            n,
            // file headers
            {
              uploadName: `${e.file.name}`,
              uploadLength: `${e.file.size}`
            },
            // upload progress
            {
              onprogress: r,
              signal: s
            },
            // entry reference
            e
          );
          o = [...o, ...t];
        } catch (t) {
          throw u && x(s, t) && E(e, n), t;
        }
        return M(n, o, { signal: s }, e);
      },
      releaseEntry: async (e, r, s) => {
        const {
          url: a,
          resolveRequest: { release: u = k }
        } = v, { signal: l } = s ?? {}, n = await u({
          url: a,
          options: {
            method: "DELETE",
            queryString: {
              id: e
            }
          },
          entry: r,
          id: e
        });
        return await S(n.url, {
          ...n.options,
          signal: l
        }), !0;
      }
    };
  }
});
export {
  oe as ChunkedUploadStore
};
