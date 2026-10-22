/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onMount as J, onDestroy as K } from "../../../../../vendor/svelte/src/index-client.js";
import { user_effect as v } from "../../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as N, pop as V } from "../../../../../vendor/svelte/src/internal/client/context.js";
import { get as e } from "../../../../../vendor/svelte/src/internal/client/runtime.js";
import { state as s, set as n } from "../../../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_derived as z } from "../../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as X, append as Y } from "../../../../../vendor/svelte/src/internal/client/dom/template.js";
import { bind_this as Z } from "../../../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as m } from "../../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { isFirefox as $ } from "../../../../../utils/test.js";
import { createObjectURL as ee } from "../../../../../utils/objectURL.js";
import { getImageSize as te } from "../../../../../utils/media.js";
import { getAppContext as re } from "../../../contexts/appContext.js";
import { getBitmapCacheItem as ie, setBitmapCacheItem as k } from "./BitmapRendererCache.js";
import { thread as ae, createThreadWorker as oe } from "../../../../../utils/thread.js";
import { transformImage as ne } from "../../../../../workers/transformImage.js";
import { yieldScheduler as D } from "../../../../../common/yield.js";
var me = X('<canvas width="0" height="0"></canvas>');
function xe(O, t) {
  N(t, !0);
  let R = m(t, "taskIgnoreSoftFailure", 3, !1), u = m(t, "maximumPixels", 3, 1024 * 1024), T = m(t, "resizeQuality", 3, "medium"), W = m(t, "workersURL", 3, void 0), j = m(t, "oninit", 3, void 0), y = m(t, "onload", 3, void 0), P = m(t, "onrender", 3, void 0), S = m(t, "onerror", 3, void 0);
  const Q = () => ee(t.file), b = () => t.file.type !== "image/svg+xml", { size: l, canvas: h } = ie(t.file) ?? {};
  let i = l?.width, a = l?.height, x = s(!!l), C = s(!!l), g = s(!!h), c = s(!1);
  v(() => {
    e(c) && P()?.({ didRestore: !!h });
  });
  const { pushTask: L, abortTask: _ } = re();
  let d = s(void 0), r = s(void 0);
  const q = z(() => !!e(r)), p = z(() => e(q) && !e(x)), H = z(() => e(q) && e(C) && !e(g));
  async function E(I, { signal: f }) {
    n(g, !0);
    try {
      const o = await ae(
        oe(W(), ne),
        [
          t.file,
          null,
          {
            resizeWidth: i,
            resizeHeight: a,
            resizeQuality: T(),
            imageOrientation: "from-image"
          }
        ],
        { signal: f }
      );
      f.throwIfAborted(), await D(), e(r).width = i, e(r).height = a, e(r).getContext("bitmaprenderer")?.transferFromImageBitmap(o), k(t.file, { size: { width: i, height: a }, canvas: e(r) }), n(c, !0);
    } catch (o) {
      f.throwIfAborted(), S()?.(o);
    }
  }
  async function G() {
    n(g, !0), await D(), n(d, new Image()), e(d).src = Q(), await e(d).decode(), e(r).width = i, e(r).height = a, e(r).getContext("2d")?.drawImage(e(d), 0, 0, i, a), k(t.file, { size: { width: i, height: a }, canvas: e(r) }), n(c, !0);
  }
  const F = $() || !b() ? G : E;
  async function M(I, { signal: f }) {
    n(x, !0);
    let o;
    try {
      o = await te(t.file);
    } catch (B) {
      throw f.throwIfAborted(), S()?.(B), B;
    }
    f.throwIfAborted();
    let w = 1;
    const A = o.width * o.height;
    u() && (A > u() || !b()) && (w = Math.sqrt(u()) / Math.sqrt(A)), i = Math.floor(o.width * w), a = Math.floor(o.height * w), y()?.({ width: i, height: a }), e(r).width = i, e(r).height = a, k(t.file, { size: { width: i, height: a }, canvas: null }), n(C, !0);
  }
  v(() => {
    e(p) && L(t.taskId, M, { parallel: 1, ignoreSoftFailure: R() });
  }), v(() => {
    e(H) && L(t.taskId, F, { parallel: 1, ignoreSoftFailure: R() });
  }), J(() => {
    j()?.({ willRestore: !!h }), l && (y()?.({ width: i, height: a }), h && (e(r).replaceWith(h), n(c, !0)));
  }), K(() => {
    _(t.taskId, M), _(t.taskId, F), e(d) && URL.revokeObjectURL(e(d).src);
  });
  var U = me();
  Z(U, (I) => n(r, I), () => e(r)), Y(O, U), V();
}
export {
  xe as default
};
