/*!
* FilePond v5.0.0-beta.77
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as xt } from "../../vendor/svelte/src/index-client.js";
import { user_effect as T, template_effect as It } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as Rt, pop as At } from "../../vendor/svelte/src/internal/client/context.js";
import { get as t, untrack as b, tick as Ct } from "../../vendor/svelte/src/internal/client/runtime.js";
import { $window as kt, child as Tt, sibling as Mt, only_child as wt } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { set as n, state as c } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { set_text as Ot } from "../../vendor/svelte/src/internal/client/render.js";
import { user_derived as l } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as Pt, append as _t } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { attach as Z } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { delegate as Nt, event as Ft, delegated as xe } from "../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { proxy as Gt } from "../../vendor/svelte/src/internal/client/proxy.js";
import { bind_this as Kt } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { bind_window_size as Ie } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/window.js";
import { prop as s } from "../../vendor/svelte/src/internal/client/reactivity/props.js";
import { dragArea as Bt } from "../attachments/drag-area.js";
import { dropArea as Lt } from "../attachments/drop-area.js";
import { arrayMove as Re, arrayInsertAtIndex as Ae } from "../../utils/array.js";
import { ORIGIN as P, vectorCreate as $, vectorEqual as Ut, vectorSubtract as zt, vectorAdd as jt } from "../../utils/vector.js";
import { rectPad as ee, rectContainsPoint as te, rectFromBounds as Ce, rectCenter as Vt } from "../../utils/rect.js";
import { passthrough as qt, noop as _ } from "../../utils/placeholder.js";
import { measurable as ke } from "../attachments/measurable.js";
import { dispatchCustomEvent as N, setBooleanAttribute as Ht } from "../../utils/dom.js";
import { setAppContext as Wt } from "./contexts/appContext.js";
import { setDragContext as Xt } from "./contexts/dragContext.js";
import { setDropContext as Jt } from "./contexts/dropContext.js";
import { getUniqueId as Te } from "../../utils/string.js";
import { setSpringElementTreeContext as Qt } from "./contexts/springElementTreeContext.js";
import { sizeFromRect as Yt } from "../../utils/size.js";
import { isNumber as Me } from "../../utils/test.js";
import Zt from "../components/NodeList/index-svelte.js";
import { hasOwnProp as $t } from "../../utils/object.js";
import { getDragTargetIndex as er, getDropTargetIndex as tr } from "../common/dragDrop.js";
import { clamp as rr } from "../../utils/math.js";
import { isActivationKeyboardEvent as we, isArrowKeyboardEvent as nr, getDirectionFromKeyboardEvent as ir, isTabKeyboardEvent as or, isCancelKeyboardEvent as ar } from "../../utils/keyboard.js";
import { stringReplaceVariables as sr } from "../common/string.js";
import { createMotionStateObserver as dr, shouldReduceMotion as ur } from "../common/motionState-svelte.js";
var cr = Pt('<div class="root" role="group"><!> <div role="status" aria-live="polite" class="implicit"> </div></div>');
function Xr(Oe, i) {
  Rt(i, !0);
  let W = s(i, "disabled", 3, !1), X = s(i, "assets", 19, () => ({})), F = s(i, "locale", 19, () => ({})), Pe = s(i, "template", 19, () => []), re = s(i, "propResourceMap", 19, () => ({ title: "locale", label: "locale", icon: "assets" })), ne = s(i, "drag", 3, !0), _e = s(i, "dragGrabTimeout", 3, 100), Ne = s(i, "dragDetachMargin", 3, 40), ie = s(i, "dragSafetyMargin", 3, 80), oe = s(i, "drop", 3, !0), Fe = s(i, "dropRoot", 3, void 0), ae = s(i, "dropPadding", 3, 20), Ge = s(i, "entryAnimationOriginMap", 19, () => ({})), Ke = s(i, "entryAnimationProps", 19, () => ({})), se = s(i, "entryAnimationStaggerInterval", 3, 50), Be = s(i, "beforeRenderNode", 3, qt), Le = s(i, "byteUnits", 3, void 0);
  const de = dr(), z = l(() => ur(de.current, i.reducedMotionPreference)), Ue = 50;
  let g = c(void 0), ue = c(void 0), J = c(void 0), p = c([]), h = c([]), f = c({}), ce = c(0), le = c(0);
  const ze = l(() => ({
    top: 0,
    right: t(ce),
    bottom: t(le),
    left: 0
  })), o = Gt({
    setEntries: fe,
    insertEntries: _,
    removeEntries: _,
    updateEntry: _,
    setEntryExtensionState: _,
    getEntryExtensionState: () => ({}),
    pushTask: _,
    abortTask: _
  });
  function je(e) {
    o.setEntries = e;
  }
  function Ve(e) {
    o.insertEntries = e;
  }
  function qe(e) {
    o.removeEntries = e;
  }
  function He(e) {
    o.updateEntry = e;
  }
  function We(e) {
    o.getEntryExtensionState = e;
  }
  function Xe(e) {
    o.setEntryExtensionState = e;
  }
  function Je(e) {
    o.pushTask = e;
  }
  function Qe(e) {
    o.abortTask = e;
  }
  function fe(e) {
    e && n(p, e);
  }
  function Ye(e) {
    const r = Ge()[e.origin];
    r && G(e, r, { stagger: se() });
  }
  function Ze({ entry: e, index: r }) {
    r[0] !== -1 && (et(e, r[0]), G(e, "fall", {
      stagger: se(),
      oncomplete: () => {
        me(() => {
          tt(e.id);
        });
      }
    }));
  }
  function me(e) {
    setTimeout(
      () => {
        e();
      },
      0
    );
  }
  function $e(e) {
    t(m) && N(t(m), "placeholderchange", { detail: e || null });
  }
  function et(e, r) {
    n(h, [...t(h), { index: r, entry: e }]);
  }
  function tt(e) {
    n(h, t(h).filter(({ entry: r }) => r.id !== e));
  }
  const rt = l(() => Math.max(t(h).length, t(p).length));
  T(() => {
    N(t(m), "entrieschange", { detail: t(rt) });
  });
  const ge = {};
  function G(e, r, d) {
    if (!e)
      return;
    const { stagger: R, oncomplete: y, retain: w = !1 } = d ?? {};
    if (t(z)) {
      y && y();
      return;
    }
    if (t(f)[e.id]?.animation === r)
      return;
    if (Object.keys(t(f)).length > Ue) {
      y && y();
      return;
    }
    let A = !1, B = !1, C = 0;
    if (Me(R)) {
      const E = ge[r] || 0, k = Date.now();
      if (E + R > k) {
        const L = k - E;
        C = R - L;
      }
      ge[r] = k + C;
    }
    let O;
    const D = {
      entry: e,
      animation: r,
      oncancel: () => {
        A || !O || (A = !0, clearTimeout(O), b(() => {
          pe(e, r);
        }), y && y());
      },
      oncomplete: () => {
        B || (B = !0, w || b(() => {
          pe(e, r);
        }), y && y());
      }
    };
    n(f, {
      ...t(f),
      [e.id]: { ...D, delayed: C > 0 }
    }), C > 0 && (O = setTimeout(
      () => {
        n(f, {
          ...t(f),
          [e.id]: { ...D, delayed: !1 }
        });
      },
      C
    ));
  }
  function nt(e) {
    for (const r of Object.values(t(f)))
      if (e === r.animation)
        return r.entry;
    return null;
  }
  function pe(e, r) {
    t(f)[e.id]?.animation === r && (delete t(f)[e.id], n(f, { ...t(f) }));
  }
  Wt({
    get reduceMotion() {
      return t(z);
    },
    get enableDrag() {
      return ne();
    },
    get locale() {
      return F();
    },
    get assets() {
      return X();
    },
    get resources() {
      return { locale: F(), assets: X() };
    },
    get springOptions() {
      return i.springOptions;
    },
    get propResourceMap() {
      return re();
    },
    get retainedEntries() {
      return t(h);
    },
    get animatedEntries() {
      return t(f);
    },
    get entryAnimationProps() {
      return Ke();
    },
    // so others can know of the placeholder rectangle location
    updateEntryPlaceholderRect: $e,
    // copy over AppCallbacks to AppContext
    ...Object.keys(o).reduce(
      (e, r) => (e[r] = (...d) => o[r](...d), e),
      {}
    )
  });
  let j = c(void 0);
  function it(e) {
    n(j, Ce(e));
  }
  let m = c(void 0), a = c(void 0);
  const ye = l(oe), Ee = l(() => t(ye) ? Fe() ?? t(m) : void 0);
  let v = c(void 0);
  T(() => {
    if (!t(a) || ie() === 1 / 0)
      return;
    const { viewPosition: e } = t(a);
    if (!e)
      return;
    const r = ee(b(() => t(j) ?? t(g)), ie());
    te(r, e) ? t(v) && n(v, void 0) : t(v) || n(v, { remove: !0 });
  });
  let V, K, q, M = c(P);
  T(() => {
    if (!t(g)) {
      n(M, P);
      return;
    }
    if (!t(a)) {
      V = { ...t(g) }, n(M, P), q = P;
      return;
    }
    const e = V ? $(V.x - t(g).x, V.y - t(g).y) : P;
    if (K && Ut(e, K)) {
      q = P;
      return;
    }
    K && (q = zt(e, K)), K = { ...e }, me(() => {
      n(M, e);
    });
  });
  let ve = -1, u = c(void 0);
  T(() => {
    if (!t(a)) {
      n(u, void 0);
      return;
    }
    const {
      id: e,
      element: r,
      offset: d,
      translation: R,
      vector: y = $(),
      viewPosition: w = $(),
      direction: A
    } = t(a);
    if (!r && t(ye) && ae() < 1 / 0) {
      const E = ee(b(() => t(j) ?? t(g)), ae());
      if (!te(E, w)) {
        n(u, void 0);
        return;
      }
    }
    if (r && A) {
      let E;
      const L = r.closest("ul").children, U = Array.from(L).indexOf(r);
      if (A !== "none") {
        let x = U;
        A === "up" ? x-- : A === "down" && x++, x = rr(x, 0, L.length - 1), b(() => {
          o.setEntries(Re([...t(p)], U, x));
        }), E = x, b(() => {
          n(I, {
            key: "ariaDragStateSort",
            name: t(p)[x].name,
            position: x + 1,
            total: L.length
          });
        }), Ct().then(() => {
          r.isConnected && r.focus({ preventScroll: !0 });
        });
      } else
        E = U, b(() => {
          n(I, {
            key: "ariaDragStateGrab",
            name: t(p)[U].name,
            position: U + 1
          });
        });
      n(u, { id: e, index: E, element: r });
      return;
    }
    const B = !te(ee(b(() => t(j) ?? t(g)), Ne()), w), C = t(M).x !== 0 || t(M).y !== 0, Y = {
      searchBounds: t(ze),
      cacheClientRectangles: C ? 0 : 250
    }, O = jt(q, y), D = B ? ve : r ? er(r, w, O, Y) : tr(t(m), w, O, Y);
    if (r && D > -1) {
      const E = r.closest("ul"), k = Array.from(E.children).indexOf(r);
      k !== D && b(() => {
        o.setEntries(Re([...t(p)], k, D));
      });
    }
    ve = D, n(u, {
      id: e,
      index: D,
      element: r,
      offset: d,
      translation: R,
      parentTranslation: t(M),
      outside: B
    });
  });
  const ot = l(() => t(u) ? t(u).id : void 0), H = l(() => t(u) ? t(u).index : void 0), be = l(() => t(u) ? t(u).element : void 0), at = l(() => !!(t(u) && !t(be) && t(H) !== void 0));
  T(() => {
    if (!t(be)) {
      const r = nt("lift");
      r && G(r, "release");
      return;
    }
    if (!Me(t(H)))
      return;
    const e = t(p)[t(H)];
    if (t(v)?.remove) {
      G(e, "dissolve", { retain: !0 });
      return;
    }
    G(e, "lift", { retain: !0 });
  });
  function st(e) {
    N(t(m), "entrydragstart"), n(a, e);
  }
  function dt(e) {
  }
  function he(e) {
    N(t(m), "entrydrag"), n(a, e);
  }
  function ut(e) {
    n(a, e);
  }
  function ct(e) {
    n(a, void 0);
  }
  function lt() {
    N(t(m), "entrydragend"), n(a, void 0);
  }
  function ft(e) {
    return !!t(u);
  }
  function Se(e) {
    if (N(t(m), "entrydragend"), !t(u))
      return;
    const { index: r } = t(u);
    if (n(a, void 0), $t(e, "dataTransfer")) {
      const d = e.dataTransfer;
      if (!d.types.includes("Files"))
        return;
      o.insertEntries({ id: Te(), src: d, origin: "drop" }, r);
      return;
    }
    if (t(v)?.remove) {
      const d = t(p)[r].id;
      n(v, { ...t(v), id: d }), o.removeEntries(d);
      return;
    }
  }
  const mt = l(() => {
    let e = t(p);
    if (t(at) && (e = Ae(
      // array to insert the placeholder into
      [...t(p)],
      t(
        // where to add placeholder
        H
      ),
      // item placeholder when dropping a new file
      { id: t(ot) }
    )), !t(h).length)
      return e;
    let r = [...e];
    return t(h).forEach(({ entry: d, index: R }) => {
      r = Ae(r, R, d);
    }), r;
  });
  Xt({
    get current() {
      return t(u);
    }
  }), Jt({
    get current() {
      return t(v);
    }
  }), T(() => {
    if (!t(Ee))
      return;
    const e = ke({ onmeasure: it })(t(Ee));
    return () => {
      e();
    };
  }), T(() => {
    Ht(t(m), "data-disabled", W());
  });
  const gt = {
    insertEntries: (e, r) => o.insertEntries(e, r),
    removeEntries: (...e) => o.removeEntries(...e),
    updateEntry: (e, ...r) => o.updateEntry(e, ...r),
    updateEntryState: (e, r) => {
      o.updateEntry(e, { state: r });
    }
  };
  function pt(e) {
    n(g, Ce(e), !0), n(ue, Vt(t(g)), !0), n(J, Yt(t(g)), !0);
  }
  Qt({
    parent: null,
    get isReady() {
      return !0;
    },
    get currentRect() {
      return t(g);
    },
    get currentRectCenter() {
      return t(ue);
    },
    get targetSize() {
      return t(J);
    },
    get currentSize() {
      return t(J);
    },
    get currentScale() {
      return 1;
    },
    childSpringCount: 0,
    childSpringReadyCount: 0
  });
  function yt(e) {
    t(a) && e.preventDefault();
  }
  function Q() {
    return t(a) ? (n(a, void 0), n(I, {
      key: "ariaDragStateDrop",
      name: t(I).name,
      position: t(I).position
    }), !0) : !1;
  }
  function Et(e) {
    if (e.target.dataset.draggable === "" && we(e) && e.preventDefault(), t(a) && nr(e)) {
      n(a, {
        ...t(a),
        direction: ir(e)
      }), e.preventDefault();
      return;
    }
  }
  function vt(e) {
    if (or(e)) {
      Q();
      return;
    }
    if (we(e)) {
      const r = e.target;
      if (!(r?.dataset.draggable === "") || (e.preventDefault(), Q()))
        return;
      n(a, { id: Te(), element: r, direction: "none" });
      return;
    }
    if (ar(e) && Q()) {
      e.preventDefault();
      return;
    }
  }
  let I = c(void 0);
  const bt = l(() => {
    if (!t(I))
      return "";
    const { key: e, ...r } = t(I);
    return sr(F()[e], r, F());
  });
  xt(() => {
    de.destroy();
  });
  var ht = {
    setSetEntriesCallback: je,
    setInsertEntriesCallback: Ve,
    setRemoveEntriesCallback: qe,
    setUpdateEntryCallback: He,
    setGetEntryExtensionStateCallback: We,
    setSetEntryExtensionStateCallback: Xe,
    setPushTaskCallback: Je,
    setAbortTaskCallback: Qe,
    onSetEntries: fe,
    onInsertEntry: Ye,
    onRemoveEntry: Ze
  }, S = cr();
  Ft("contextmenu", kt, yt);
  var De = Tt(S);
  {
    let e = l(() => ({ locale: F(), assets: X() })), r = l(() => ({ entries: t(mt) })), d = l(() => ({
      ...gt,
      byteUnits: Le(),
      reduceMotion: t(z),
      springOptions: i.springOptions
    }));
    Zt(De, {
      get reduceMotion() {
        return t(z);
      },
      get springOptions() {
        return i.springOptions;
      },
      get resources() {
        return t(e);
      },
      get propResourceMap() {
        return re();
      },
      get nodes() {
        return Pe();
      },
      get data() {
        return t(r);
      },
      get context() {
        return t(d);
      },
      get beforeRenderNode() {
        return Be();
      }
    });
  }
  var St = Mt(De, 2), Dt = wt(St, !0);
  return Kt(S, (e) => n(m, e), () => t(m)), Z(S, () => ke({ onmeasure: pt })), Z(S, () => Bt({
    disabled: !ne() || W(),
    itemSelector: "[data-draggable]",
    grabTimeout: _e(),
    onitemgrab: st,
    onitemgrabcancel: dt,
    onitemdrag: he,
    onitemdrop: Se
  })), Z(S, () => Lt({
    disabled: !oe() || W(),
    willAcceptDrop: ft,
    onitemdrag: he,
    onitemdragin: ut,
    onitemdragout: ct,
    onitemdropcancel: lt,
    onitemdrop: Se
  })), It(() => Ot(Dt, t(bt))), Ie("innerWidth", (e) => n(ce, e, !0)), Ie("innerHeight", (e) => n(le, e, !0)), xe("keydown", S, Et), xe("keyup", S, vt), _t(Oe, S), At(ht);
}
Nt(["keydown", "keyup"]);
export {
  Xr as default
};
