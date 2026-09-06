/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { onDestroy as At } from "../../vendor/svelte/src/index-client.js";
import { user_effect as I, template_effect as It } from "../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { push as Rt, pop as Ct } from "../../vendor/svelte/src/internal/client/context.js";
import { get as t, untrack as h } from "../../vendor/svelte/src/internal/client/runtime.js";
import { $window as Tt, child as xe, sibling as kt } from "../../vendor/svelte/src/internal/client/dom/operations.js";
import { set as n, state as u } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { set_text as wt } from "../../vendor/svelte/src/internal/client/render.js";
import { user_derived as l } from "../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { from_html as Mt, append as Pt } from "../../vendor/svelte/src/internal/client/dom/template.js";
import { attach as $ } from "../../vendor/svelte/src/internal/client/dom/elements/attachments.js";
import { delegate as Ot, event as _t, delegated as Ae } from "../../vendor/svelte/src/internal/client/dom/elements/events.js";
import { proxy as Nt } from "../../vendor/svelte/src/internal/client/proxy.js";
import { bind_this as Ft } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { bind_window_size as Ie } from "../../vendor/svelte/src/internal/client/dom/elements/bindings/window.js";
import { prop as s } from "../../vendor/svelte/src/internal/client/reactivity/props.js";
import { dragArea as Gt } from "../attachments/drag-area.js";
import { dropArea as Kt } from "../attachments/drop-area.js";
import { arrayMove as Re, arrayInsertAtIndex as Ce } from "../../utils/array.js";
import { ORIGIN as O, vectorCreate as ee, vectorEqual as Bt, vectorSubtract as Lt, vectorAdd as Ut } from "../../utils/vector.js";
import { rectPad as te, rectContainsPoint as re, rectFromBounds as Te, rectCenter as zt } from "../../utils/rect.js";
import { passthrough as jt, noop as _ } from "../../utils/placeholder.js";
import { measurable as ke } from "../attachments/measurable.js";
import { dispatchCustomEvent as N, setBooleanAttribute as Vt } from "../../utils/dom.js";
import { createAnimationModeObserver as qt } from "../common/animationPreference-svelte.js";
import { setAppContext as Ht } from "./contexts/appContext.js";
import { setDragContext as Wt } from "./contexts/dragContext.js";
import { setDropContext as Xt } from "./contexts/dropContext.js";
import { getUniqueId as we } from "../../utils/string.js";
import { setSpringElementTreeContext as Jt } from "./contexts/springElementTreeContext.js";
import { sizeFromRect as Qt } from "../../utils/size.js";
import { isNumber as Me } from "../../utils/test.js";
import Yt from "../components/NodeList/index-svelte.js";
import { hasOwnProp as Zt } from "../../utils/object.js";
import { getDragTargetIndex as $t, getDropTargetIndex as er } from "../common/dragDrop.js";
import { clamp as tr } from "../../utils/math.js";
import { isActivationKeyboardEvent as Pe, isArrowKeyboardEvent as rr, getDirectionFromKeyboardEvent as nr, isTabKeyboardEvent as ir, isCancelKeyboardEvent as or } from "../../utils/keyboard.js";
import { stringReplaceVariables as ar } from "../common/string.js";
var sr = Mt('<div class="root" role="group"><!> <div role="status" aria-live="polite" class="implicit"> </div></div>');
function qr(Oe, i) {
  Rt(i, !0);
  let W = s(i, "disabled", 3, !1), X = s(i, "assets", 19, () => ({})), F = s(i, "locale", 19, () => ({})), _e = s(i, "template", 19, () => []), ne = s(i, "propResourceMap", 19, () => ({ title: "locale", label: "locale", icon: "assets" })), ie = s(i, "drag", 3, !0), Ne = s(i, "dragGrabTimeout", 3, 100), Fe = s(i, "dragDetachMargin", 3, 40), oe = s(i, "dragSafetyMargin", 3, 80), ae = s(i, "drop", 3, !0), Ge = s(i, "dropRoot", 3, void 0), se = s(i, "dropPadding", 3, 20), Ke = s(i, "animations", 3, "auto"), Be = s(i, "entryAnimationOriginMap", 19, () => ({})), Le = s(i, "entryAnimationProps", 19, () => ({})), de = s(i, "entryAnimationStaggerInterval", 3, 50), Ue = s(i, "beforeRenderNode", 3, jt), ze = s(i, "byteUnits", 3, void 0);
  const J = qt(), z = l(() => J.current);
  I(() => {
    J.setPreference(Ke());
  });
  const je = 50;
  let g = u(void 0), ue = u(void 0), Q = u(void 0), p = u([]), D = u([]), f = u({}), ce = u(0), le = u(0);
  const Ve = l(() => ({
    top: 0,
    right: t(ce),
    bottom: t(le),
    left: 0
  })), o = Nt({
    setEntries: fe,
    insertEntries: _,
    removeEntries: _,
    updateEntry: _,
    setEntryExtensionState: _,
    getEntryExtensionState: () => ({}),
    pushTask: _,
    abortTask: _
  });
  function qe(e) {
    o.setEntries = e;
  }
  function He(e) {
    o.insertEntries = e;
  }
  function We(e) {
    o.removeEntries = e;
  }
  function Xe(e) {
    o.updateEntry = e;
  }
  function Je(e) {
    o.getEntryExtensionState = e;
  }
  function Qe(e) {
    o.setEntryExtensionState = e;
  }
  function Ye(e) {
    o.pushTask = e;
  }
  function Ze(e) {
    o.abortTask = e;
  }
  function fe(e) {
    e && n(p, e);
  }
  function $e(e) {
    const r = Be()[e.origin];
    r && G(e, r, { stagger: de() });
  }
  function et({ entry: e, index: r }) {
    r[0] !== -1 && (rt(e, r[0]), G(e, "fall", {
      stagger: de(),
      oncomplete: () => {
        me(() => {
          nt(e.id);
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
  function tt(e) {
    t(m) && N(t(m), "placeholderchange", { detail: e || null });
  }
  function rt(e, r) {
    n(D, [...t(D), { index: r, entry: e }]);
  }
  function nt(e) {
    n(D, t(D).filter(({ entry: r }) => r.id !== e));
  }
  const it = l(() => Math.max(t(D).length, t(p).length));
  I(() => {
    N(t(m), "entrieschange", { detail: t(it) });
  });
  const ge = {};
  function G(e, r, d) {
    if (!e)
      return;
    const { stagger: v, oncomplete: y, retain: M = !1 } = d ?? {};
    if (!t(z)) {
      y && y();
      return;
    }
    if (t(f)[e.id]?.animation === r)
      return;
    if (Object.keys(t(f)).length > je) {
      y && y();
      return;
    }
    let C = !1, B = !1, T = 0;
    if (Me(v)) {
      const E = ge[r] || 0, k = Date.now();
      if (E + v > k) {
        const L = k - E;
        T = v - L;
      }
      ge[r] = k + T;
    }
    let P;
    const x = {
      entry: e,
      animation: r,
      oncancel: () => {
        C || !P || (C = !0, clearTimeout(P), h(() => {
          pe(e, r);
        }), y && y());
      },
      oncomplete: () => {
        B || (B = !0, M || h(() => {
          pe(e, r);
        }), y && y());
      }
    };
    n(f, {
      ...t(f),
      [e.id]: { ...x, delayed: T > 0 }
    }), T > 0 && (P = setTimeout(
      () => {
        n(f, {
          ...t(f),
          [e.id]: { ...x, delayed: !1 }
        });
      },
      T
    ));
  }
  function ot(e) {
    for (const r of Object.values(t(f)))
      if (e === r.animation)
        return r.entry;
    return null;
  }
  function pe(e, r) {
    t(f)[e.id]?.animation === r && (delete t(f)[e.id], n(f, { ...t(f) }));
  }
  Ht({
    get enableAnimations() {
      return t(z);
    },
    get enableDrag() {
      return ie();
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
    get springDefaults() {
      return i.springDefaults;
    },
    get propResourceMap() {
      return ne();
    },
    get retainedEntries() {
      return t(D);
    },
    get animatedEntries() {
      return t(f);
    },
    get entryAnimationProps() {
      return Le();
    },
    // so others can know of the placeholder rectangle location
    updateEntryPlaceholderRect: tt,
    // copy over AppCallbacks to AppContext
    ...Object.keys(o).reduce(
      (e, r) => (e[r] = (...d) => o[r](...d), e),
      {}
    )
  });
  let j = u(void 0);
  function at(e) {
    n(j, Te(e));
  }
  let m = u(void 0), a = u(void 0);
  const ye = l(ae), Ee = l(() => t(ye) ? Ge() ?? t(m) : void 0);
  let b = u(void 0);
  I(() => {
    if (!t(a) || oe() === 1 / 0)
      return;
    const { viewPosition: e } = t(a);
    if (!e)
      return;
    const r = te(h(() => t(j) ?? t(g)), oe());
    re(r, e) ? t(b) && n(b, void 0) : t(b) || n(b, { remove: !0 });
  });
  let V, K, q, w = u(O);
  I(() => {
    if (!t(g)) {
      n(w, O);
      return;
    }
    if (!t(a)) {
      V = { ...t(g) }, n(w, O), q = O;
      return;
    }
    const e = V ? ee(V.x - t(g).x, V.y - t(g).y) : O;
    if (K && Bt(e, K)) {
      q = O;
      return;
    }
    K && (q = Lt(e, K)), K = { ...e }, me(() => {
      n(w, e);
    });
  });
  let be = -1, c = u(void 0);
  I(() => {
    if (!t(a)) {
      n(c, void 0);
      return;
    }
    const {
      id: e,
      element: r,
      offset: d,
      translation: v,
      vector: y = ee(),
      viewPosition: M = ee(),
      direction: C
    } = t(a);
    if (!r && t(ye) && se() < 1 / 0) {
      const E = te(h(() => t(j) ?? t(g)), se());
      if (!re(E, M)) {
        n(c, void 0);
        return;
      }
    }
    if (r && C) {
      let E;
      const L = r.closest("ul").children, U = Array.from(L).indexOf(r);
      if (C !== "none") {
        let A = U;
        C === "up" ? A-- : C === "down" && A++, A = tr(A, 0, L.length - 1), h(() => {
          o.setEntries(Re([...t(p)], U, A));
        }), E = A, h(() => {
          n(R, {
            key: "ariaDragStateSort",
            name: t(p)[A].name,
            position: A + 1,
            total: L.length
          });
        });
      } else
        E = U, h(() => {
          n(R, {
            key: "ariaDragStateGrab",
            name: t(p)[U].name,
            position: U + 1
          });
        });
      n(c, { id: e, index: E, element: r });
      return;
    }
    const B = !re(te(h(() => t(j) ?? t(g)), Fe()), M), T = t(w).x !== 0 || t(w).y !== 0, Z = {
      searchBounds: t(Ve),
      cacheClientRectangles: T ? 0 : 250
    }, P = Ut(q, y), x = B ? be : r ? $t(r, M, P, Z) : er(t(m), M, P, Z);
    if (r && x > -1) {
      const E = r.closest("ul"), k = Array.from(E.children).indexOf(r);
      k !== x && h(() => {
        o.setEntries(Re([...t(p)], k, x));
      });
    }
    be = x, n(c, {
      id: e,
      index: x,
      element: r,
      offset: d,
      translation: v,
      parentTranslation: t(w),
      outside: B
    });
  });
  const st = l(() => t(c) ? t(c).id : void 0), H = l(() => t(c) ? t(c).index : void 0), ve = l(() => t(c) ? t(c).element : void 0), dt = l(() => !!(t(c) && !t(ve) && t(H) !== void 0));
  I(() => {
    if (!t(ve)) {
      const r = ot("lift");
      r && G(r, "release");
      return;
    }
    if (!Me(t(H)))
      return;
    const e = t(p)[t(H)];
    if (t(b)?.remove) {
      G(e, "dissolve", { retain: !0 });
      return;
    }
    G(e, "lift", { retain: !0 });
  });
  function ut(e) {
    N(t(m), "entrydragstart"), n(a, e);
  }
  function ct(e) {
  }
  function he(e) {
    N(t(m), "entrydrag"), n(a, e);
  }
  function lt(e) {
    n(a, e);
  }
  function ft(e) {
    n(a, void 0);
  }
  function mt() {
    N(t(m), "entrydragend"), n(a, void 0);
  }
  function De(e) {
    if (N(t(m), "entrydragend"), !t(c))
      return;
    const { index: r } = t(c);
    if (n(a, void 0), Zt(e, "dataTransfer")) {
      const d = e.dataTransfer;
      if (!d.types.includes("Files"))
        return;
      o.insertEntries({ id: we(), src: d, origin: "drop" }, r);
      return;
    }
    if (t(b)?.remove) {
      const d = t(p)[r].id;
      n(b, { ...t(b), id: d }), o.removeEntries(d);
      return;
    }
  }
  const gt = l(() => {
    let e = t(p);
    if (t(dt) && (e = Ce(
      // array to insert the placeholder into
      [...t(p)],
      t(
        // where to add placeholder
        H
      ),
      // item placeholder when dropping a new file
      { id: t(st) }
    )), !t(D).length)
      return e;
    let r = [...e];
    return t(D).forEach(({ entry: d, index: v }) => {
      r = Ce(r, v, d);
    }), r;
  });
  Wt({
    get current() {
      return t(c);
    }
  }), Xt({
    get current() {
      return t(b);
    }
  }), I(() => {
    if (!t(Ee))
      return;
    const e = ke({ onmeasure: at })(t(Ee));
    return () => {
      e();
    };
  }), I(() => {
    Vt(t(m), "data-disabled", W());
  });
  const pt = l(() => ({
    insertEntries: o.insertEntries,
    removeEntries: o.removeEntries,
    updateEntry: o.updateEntry,
    updateEntryState: (e, r) => {
      o.updateEntry(e, { state: r });
    },
    resources: { locale: F(), assets: X() },
    propResourceMap: ne(),
    enableAnimations: t(z)
  }));
  function yt(e) {
    n(g, Te(e), !0), n(ue, zt(t(g)), !0), n(Q, Qt(t(g)), !0);
  }
  Jt({
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
      return t(Q);
    },
    get currentSize() {
      return t(Q);
    },
    get currentScale() {
      return 1;
    },
    childSpringCount: 0,
    childSpringReadyCount: 0
  });
  function Et(e) {
    t(a) && e.preventDefault();
  }
  function Y() {
    return t(a) ? (n(a, void 0), n(R, {
      key: "ariaDragStateDrop",
      name: t(R).name,
      position: t(R).position
    }), !0) : !1;
  }
  function bt(e) {
    if (e.target.dataset.draggable === "" && Pe(e) && e.preventDefault(), t(a) && rr(e)) {
      n(a, {
        ...t(a),
        direction: nr(e)
      }), e.preventDefault();
      return;
    }
  }
  function vt(e) {
    if (ir(e)) {
      Y();
      return;
    }
    if (Pe(e)) {
      const r = e.target;
      if (!(r?.dataset.draggable === "") || (e.preventDefault(), Y()))
        return;
      n(a, { id: we(), element: r, direction: "none" });
      return;
    }
    if (or(e) && Y()) {
      e.preventDefault();
      return;
    }
  }
  let R = u(void 0);
  const ht = l(() => {
    if (!t(R))
      return "";
    const { key: e, ...r } = t(R);
    return ar(F()[e], r, F());
  });
  At(() => {
    J.destroy();
  });
  var Dt = {
    setSetEntriesCallback: qe,
    setInsertEntriesCallback: He,
    setRemoveEntriesCallback: We,
    setUpdateEntryCallback: Xe,
    setGetEntryExtensionStateCallback: Je,
    setSetEntryExtensionStateCallback: Qe,
    setPushTaskCallback: Ye,
    setAbortTaskCallback: Ze,
    onSetEntries: fe,
    onInsertEntry: $e,
    onRemoveEntry: et
  }, S = sr();
  _t("contextmenu", Tt, Et);
  var Se = xe(S);
  {
    let e = l(() => ({ entries: t(gt) }));
    Yt(Se, {
      get nodes() {
        return _e();
      },
      get context() {
        return t(e);
      },
      get sharedContext() {
        return t(pt);
      },
      beforeRenderNode: (r, d, v) => Ue()(r, d, v),
      beforeSetProps: (r) => ({
        ...r,
        byteUnits: ze(),
        enableAnimations: t(z),
        springDefaults: i.springDefaults
      })
    });
  }
  var St = kt(Se, 2), xt = xe(St);
  return Ft(S, (e) => n(m, e), () => t(m)), $(S, () => ke({ onmeasure: yt })), $(S, () => Gt({
    disabled: !ie() || W(),
    itemSelector: "[data-draggable]",
    grabTimeout: Ne(),
    onitemgrab: ut,
    onitemgrabcancel: ct,
    onitemdrag: he,
    onitemdrop: De
  })), $(S, () => Kt({
    disabled: !ae() || W(),
    onitemdrag: he,
    onitemdragin: lt,
    onitemdragout: ft,
    onitemdropcancel: mt,
    onitemdrop: De
  })), It(() => wt(xt, t(ht))), Ie("innerWidth", (e) => n(ce, e, !0)), Ie("innerHeight", (e) => n(le, e, !0)), Ae("keydown", S, bt), Ae("keyup", S, vt), Pt(Oe, S), Ct(Dt);
}
Ot(["keydown", "keyup"]);
export {
  qr as default
};
