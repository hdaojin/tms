/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onMount as Q } from "../../vendor/svelte/src/index-client.js";
import { user_effect as V, template_effect as x } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as X, pop as Y } from "../../vendor/svelte/src/internal/client/context.js";
import { get as t } from "../../vendor/svelte/src/internal/client/runtime.js";
import { sibling as p, child as y } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as c, set as i } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { set_text as Z } from "../../vendor/svelte/src/internal/client/render.js";
import { user_derived as T } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as M, append as _ } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as j } from "../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { attach as $ } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_attribute as tt } from "../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { delegate as et, event as z, delegated as B } from "../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { set_style as rt } from "../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { proxy as at } from "../../vendor/svelte/src/internal/client/proxy.js";
import { bind_this as O } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as ot } from "../../vendor/svelte/src/internal/client/reactivity/props.js";
import { getExtensionFromMimeType as it, blobToFile as nt } from "../../utils/file.js";
import { measurable as st } from "../attachments/measurable.js";
import { rectFromBounds as lt } from "../../utils/rect.js";
import "../components/ProgressIndicator/index.js";
import { canvasToBlob as ct } from "../../utils/canvasToBlob.js";
import { isFunction as dt } from "../../utils/test.js";
import mt from "../components/ProgressIndicator/index-svelte.js";
var ut = M('<p class="status"> </p>'), ft = M('<div class="camera-footer"><button class="capture" type="button">Capture</button> <button class="reset" type="button" aria-label="Reset"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M20 6a1 1 0 0 1 .117 1.993l-.117 .007h-.081l-.919 11a3 3 0 0 1 -2.824 2.995l-.176 .005h-8c-1.598 0 -2.904 -1.249 -2.992 -2.75l-.005 -.167l-.923 -11.083h-.08a1 1 0 0 1 -.117 -1.993l.117 -.007zm-10 4a1 1 0 0 0 -1 1v6a1 1 0 0 0 2 0v-6a1 1 0 0 0 -1 -1m4 0a1 1 0 0 0 -1 1v6a1 1 0 0 0 2 0v-6a1 1 0 0 0 -1 -1"></path><path d="M14 2a2 2 0 0 1 2 2a1 1 0 0 1 -1.993 .117l-.007 -.117h-4l-.007 .117a1 1 0 0 1 -1.993 -.117a2 2 0 0 1 1.85 -1.995l.15 -.005z"></path></svg></button></div>'), ht = M('<div class="camera"><!> <video class="feed"></video> <canvas class="preview"></canvas> <!></div>', 2);
function Ht(S, u) {
  X(u, !0);
  let g = ot(u, "filename", 3, "Untitled"), f = c(null), r = c(null), o = c(null), w = c(void 0), b = c(!1), d = c(at(["load"]));
  function U() {
    i(d, ["ready"], !0);
  }
  const q = function(e) {
    return t(r) ? C(e) : new Promise((a, n) => {
      F = () => {
        C().then(a).catch(n);
      };
    });
  }, C = function(e) {
    return new Promise((a, n) => {
      navigator.mediaDevices.getUserMedia({ video: !0, audio: !1, ...e }).then((l) => {
        t(r) && (t(r).srcObject = l, i(b, !0), a(l));
      }).catch((l) => {
        i(w, l.message, !0), n(l);
      });
    });
  };
  let F;
  V(() => {
    t(r) && F?.();
  });
  function A() {
    if (!t(o))
      return;
    const e = t(o).getContext("2d");
    e && (e.clearRect(0, 0, t(o).width, t(o).height), i(d, t(d).filter((a) => a !== "preview"), !0), i(f, null), u.onreset?.());
  }
  let s = c(null);
  function H() {
    t(r) && (i(
      s,
      {
        width: t(r).videoWidth,
        height: t(r).videoHeight
      },
      !0
    ), t(r).play());
  }
  async function W() {
    if (!t(r) || !t(o))
      return;
    i(d, [...t(d), "processing"], !0), t(o).width = t(r).videoWidth, t(o).height = t(r).videoHeight;
    const e = t(o).getContext("2d");
    e && (e.save(), e.scale(-1, 1), e.drawImage(t(r), t(o).width * -1, 0), e.restore(), ct(t(o), { ...u.blobOptions }).then((a) => {
      const n = it(a.type);
      i(f, nt(a, `${dt(g()) ? g()(a) : g()}${n}`), !0), u.oncapture?.(t(f)), i(d, ["ready", "preview"], !0);
    }).catch((a) => {
      u.onerror?.(a);
    }));
  }
  let m = c(null);
  function D(e) {
    t(s) && i(m, lt(e), !0);
  }
  const R = T(() => t(m) && t(s) ? {
    x: (t(m).width - t(s).width) * 0.5,
    y: (t(m).height - t(s).height) * 0.5
  } : { x: 0, y: 0 }), E = T(() => t(m) && t(s) ? Math.min(t(m).width / t(s).width, t(m).height / t(s).height) : 1);
  Q(() => () => {
    t(r) && (t(r).pause(), t(r).srcObject = null);
  });
  var G = { requestCameraAccess: q }, h = ht();
  let k;
  var I = y(h);
  {
    var J = (e) => {
      var a = ut(), n = y(a);
      x(() => Z(n, t(w))), _(e, a);
    }, K = (e) => {
      mt(e, { value: 1 / 0 });
    };
    j(I, (e) => {
      t(w) ? e(J) : e(K, -1);
    });
  }
  var v = p(I, 2);
  O(v, (e) => i(r, e), () => t(r));
  var P = p(v, 2);
  O(P, (e) => i(o, e), () => t(o));
  var L = p(P, 2);
  {
    var N = (e) => {
      var a = ft(), n = y(a), l = p(n, 2);
      x(() => {
        n.disabled = !!t(f), l.disabled = !t(f);
      }), B("click", n, W), B("click", l, A), _(e, a);
    };
    j(L, (e) => {
      t(b) && e(N);
    });
  }
  return $(h, () => st({ onmeasure: D })), x(
    (e) => {
      tt(h, "data-state", e), k = rt(h, "", k, {
        "--scalar": t(E),
        "--translate-x": `${t(R).x}px`,
        "--translate-y": `${t(R).y}px`,
        "--progress-opacity": t(b) ? 0 : 1
      });
    },
    [() => t(d).join(" ")]
  ), z("loadedmetadata", v, H), z("loadeddata", v, U), _(S, h), Y(G);
}
et(["click"]);
export {
  Ht as default
};
