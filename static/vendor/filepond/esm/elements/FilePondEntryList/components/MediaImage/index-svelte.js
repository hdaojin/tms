/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as e, untrack as F } from "../../../../vendor/svelte/src/internal/client/runtime.js";
import { push as me, pop as fe } from "../../../../vendor/svelte/src/internal/client/context.js";
import { first_child as ue, child as de } from "../../../../vendor/svelte/src/internal/client/dom/operations.js";
import { state as d, set as o } from "../../../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { user_effect as b, template_effect as h } from "../../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as c } from "../../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { comment as ce, append as M, from_html as T } from "../../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as pe } from "../../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { each as ge } from "../../../../vendor/svelte/src/internal/client/dom/blocks/each.js";
import { set_custom_element_data as R } from "../../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { set_class as B } from "../../../../vendor/svelte/src/internal/client/dom/elements/class.js";
import { clsx as D } from "../../../../vendor/svelte/src/internal/shared/attributes.js";
import { prop as p } from "../../../../vendor/svelte/src/internal/client/reactivity/props.js";
import "../MediaPane/index.js";
import { arrayRemoveFalsy as he } from "../../../../utils/array.js";
import { isImageFile as C, isBlobOrFile as Pe, isURL as ve } from "../../../../utils/test.js";
import { getAppContext as ye } from "../../contexts/appContext.js";
import { getEntryContext as Ee } from "../../contexts/entryContext.js";
import { filesAreProbablyEqual as xe } from "../../../../utils/file.js";
import { Status as _e } from "../../../../common/status.js";
import Fe from "./components/BitmapRenderer-svelte.js";
import be from "../MediaPane/index-svelte.js";
var Me = T("<media-image-item><!></media-image-item>", 2), Re = T("<media-image></media-image>", 2);
function We(V, l) {
  me(l, !0);
  let I = p(l, "class", 3, void 0), q = p(l, "maximumPixels", 3, void 0), U = p(l, "resizeQuality", 3, void 0), G = p(l, "objectFit", 3, void 0), H = p(l, "overflowAmount", 3, void 0), J = p(l, "enableParallax", 3, void 0);
  const { setEntryExtensionState: w, getEntryExtensionState: K } = ye(), g = Ee(), y = c(() => g.current.file), N = c(() => K(g.current)), m = c(() => e(N)?.poster);
  let f = d(null);
  b(() => {
    C(e(y)) ? xe(
      // don't want to re-run when currentFile is assigned
      F(() => e(f)?.file),
      e(
        // newly updated file
        y
      )
    ).then((t) => {
      t || o(f, {
        file: e(y),
        isError: !1,
        isComplete: !1,
        isPoster: !1
      });
    }).catch(E) : e(m) && (Pe(e(m)) && C(e(m)) ? o(f, {
      file: e(m),
      isComplete: !1,
      isPoster: !0,
      isError: !1
    }) : ve(e(m)) && fetch(e(m)).then((t) => {
      if (!t.ok)
        throw new Error("Failed to load poster");
      return t.blob();
    }).then((t) => {
      if (!C(t))
        throw new Error("Poster is not an image");
      return {
        file: t,
        isError: !1,
        isComplete: !1,
        isPoster: !0
      };
    }).then((t) => {
      o(f, t);
    }).catch(E));
  });
  let a = d([]);
  b(() => {
    e(f) && F(() => {
      o(a, he([e(a).at(-1), e(f)]).sort((t, r) => t.isPoster && !r.isPoster ? -1 : r.isPoster && !t.isPoster ? 1 : 0));
    });
  });
  function W(t) {
    o(a, e(a).map((r) => r.file === t ? { ...r, isComplete: !0 } : r));
  }
  function X(t, r) {
    o(a, e(a).map((i) => i.file === t ? { ...i, isError: r } : i)), e(a).every((i) => i.isError) && E(r);
  }
  const A = c(() => e(a).map(({ file: t, isPoster: r, isComplete: i, isError: n }, P, x) => ({
    // use file as draw key
    key: t,
    // file object
    file: t,
    // previous file was a poster, if this is true we instantly replace the previous image
    replacesPoster: !!e(a)[P - 1]?.isPoster,
    // always make last file active
    active: P === x.length - 1 ? "" : void 0,
    // did draw this file to bitmap
    complete: i ? "" : void 0,
    // is this a poster
    poster: r ? "" : void 0,
    // error state
    error: n || void 0
  })));
  function E(t) {
    w(g.current, {
      status: {
        type: _e.Error,
        code: "MEDIA_LOAD_ERROR",
        values: { error: t, fileMainType: "fileMainTypeImage" }
      }
    }), o(k, !0);
  }
  let k = d(!1), L = d(!1), O = d(!1), S = d(!1);
  b(() => {
    const t = {
      isCached: e(S),
      isReady: e(L),
      isVisible: e(O)
    };
    F(() => {
      w(g.current, { media: t });
    });
  });
  var j = ce(), Y = ue(j);
  {
    var Z = (t) => {
      var r = Re();
      ge(r, 21, () => e(A), ({ key: i, file: n, active: P, complete: x, poster: v, replacesPoster: z }) => i, (i, n, P, x) => {
        let v = () => e(n).file, z = () => e(n).active, $ = () => e(n).complete, ee = () => e(n).poster, Q = () => e(n).replacesPoster;
        var u = Me();
        h(() => R(u, "active", z())), h(() => R(u, "complete", $())), h(() => R(u, "poster", ee()));
        var te = de(u);
        {
          const re = (ae, _) => {
            let ne = () => (_?.()).onInitMedia, le = () => (_?.()).onLoadMedia, se = () => (_?.()).onRenderMedia;
            Fe(ae, {
              get file() {
                return v();
              },
              get resizeQuality() {
                return U();
              },
              get maximumPixels() {
                return q();
              },
              get taskId() {
                return g.current.id;
              },
              oninit: ({ willRestore: s }) => {
                o(S, s, !0), ne()();
              },
              onload: (s) => {
                o(L, !0), W(v()), le()(s);
              },
              onrender: ({ didRestore: s }) => {
                o(O, !0), se()({ instant: s });
              },
              onerror: (s) => {
                X(v(), s);
              }
            });
          };
          let ie = c(() => Q() ? 1 : 0), oe = c(() => Q() || e(A).length > 1 ? 1 : 0);
          be(te, {
            get enableParallax() {
              return J();
            },
            get overflowAmount() {
              return H();
            },
            get mediaObjectFit() {
              return G();
            },
            get mediaInitialOpacity() {
              return e(ie);
            },
            get mediaInitialScalar() {
              return e(oe);
            },
            children: re,
            $$slots: { default: !0 }
          });
        }
        h(() => B(u, 1, D(I()))), M(i, u);
      }), h(() => B(r, 1, D(I()))), M(t, r);
    };
    pe(Y, (t) => {
      e(k) || t(Z);
    });
  }
  M(V, j), fe();
}
export {
  We as default
};
