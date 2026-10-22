/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as se } from "../../../vendor/svelte/src/index-client.js";
import { user_effect as ce, template_effect as E } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { pop as ue, push as me } from "../../../vendor/svelte/src/internal/client/context.js";
import { get as e } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { child as I, sibling as g, only_child as H, first_child as de } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as s, set as o } from "../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { set_text as W } from "../../../vendor/svelte/src/internal/client/render.js";
import { user_derived as L } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as j, append as T } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as V } from "../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { attach as fe } from "../../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { set_attribute as b } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { delegate as ve, event as G, delegated as J } from "../../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { set_style as pe } from "../../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { proxy as he } from "../../../vendor/svelte/src/internal/client/proxy.js";
import { bind_this as x } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as C } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { getExtensionFromMimeType as ge, blobToFile as be } from "../../../utils/file.js";
import { measurable as we } from "../../attachments/measurable.js";
import { rectFromBounds as ye } from "../../../utils/rect.js";
import "../ProgressIndicator/index.js";
import { canvasToBlob as _e } from "../../../utils/canvasToBlob.js";
import { isFunction as xe } from "../../../utils/test.js";
import { dispatchCustomEvent as k, resetFileInput as Ce, filesToFileList as Me } from "../../../utils/dom.js";
import Fe from "../ProgressIndicator/index-svelte.js";
var Re = j('<p class="status"> </p>'), Ee = j('<button class="capture" type="button"> </button> <button class="reset" type="button"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><path d="M20 6a1 1 0 0 1 .117 1.993l-.117 .007h-.081l-.919 11a3 3 0 0 1 -2.824 2.995l-.176 .005h-8c-1.598 0 -2.904 -1.249 -2.992 -2.75l-.005 -.167l-.923 -11.083h-.08a1 1 0 0 1 -.117 -1.993l.117 -.007zm-10 4a1 1 0 0 0 -1 1v6a1 1 0 0 0 2 0v-6a1 1 0 0 0 -1 -1m4 0a1 1 0 0 0 -1 1v6a1 1 0 0 0 2 0v-6a1 1 0 0 0 -1 -1"></path><path d="M14 2a2 2 0 0 1 2 2a1 1 0 0 1 -1.993 .117l-.007 -.117h-4l-.007 .117a1 1 0 0 1 -1.993 -.117a2 2 0 0 1 1.85 -1.995l.15 -.005z"></path></svg></button>', 1), Ie = j('<camera-input><div class="camera"><!> <video class="feed"></video> <canvas class="preview"></canvas> <div class="camera-footer"><input class="implicit" type="file"/> <!></div></div></camera-input>', 2);
function et(K, l) {
  me(l, !0), C(l, "reduceMotion", 3, !1);
  let M = C(l, "filename", 3, "Untitled"), q = C(l, "labelCapture", 3, "capture"), O = C(l, "labelReset", 3, "reset"), p = s(void 0), v;
  function N(t, r) {
    t.files = Me([r]);
  }
  let u = s(null), a = s(null), n = s(null), F = s(void 0), R = s(!1), m = s(he(["load"]));
  function Q() {
    o(m, ["ready"], !0);
  }
  const X = function(t) {
    return e(a) ? z(t) : new Promise((r, i) => {
      B = () => {
        z().then(r).catch(i);
      };
    });
  }, z = function(t) {
    return new Promise((r, i) => {
      navigator.mediaDevices.getUserMedia({ video: !0, audio: !1, ...t }).then((f) => {
        e(a) && (e(a).srcObject = f, o(R, !0), r(f));
      }).catch((f) => {
        o(F, f.message, !0), i(f);
      });
    });
  };
  let B;
  ce(() => {
    e(a) && B?.();
  });
  function Y() {
    if (!e(n))
      return;
    const t = e(n).getContext("2d");
    t && (t.clearRect(0, 0, e(n).width, e(n).height), o(m, e(m).filter((r) => r !== "preview"), !0), o(u, null), Ce(v), v.dispatchEvent(new CustomEvent("change", { bubbles: !0 })), k(e(p), "reset"));
  }
  let c = s(null);
  function Z() {
    e(a) && (o(
      c,
      {
        width: e(a).videoWidth,
        height: e(a).videoHeight
      },
      !0
    ), e(a).play());
  }
  async function $() {
    if (!e(a) || !e(n))
      return;
    o(m, [...e(m), "processing"], !0), e(n).width = e(a).videoWidth, e(n).height = e(a).videoHeight;
    const t = e(n).getContext("2d");
    t && (t.save(), t.scale(-1, 1), t.drawImage(e(a), e(n).width * -1, 0), t.restore(), _e(e(n), { ...l.blobOptions }).then((r) => {
      const i = ge(r.type);
      o(u, be(r, `${xe(M()) ? M()(r) : M()}${i}`), !0), N(v, e(u)), v.dispatchEvent(new CustomEvent("change", { bubbles: !0 })), l.oncapture?.(e(u)), k(e(p), "capture", { detail: e(u) }), o(m, ["ready", "preview"], !0);
    }).catch((r) => {
      l.onerror?.(r), k(e(p), "error", { detail: r });
    }));
  }
  let d = s(null);
  function ee(t) {
    e(c) && o(d, ye(t), !0);
  }
  const P = L(() => e(d) && e(c) ? {
    x: (e(d).width - e(c).width) * 0.5,
    y: (e(d).height - e(c).height) * 0.5
  } : { x: 0, y: 0 }), te = L(() => e(d) && e(c) ? Math.min(e(d).width / e(c).width, e(d).height / e(c).height) : 1);
  se(() => {
    if (!e(a))
      return;
    e(a).srcObject?.getTracks().forEach((r) => {
      r.stop();
    }), e(a).pause(), e(a).srcObject = null;
  });
  var re = { requestCameraAccess: X }, S = Ie(), h = I(S);
  let U;
  var A = I(h);
  {
    var ae = (t) => {
      var r = Re(), i = H(r, !0);
      E(() => W(i, e(F))), T(t, r);
    }, ie = (t) => {
      Fe(t, { value: 1 / 0 });
    };
    V(A, (t) => {
      e(F) ? t(ae) : t(ie, -1);
    });
  }
  var w = g(A, 2);
  x(w, (t) => o(a, t), () => e(a));
  var D = g(w, 2);
  x(D, (t) => o(n, t), () => e(n));
  var oe = g(D, 2), y = I(oe);
  x(y, (t) => v = t, () => v);
  var ne = g(y, 2);
  {
    var le = (t) => {
      var r = Ee(), i = de(r), f = H(i, !0), _ = g(i, 2);
      E(() => {
        b(i, "title", q()), i.disabled = !!e(u), W(f, q()), _.disabled = !e(u), b(_, "title", O()), b(_, "aria-label", O());
      }), J("click", i, $), J("click", _, Y), T(t, r);
    };
    V(ne, (t) => {
      e(R) && t(le);
    });
  }
  return x(h, (t) => o(p, t), () => e(p)), fe(h, () => we({ onmeasure: ee })), E(
    (t) => {
      b(h, "data-state", t), U = pe(h, "", U, {
        "--scalar": e(te),
        "--translate-x": `${e(P).x}px`,
        "--translate-y": `${e(P).y}px`,
        "--progress-opacity": e(R) ? 0 : 1
      }), b(y, "name", l.name), y.required = l.required;
    },
    [() => e(m).join(" ")]
  ), G("loadedmetadata", w, Z), G("loadeddata", w, Q), T(K, S), ue(re);
}
ve(["click"]);
export {
  et as default
};
