/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as e, untrack as F } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { push as se, pop as me } from "../../../../vendor/svelte/src/internal/client/context.js";
import { first_child as fe, child as ue } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as g, set as n } from "../../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_effect as b, template_effect as P } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { comment as de, append as M, from_html as D } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { user_derived as u } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { if_block as ce } from "../../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { each as pe } from "../../../../vendor/svelte/src/internal/client/dom/blocks/each.js";
import { set_custom_element_data as R } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_class as Q } from "../../../../vendor/svelte/src/internal/client/dom/elements/class.js";
import { clsx as B } from "../../../../vendor/svelte/src/internal/shared/attributes.js";
import { prop as d } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import "../MediaPane/index.js";
import { arrayRemoveFalsy as ge } from "../../../../utils/array.js";
import { isImageFile as I, isBlobOrFile as Pe, isURL as ve } from "../../../../utils/test.js";
import { getAppContext as he } from "../../contexts/appContext.js";
import { getEntryContext as ye } from "../../contexts/entryContext.js";
import { filesAreProbablyEqual as Ee } from "../../../../utils/file.js";
import { Status as _e } from "../../../../common/status.js";
import xe from "./components/BitmapRenderer-svelte.js";
import Fe from "../MediaPane/index-svelte.js";
var be = D("<media-image-item><!></media-image-item>", 2), Me = D("<media-image></media-image>", 2);
function Ne(T, l) {
  se(l, !0);
  let w = d(l, "class", 3, void 0), V = d(l, "maximumPixels", 3, void 0), q = d(l, "resizeQuality", 3, void 0), U = d(l, "objectFit", 3, void 0), G = d(l, "overflowAmount", 3, void 0), H = d(l, "enableParallax", 3, void 0);
  const { setEntryExtensionState: A, getEntryExtensionState: J } = he(), c = ye(), y = u(() => c.current.file), K = u(() => J(c.current)), s = u(() => e(K)?.poster);
  let m = g(null);
  b(() => {
    I(e(y)) ? Ee(
      // don't want to re-run when currentFile is assigned
      F(() => e(m)?.file),
      e(
        // newly updated file
        y
      )
    ).then((t) => {
      t || n(m, {
        file: e(y),
        isError: !1,
        isComplete: !1,
        isPoster: !1
      });
    }).catch(E) : e(s) && (Pe(e(s)) && I(e(s)) ? n(m, {
      file: e(s),
      isComplete: !1,
      isPoster: !0,
      isError: !1
    }) : ve(e(s)) && fetch(e(s)).then((t) => {
      if (!t.ok)
        throw new Error("Failed to load poster");
      return t.blob();
    }).then((t) => {
      if (!I(t))
        throw new Error("Poster is not an image");
      return {
        file: t,
        isError: !1,
        isComplete: !1,
        isPoster: !0
      };
    }).then((t) => {
      n(m, t);
    }).catch(E));
  });
  let o = g([]);
  b(() => {
    e(m) && F(() => {
      n(o, ge([e(o).at(-1), e(m)]).sort((t, r) => t.isPoster && !r.isPoster ? -1 : r.isPoster && !t.isPoster ? 1 : 0));
    });
  });
  function N(t) {
    n(o, e(o).map((r) => r.file === t ? { ...r, isComplete: !0 } : r));
  }
  function W(t, r) {
    n(o, e(o).map((i) => i.file === t ? { ...i, isError: r } : i)), e(o).every((i) => i.isError) && E(r);
  }
  const C = u(() => e(o).map(({ file: t, isPoster: r, isComplete: i, isError: a }, v, _) => ({
    // use file as draw key
    key: t,
    // file object
    file: t,
    // previous file was a poster, if this is true we instantly replace the previous image
    replacesPoster: !!e(o)[v - 1]?.isPoster,
    // always make last file active
    active: v === _.length - 1 ? "" : void 0,
    // did draw this file to bitmap
    complete: i ? "" : void 0,
    // is this a poster
    poster: r ? "" : void 0,
    // error state
    error: a || void 0
  })));
  function E(t) {
    A(c.current, {
      status: {
        type: _e.Error,
        code: "MEDIA_LOAD_ERROR",
        values: { error: t, fileMainType: "fileMainTypeImage" }
      }
    }), n(k, !0);
  }
  let k = g(!1), S = g(!1), L = g(!1);
  b(() => {
    const t = { isReady: e(S), isVisible: e(L) };
    F(() => {
      A(c.current, { media: t });
    });
  });
  var O = de(), X = fe(O);
  {
    var Y = (t) => {
      var r = Me();
      pe(r, 21, () => e(C), ({ key: i, file: a, active: v, complete: _, poster: h, replacesPoster: j }) => i, (i, a, v, _) => {
        let h = () => e(a).file, j = () => e(a).active, Z = () => e(a).complete, $ = () => e(a).poster, z = () => e(a).replacesPoster;
        var f = be();
        P(() => R(f, "active", j())), P(() => R(f, "complete", Z())), P(() => R(f, "poster", $()));
        var ee = ue(f);
        {
          const te = (oe, x) => {
            let ae = () => x?.().onInitMedia, ne = () => x?.().onLoadMedia, le = () => x?.().onRenderMedia;
            xe(oe, {
              get file() {
                return h();
              },
              get resizeQuality() {
                return q();
              },
              get maximumPixels() {
                return V();
              },
              get taskId() {
                return c.current.id;
              },
              oninit: () => {
                ae()();
              },
              onload: (p) => {
                n(S, !0), N(h()), ne()(p);
              },
              onrender: ({ didRestore: p }) => {
                n(L, !0), le()({ instant: p });
              },
              onerror: (p) => {
                W(h(), p);
              }
            });
          };
          let re = u(() => z() ? 1 : 0), ie = u(() => z() || e(C).length > 1 ? 1 : 0);
          Fe(ee, {
            get enableParallax() {
              return H();
            },
            get overflowAmount() {
              return G();
            },
            get mediaObjectFit() {
              return U();
            },
            get mediaInitialOpacity() {
              return e(re);
            },
            get mediaInitialScalar() {
              return e(ie);
            },
            children: te,
            $$slots: { default: !0 }
          });
        }
        P(() => Q(f, 1, B(w()))), M(i, f);
      }), P(() => Q(r, 1, B(w()))), M(t, r);
    };
    ce(X, (t) => {
      e(k) || t(Y);
    });
  }
  M(T, O), me();
}
export {
  Ne as default
};
