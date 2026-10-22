/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as e } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { push as Se, pop as Re } from "../../../vendor/svelte/src/internal/client/context.js";
import { first_child as A, child as b, sibling as k } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as V, set as v } from "../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_effect as w, template_effect as U } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as c } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { comment as ne, append as y, from_html as Ve, from_svg as J } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as H } from "../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { set_custom_element_data as Te, set_attribute as p } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_class as Oe } from "../../../vendor/svelte/src/internal/client/dom/elements/class.js";
import { set_style as De } from "../../../vendor/svelte/src/internal/client/dom/elements/style.js";
import { bind_this as T } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as f } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { clsx as Le } from "../../../vendor/svelte/src/internal/shared/attributes.js";
import { Spring as ie } from "../../../vendor/svelte/src/motion/spring.js";
import { clamp as Ae } from "../../../utils/math.js";
import { isNumber as O, isSafari as Ue } from "../../../utils/test.js";
import { getUniqueId as qe } from "../../../utils/string.js";
var Be = J("<rect></rect><rect></rect>", 1), Ne = J('<g><circle></circle><circle pathLength="1"></circle></g>'), We = J('<mask><rect width="100%" height="100%" fill="black"></rect><rect x="0" y="0" stroke="white"></rect></mask><g><rect></rect><rect pathLength="1"></rect></g>', 1), je = Ve('<progress-indicator><progress></progress> <div><svg aria-hidden="true" focusable="false" xmlns="http://www.w3.org/2000/svg"><!></svg></div></progress-indicator>', 2);
function st(oe, a) {
  Se(a, !0);
  const i = { Line: "line", Circle: "circle", Rectangle: "rectangle" };
  let se = f(a, "class", 3, void 0), q = f(a, "max", 3, 1), ce = f(a, "label", 3, "Busy"), fe = f(a, "direction", 3, "normal"), K = f(a, "shape", 3, "auto"), Q = f(a, "oncomplete", 3, void 0), X = f(a, "onchange", 3, void 0), B = f(a, "precision", 3, 3), N = f(a, "reduceMotion", 3, !1);
  function Y(t) {
    return t.substring(7).slice(0, -1).split(",");
  }
  function le(t) {
    const r = Y(t);
    return Math.atan2(parseFloat(r[1]), parseFloat(r[0]));
  }
  function me(t) {
    const r = Y(t);
    return parseFloat(r[4]);
  }
  let M = V(void 0), h = V(void 0);
  const ue = { stiffness: 0.1, damping: 0.7, precision: 1e-3 }, F = new ie(void 0, { precision: 0.01 }), C = new ie(0, ue);
  let W = V(void 0), P = V(void 0);
  const de = c(() => fe() === "reverse" ? -1 : 1), Z = c(() => O(a.value)), I = c(() => e(Z) && a.value !== 1 / 0);
  w(() => {
    F.set(e(I) ? a.value : 0.5, { instant: N() });
  }), w(() => {
    X() && e(I) && X()(Math.min(a.value, F.current));
  });
  function ge(t, r) {
    if (!t)
      return;
    const s = getComputedStyle(t).getPropertyValue("transform"), u = (r === i.Circle ? le : me)(s);
    C.set(u, { instant: !0 });
    let d;
    r === i.Circle ? d = u > Math.PI / 2 ? Math.PI * 4 : Math.PI * 2 : d = 0, C.set(d, { instant: N() });
  }
  function ve(t) {
    if (!t)
      return;
    const r = parseFloat(getComputedStyle(t).getPropertyValue("stroke-dashoffset"));
    C.set(r, { instant: !0 });
    const s = r < 0.5 ? -1 : 0;
    C.set(s, { instant: N() });
  }
  function pe(t, r) {
    const s = Math.min(r, t / 2), _ = 4 * (t - 2 * s), u = 2 * Math.PI * s, d = _ + u;
    return -((t / 2 - s) / d);
  }
  w(() => {
    e(I) ? (e(W) === !1 && (e(m) === i.Rectangle ? ve(e(h)) : ge(e(m) === i.Circle ? e(P) : e(h), e(m))), v(W, !0)) : v(W, !1);
  });
  const he = c(() => e(I) ? Ae(F.current, 0, q()) : void 0);
  w(() => {
    e(M) && (e(I) ? e(M).setAttribute("value", e(he).toFixed(B())) : e(M).removeAttribute("value"));
  }), w(() => {
    Q() && _e(a.value, F.current);
  });
  function _e(t, r) {
    t < 1 || Math.round(r) < q() || Q()?.();
  }
  let D = V(void 0);
  const L = c(() => e(D) ? getComputedStyle(e(D)) : void 0), j = c(() => !!e(L)), o = c(() => e(j) ? parseFloat(e(L).getPropertyValue("height")) : void 0), l = c(() => e(j) ? parseFloat(e(L).getPropertyValue("border-radius")) : void 0), $ = c(() => e(j) ? parseFloat(e(L).getPropertyValue("--_stroke-width")) : void 0), xe = c(() => O(e(o)) && O(e(l)) ? pe(e(o), e(l)) : void 0), m = c(() => K() !== "auto" ? K() : !O(e(l)) || !O(e(o)) ? i.Circle : e(l) < e(o) * 0.5 ? i.Rectangle : i.Circle), ee = `mask_${qe()}`, te = c(() => Ue() && e(o) && e(l) && e($) ? `data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'><rect width='100%' height='100%' fill='black'/><rect width='${e(o)}' height='${e(o)}' rx='${e(l)}' stroke='white' stroke-width='${e($) * 2}'/></svg>` : void 0);
  w(() => {
    e(P) && e(m) === i.Rectangle && (e(P).style.mask = e(te) ? `url("${e(te)}") luminance` : `url(#${ee})`);
  });
  var be = { ProgressIndicatorShape: i }, re = ne(), ke = A(re);
  {
    var we = (t) => {
      var r = je();
      U(() => Te(r, "shape", e(m)));
      var s = b(r);
      T(s, (n) => v(M, n), () => e(M));
      var _ = k(s, 2);
      let u;
      var d = b(_), ae = b(d);
      {
        var ye = (n) => {
          var g = Be(), z = k(A(g));
          T(z, (E) => v(h, E), () => e(h)), y(n, g);
        }, Me = (n) => {
          var g = ne(), z = A(g);
          {
            var E = (x) => {
              var S = Ne(), R = k(b(S));
              U(() => p(R, "transform", `rotate(-90) translate(-${e(o)})`)), y(x, S);
            }, Fe = (x) => {
              var S = We(), R = A(S), G = k(b(R)), Ce = k(R), Pe = k(b(Ce));
              T(Pe, (Ie) => v(h, Ie), () => e(h)), U(() => {
                p(R, "id", ee), p(G, "width", e(o)), p(G, "height", e(o)), p(G, "rx", e(l));
              }), y(x, S);
            };
            H(z, (x) => {
              e(m) === i.Circle ? x(E) : e(m) === i.Rectangle && x(Fe, 1);
            });
          }
          y(n, g);
        };
        H(ae, (n) => {
          e(m) === i.Line ? n(ye) : e(o) && n(Me, 1);
        });
      }
      T(_, (n) => v(P, n), () => e(P)), T(r, (n) => v(D, n), () => e(D)), U(
        (n, g) => {
          Oe(r, 1, Le(se())), p(s, "aria-label", ce()), p(s, "max", q()), u = De(_, "", u, {
            "--_size": e(o),
            "--_border-radius": e(l),
            "--_offset": n,
            "--_center": e(xe),
            "--_progress": g,
            "--_flip": e(de)
          });
        },
        [
          () => C.current?.toFixed(B()),
          () => F.current?.toFixed(B())
        ]
      ), y(t, r);
    };
    H(ke, (t) => {
      e(Z) && t(we);
    });
  }
  return y(oe, re), Re(be);
}
export {
  st as default
};
