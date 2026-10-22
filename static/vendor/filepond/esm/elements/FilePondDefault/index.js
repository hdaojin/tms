/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { FilePondInputElement as P } from "../FilePondInput/index.js";
import { FilePondEntryListElement as E, getDefaultEntryAnimationOriginMap as A, getDefaultEntryAnimationProps as L, getDefaultSpringOptions as S } from "../FilePondEntryList/index.js";
import { FilePondFrameElement as C } from "../FilePondFrame/index.js";
import { FilePondDropIndicatorElement as D } from "../FilePondDropIndicator/index.js";
import { FilePondSourceListElement as w } from "../FilePondSourceList/index.js";
import { hasDefinedTag as _, defineCustomElements as O, defineCustomElement as k, setStringAttribute as x, setBooleanAttribute as p, h as c, addListener as d, dispatchCustomEvent as f } from "../../utils/dom.js";
import { isBrowser as F, isBoolean as m, isString as l } from "../../utils/test.js";
import { assets as g } from "../../assets/index.js";
import M from "./index.css.js";
import { createFilePondEntryList as R } from "../../templates/entry-list/index.js";
import { createFilePondSourceList as I } from "../../templates/source-list/index.js";
import { createFilePondExtensionSet as T } from "./createFilePondExtensionSet.js";
let u;
function b(s, t = /* @__PURE__ */ new Set([])) {
  return (e) => {
    if (!e || t.has(e))
      return;
    const r = Array.from(t.add(e)).join(",");
    s.setAttribute("exportparts", r.replace(/ /g, ","));
  };
}
const N = [
  // macOS hidden files
  /^\.(DS_Store|Trashes|Spotlight)/,
  /^__MACOSX/,
  // Windows hidden files
  /^(desktop\.ini|Thumbs\.db)$/,
  // basic files and folders in project dirs
  /^\.(git|env|idea|vscode)/
];
class j extends P {
  // Child components
  #t = {};
  /** Holds reference to attribution link element */
  #e;
  /** Holds references to event subscriptions so we can more easily unsub */
  #n = [];
  /** Stores the current animation mode */
  #r = "auto";
  /** Stores the current nodrop state */
  #i = !1;
  /** Stores the current attribution state */
  #s = !1;
  /** Calls a function for each component */
  #o(t) {
    Object.values(this.#t).forEach(t);
  }
  /** Wraps `createFilePondExtensionSet` so we always set the default extension set */
  set extensions(t) {
    super.extensions = T(t);
  }
  /** Automatically passes value to child elements, for usage see `FilePondSvelteComponentElement` */
  set springOptions(t) {
    this.#o((e) => e.springOptions = t);
  }
  /** Returns the current animation mode */
  get reducedMotionPreference() {
    return this.#r;
  }
  /** Setting to toggle motion, automatically passes `reducedMotionPreference` setting to child elements, for usage see `FilePondSvelteComponentElement` */
  set reducedMotionPreference(t) {
    ["", "on", "off", "auto"].includes(t) && (this.#r = t === "" ? "on" : t, this.#c());
  }
  #c() {
    this.isConnected && (this.isConnected && this.getAttribute("reduced-motion") !== this.#r && x(
      this,
      "reduced-motion",
      this.#r === "auto" ? void 0 : this.#r
    ), this.#o(
      (t) => t.reducedMotionPreference = this.#r
    ));
  }
  /** Set to `true` to remove drop area */
  set noDrop(t) {
    m(t) && (this.#i = t, this.#a());
  }
  /** Returns current nodrop state */
  get noDrop() {
    return this.#i;
  }
  #a() {
    this.isConnected && (p(this, "nodrop", this.#i), this.#i ? this.#t.dropIndicator.remove() : this._root.prepend(this.#t.dropIndicator), Object.assign(this, {
      EntryListView: {
        drop: !this.#i
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
    m(t) && (this.#s = t, this.#d());
  }
  /** Returns current noattribution state */
  get noAttribution() {
    return this.#s;
  }
  #d() {
    this.isConnected && (p(this, "noattribution", this.noAttribution), this.#s ? this.#e.remove() : this._root.append(this.#e));
  }
  /** Sets the locale on parent */
  set locale(t) {
    super.locale = t, this.#o((e) => e.locale = t);
  }
  static get observedAttributes() {
    return [...super.observedAttributes, "reduced-motion", "noattribution", "nodrop"];
  }
  attributeChangedCallback(t, e, r) {
    if (t === "noattribution") {
      this.noAttribution = l(r);
      return;
    }
    if (t === "nodrop") {
      this.noDrop = l(r);
      return;
    }
    if (t === "nobrowse" && l(r)) {
      this.noDrop = l(r), super.attributeChangedCallback(t, e, r);
      return;
    }
    t === "reduced-motion" && (this.reducedMotionPreference = r), super.attributeChangedCallback(t, e, r);
  }
  constructor() {
    super({
      styles: [M]
    });
    const t = c("file-pond-entry-list", {
      part: "entry-list-element"
    }), e = c("file-pond-source-list", {
      part: "source-list-element"
    }), r = c("file-pond-source-description", {
      part: "source-description-element"
    }), a = c("file-pond-frame", {
      part: "frame-element"
    }), h = c("file-pond-drop-indicator", {
      part: "drop-indicator-element"
    });
    this.#t = {
      entryList: t,
      sourceList: e,
      frame: a,
      dropIndicator: h,
      sourceDescription: r
    };
    const i = b(
      t,
      /* @__PURE__ */ new Set(["dragging", "virtualized", "selected", "checked"])
    ), o = b(
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
      springOptions: S(),
      // default animation state
      reducedMotionPreference: "auto",
      // ignored file entry patterns
      ignoredEntryPatterns: N,
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
        template: I(),
        // assets to use
        assets: g,
        // sync source entry list parts
        beforeRenderNode(n) {
          return o(n.props?.part || n.attrs?.part), n;
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
        beforeRenderNode(n) {
          return i(n.props?.part || n.attrs?.part), n;
        },
        // entry animation
        entryAnimationProps: L(),
        entryAnimationOriginMap: A()
      }
    }), this.#e = V({
      caption: "Powered by FilePond"
    }), Object.assign(this, u);
  }
  connectedCallback() {
    super.connectedCallback();
    const { entryList: t, sourceList: e, sourceDescription: r, frame: a, dropIndicator: h } = this.#t;
    this._root.prepend(a, r), this._root.append(e, t), this.#a(), this.#d(), this.#c(), this.#n.push(
      // did compute target rect
      d(a, "rectcompute", (i) => {
        const o = i.detail;
        this._root.dataset.rect = "", f(this, "rectcompute", { detail: o });
      }),
      // did update visual rect
      d(a, "rectchange", (i) => {
        const o = i.detail;
        this._root.style.setProperty("--width", o.width), this._root.style.setProperty("--height", o.height), f(this, "rectchange", { detail: o });
      }),
      // link up placeholder position with drop indicator
      d(t, "placeholderchange", (i) => {
        h.indicatorRect = i.detail;
      }),
      // these two listeners toggle the dragging attribute to the file-pond element, we do this so we can move the file-pond element that is being interacted with to the front, so the dragged item also renders on top. Additionally they prevent interaction with slot content and attribution link while dragging
      d(t, "entrydragstart", () => {
        p(this, "dragging", !0), this._slot.inert = !0, this.#e.inert = !0;
      }),
      d(t, "entrydragend", () => {
        p(this, "dragging", !1), this._slot.inert = !1, this.#e.inert = !1;
      })
    );
  }
  /** Called each time the element is removed from the document. */
  disconnectedCallback() {
    super.disconnectedCallback(), this.#o((t) => t.remove()), this.#e.remove(), this.#n.forEach((t) => t()), this.#n = [];
  }
}
function V(s) {
  const { caption: t = "" } = s || {};
  return c("a", {
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
function U(s) {
  if (!F())
    return [];
  const t = "file-pond";
  return u = s, _(t) || (O({
    [`${t}-source-list`]: w,
    [`${t}-entry-list`]: E,
    [`${t}-frame`]: C,
    [`${t}-drop-indicator`]: D
  }), k(t, j)), Array.from(document.querySelectorAll(t));
}
export {
  j as FilePondElement,
  N as IGNORED_ENTRY_PATTERNS,
  U as defineFilePond
};
