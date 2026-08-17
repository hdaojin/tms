/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { FilePondInputElement as A } from "../FilePondInput/index.js";
import { FilePondEntryListElement as E, getDefaultEntryAnimationOriginMap as P, getDefaultEntryAnimationProps as L, getDefaultSpringOptions as C } from "../FilePondEntryList/index.js";
import { FilePondFrameElement as D } from "../FilePondFrame/index.js";
import { FilePondDropIndicatorElement as S } from "../FilePondDropIndicator/index.js";
import { FilePondSourceListElement as w } from "../FilePondSourceList/index.js";
import { hasDefinedTag as x, defineCustomElements as F, defineCustomElement as k, setStringAttribute as O, setBooleanAttribute as d, h as a, addListener as l, dispatchCustomEvent as m } from "../../utils/dom.js";
import { isBrowser as _, isBoolean as f, isString as p } from "../../utils/test.js";
import { assets as g } from "../../assets/index.js";
import I from "./index.css.js";
import { createFilePondEntryList as R } from "../../templates/entry-list/index.js";
import { createFilePondSourceList as j } from "../../templates/source-list/index.js";
import { createFilePondExtensionSet as V } from "./createFilePondExtensionSet.js";
let u;
const N = ["auto", "never", "always"];
function b(s, t = /* @__PURE__ */ new Set([])) {
  return (e) => {
    if (!e || t.has(e))
      return;
    const i = Array.from(t.add(e)).join(",");
    s.setAttribute("exportparts", i.replace(/ /g, ","));
  };
}
class $ extends A {
  // Child components
  #t = {};
  /** Holds reference to attribution link element */
  #e;
  /** Holds references to event subscriptions so we can more easily unsub */
  #o = [];
  /** Stores the current animation mode */
  #i = "auto";
  /** Stores the current nodrop state */
  #r = !1;
  /** Stores the current attribution state */
  #s = !1;
  /** Calls a function for each component */
  #n(t) {
    Object.values(this.#t).forEach(t);
  }
  /** Wraps `createFilePondExtensionSet` so we always set the default extension set */
  set extensions(t) {
    super.extensions = V(t);
  }
  /** Automatically passes value to child elements, for usage see `FilePondSvelteComponentElement` */
  set springDefaults(t) {
    this.#n((e) => e.springDefaults = t);
  }
  /** Returns the current animation mode */
  get animations() {
    return this.#i;
  }
  /** Setting to toggle animations, automatically passes `animations` setting to child elements, for usage see `FilePondSvelteComponentElement` */
  set animations(t) {
    N.includes(t) && (this.#i = t, this.#a());
  }
  #a() {
    this.isConnected && (this.isConnected && this.getAttribute("animations") !== this.#i && O(
      this,
      "animations",
      this.#i === "auto" ? void 0 : this.#i
    ), this.#n((t) => t.animations = this.#i));
  }
  /** Set to `true` to remove drop area */
  set noDrop(t) {
    f(t) && (this.#r = t, this.#c());
  }
  /** Returns current nodrop state */
  get noDrop() {
    return this.#r;
  }
  #c() {
    this.isConnected && (d(this, "nodrop", this.#r), this.#r ? this.#t.dropIndicator.remove() : this._root.prepend(this.#t.dropIndicator), Object.assign(this, {
      EntryListView: {
        drop: !this.#r
      }
    }));
  }
  /**
      A programmatic way to toggle the attribution link on/off.
  
      When set to `true` this property automatically adds the `noattribution` attribute to the `<file-pond>` element.
  
      ```js
      const element = document.querySelector('file-pond');
      element.noAttribution = true;
      ```
      */
  set noAttribution(t) {
    f(t) && (this.#s = t, this.#l());
  }
  /** Returns current noattribution state */
  get noAttribution() {
    return this.#s;
  }
  #l() {
    this.isConnected && (d(this, "noattribution", this.noAttribution), this.#s ? this.#e.remove() : this._root.append(this.#e));
  }
  /** Sets the locale on parent */
  set locale(t) {
    super.locale = t, this.#n((e) => e.locale = t);
  }
  static get observedAttributes() {
    return [...super.observedAttributes, "animations", "noattribution", "nodrop"];
  }
  attributeChangedCallback(t, e, i) {
    if (t === "noattribution") {
      this.noAttribution = p(i);
      return;
    }
    if (t === "nodrop") {
      this.noDrop = p(i);
      return;
    }
    if (t === "nobrowse" && p(i)) {
      this.noDrop = p(i), super.attributeChangedCallback(t, e, i);
      return;
    }
    t === "animations" && (this.animations = i), super.attributeChangedCallback(t, e, i);
  }
  constructor() {
    super({
      styles: [I]
    });
    const t = a("file-pond-entry-list", {
      part: "entry-list-element"
    }), e = a("file-pond-source-list", {
      part: "source-list-element"
    }), i = a("file-pond-source-description", {
      part: "source-description-element"
    }), c = a("file-pond-frame", {
      part: "frame-element"
    }), h = a("file-pond-drop-indicator", {
      part: "drop-indicator-element"
    });
    this.#t = {
      entryList: t,
      sourceList: e,
      frame: c,
      dropIndicator: h,
      sourceDescription: i
    };
    const r = b(
      t,
      /* @__PURE__ */ new Set(["dragging", "virtualized", "selected", "checked"])
    ), n = b(
      e,
      /* @__PURE__ */ new Set([
        "dialog",
        "dialog-header",
        "dialog-title",
        "dialog-form",
        "dialog-content",
        "dialog-footer"
      ])
    ), y = u?.EntryListView?.template || R();
    Object.assign(this, {
      // add items view
      extensions: this.extensions,
      // default spring values
      springDefaults: C(),
      // default animation state
      animations: "auto",
      // show progress indicator for data transfers
      DataTransferLoader: {
        perceivedPerformance: !0
      },
      // renders the description label
      SourceDescriptionView: {
        element: this.#t.sourceDescription
      },
      // set up source list view extension
      SourceListView: {
        element: this.#t.sourceList,
        // the nodes to render
        template: j(),
        // assets to use
        assets: g,
        // sync source entry list parts
        beforeRenderNode(o) {
          return n(o.props?.part || o.attrs?.part), o;
        }
      },
      // set up entry list view extension
      EntryListView: {
        // the element that the item list will be appended to
        element: this.#t.entryList,
        // the root element to use for dragging and dropping components, defaults to the list itself
        dropRoot: this.#t.frame,
        // assets to use
        assets: g,
        // the nodes to render
        template: y,
        // called before rendering a node, allows dynamically modifying a node or adding nodes
        beforeRenderNode(o) {
          return r(o.props?.part || o.attrs?.part), o;
        },
        // animations
        entryAnimationProps: L(),
        entryAnimationOriginMap: P()
      }
    }), this.#e = B({
      caption: "Powered by FilePond"
    }), Object.assign(this, u);
  }
  connectedCallback() {
    super.connectedCallback();
    const { entryList: t, sourceList: e, sourceDescription: i, frame: c, dropIndicator: h } = this.#t;
    this._root.prepend(c, i), this._root.append(e, t), this.#c(), this.#l(), this.#a(), this.#o.push(
      // did compute target rect
      l(c, "rectcompute", (r) => {
        if (!r.detail)
          return;
        const n = r.detail;
        m(this, "rectcompute", { detail: n });
      }),
      // did update visual rect
      l(c, "rectchange", (r) => {
        if (!r.detail)
          return;
        const n = r.detail;
        this._root.style.setProperty("--width", n.width), this._root.style.setProperty("--height", n.height), m(this, "rectchange", { detail: n });
      }),
      // link up placeholder position with drop indicator
      l(t, "placeholderchange", (r) => {
        h.indicatorRect = r.detail;
      }),
      // these two listeners toggle the dragging attribute to the file-pond element, we do this so we can move the file-pond element that is being interacted with to the front, so the dragged item also renders on top. Additionally they prevent interaction with slot content and attribution link while dragging
      l(t, "entrydragstart", () => {
        d(this, "dragging", !0), this._slot.inert = !0, this.#e.inert = !0;
      }),
      l(t, "entrydragend", () => {
        d(this, "dragging", !1), this._slot.inert = !1, this.#e.inert = !1;
      })
    );
  }
  /** Called each time the element is removed from the document. */
  disconnectedCallback() {
    super.disconnectedCallback(), this.#n((t) => t.remove()), this.#e.remove(), this.#o.forEach((t) => t()), this.#o = [];
  }
}
function B(s) {
  const { caption: t = "" } = s || {};
  return a("a", {
    textContent: t,
    href: "https://filepond.com",
    target: "_tab",
    rel: "noopener noreferrer nofollow",
    part: "attribution-link",
    // don't want to interfere with keyboard navigation
    tabindex: "-1",
    // don't want to annoy assistive tech with this attribution link
    "aria-hidden": "true"
  });
}
function X(s) {
  if (!_())
    return [];
  const t = "file-pond";
  return u = s, x(t) || (F({
    [`${t}-source-list`]: w,
    [`${t}-entry-list`]: E,
    [`${t}-frame`]: D,
    [`${t}-drop-indicator`]: S
  }), k(t, $)), Array.from(document.querySelectorAll(t));
}
export {
  $ as FilePondElement,
  X as defineFilePond
};
