/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createExtensionManager as k } from "../../core/extensionManager.js";
import { isString as g, isBoolean as V, isNumber as I, isFile as w, isObject as z } from "../../utils/test.js";
import { arrayRemoveFalsy as E } from "../../utils/array.js";
import { toCamelCase as C } from "../../utils/string.js";
import { setBooleanAttribute as a, setStringAttribute as o, getAttribute as h, getFileSizeAttributeValue as u, createStyleSheet as P, h as d, getAttributeFromElements as b, addListener as L, dispatchCustomEvent as c } from "../../utils/dom.js";
import { stringReplaceVariables as m, statusToLabel as O, statusCodeToLocaleKey as q } from "../common/string.js";
import { debounce as p } from "../../utils/debounce.js";
import { Status as T } from "../../common/status.js";
import { HTMLElementSafe as B } from "../../common/ssr.js";
import D from "./index.css.js";
import { createFilePondEntryTree as R } from "./createFilePondEntryTree.js";
import { FileInputSource as M } from "../../extensions/file-input-source.js";
import { ValueCallbackStore as j } from "../../extensions/value-callback-store.js";
const x = [
  // customError
  "customError",
  // if accept is mismatched
  "typeMismatch",
  // some min range exceeded
  "rangeUnderflow",
  // some max range exceeded
  "rangeOverflow",
  // if is required and value is missing
  "valueMissing"
];
function _(n) {
  const { nodeType: t, nodeValue: e, nodeName: i } = n;
  return t === 3 ? (e || "").trim().length > 0 : t === 1 && i === "INPUT" ? !/hidden|file/.test(n.type) : !0;
}
function N(n) {
  return n.some((t) => Object.values(t.extensionState ?? {}).some(({ status: e }) => e ? I(e.progress) : !1));
}
function U(n) {
  return n.some((t) => Object.values(t.extensionState ?? {}).some(({ status: e }) => e ? e.type === "error" : !1));
}
function $(n, t) {
  const e = Array.isArray(t) ? t : [t], i = new FormData();
  for (const s of e) {
    if (w(s)) {
      i.append(n, s, s.name);
      continue;
    }
    i.append(n, z(s) ? JSON.stringify(s) : `${s}`);
  }
  return i;
}
const G = ["required", "name", "id"], S = ["disabled", "accept", "capture", "webkitdirectory"], F = ["disabled", "required", "webkitdirectory"];
class nt extends B {
  /** FilePond element shadowRoot */
  #l;
  /** Div element that wraps styleable children */
  #n;
  /** FilePond element slot */
  #o;
  /** This Has a reference to the element form internals */
  #i;
  /** Source input */
  #s;
  /** Browse button, we use a separate browse button so the input doesn't show the "file chosen" or "file name", we'll render our own file list. */
  #u = "[data-browse]";
  /** No browse state */
  #c = !1;
  /** FilePond extension manager reference */
  #e;
  /** Holds the current extension set after someone has called .extensions = [...] */
  #d;
  /** FilePond core instance reference */
  #t;
  /** Locale object reference */
  #r = void 0;
  /** Holds Names of extensions we've currently set up proxies for */
  #p = [];
  /**
   * Holds default entries as set by developer to .entries, we use this so we can reset to initial
   * state when reset is clicked
   */
  #f = null;
  /** Holds references to event subscriptions so we can more easily unsub */
  #h = [];
  //#region getters and setters for <file-pond> custom element attributes
  /** Returns a reference to the shadow root element */
  get _root() {
    return this.#n;
  }
  /** Returns a reference to the slot element */
  get _slot() {
    return this.#o;
  }
  /** Attributes being observed for changes */
  static get observedAttributes() {
    return [
      "value",
      "readonly",
      "required",
      "webkitdirectory",
      "capture",
      "accept",
      "nobrowse",
      //
      // apart from 'max-files' these are convenience attributes for validation extensions
      //
      "min-files",
      "max-files",
      "min-size",
      "max-size",
      "min-list-size",
      "max-list-size"
      //
      // the root doesn't have the 'multiple' attribute it uses 'min-files' / 'max-files'
      //
      //
      // changes to 'disabled' attribute are handled by `formDisabledCallback`
      //
    ];
  }
  /** Called when attributes are changed, added, removed, or replaced */
  attributeChangedCallback(t, e, i) {
    if (t === "value") {
      this.value = `${i}`;
      return;
    }
    this.#E(t, i), this.#b(t, i), this.#x(t, i);
  }
  /** Syncs attribute to internal element state */
  #E(t, e) {
    if (t === "nobrowse") {
      a(this.#s, "data-readonly", g(e));
      return;
    }
    if (t === "max-files") {
      const i = parseInt(e, 10);
      this.#t.entries.length > i && (this.#t.entries = this.#t.entries.toSpliced(i)), this.#s.multiple = i !== 1, this.#a(), this.checkValidity();
      return;
    }
  }
  /** Syncs file-pond interaction attributes (attributes that impact file system file selection UX) to source input attributes */
  #b(t, e) {
    if (S.includes(t)) {
      if (F.includes(t)) {
        a(this.#s, t, e === !0 || e === "");
        return;
      }
      o(this.#s, t, e);
    }
  }
  /** Looks up the extension(s) linked to this attribute and assigns the matched props */
  #x(t, e) {
    const i = C(t);
    e = F.includes(t) && e === "" ? !0 : e, this.#e.propagateExtensionProperty(i, e);
  }
  /** Disable the field and sets the disabled attribute */
  set disabled(t) {
    a(this, "disabled", t);
  }
  /** Gets the field disabled state */
  get disabled() {
    return !!h(this, "disabled");
  }
  /** Set the field webkitdirectory state */
  set webkitdirectory(t) {
    a(this, "webkitdirectory", t);
  }
  /** Gets the field webkitdirectory state */
  get webkitdirectory() {
    return !!h(this, "webkitdirectory");
  }
  /** Toggle the field multiple state */
  set multiple(t) {
    t && this.maxFiles === 1 && (this.maxFiles = 1 / 0), !t && this.maxFiles !== 1 && (this.maxFiles = 1);
  }
  /** Gets the field multiple state */
  get multiple() {
    return this.maxFiles !== 1;
  }
  /**
   * Set field as readonly. Only for situations where FilePond has initial files and those files
   * should be posted. The `readonly` attribute isn't supported on a file input element as it
   * cannot have an initial value.
   */
  set readOnly(t) {
    a(this, "readonly", t);
  }
  /** Gets the field readonly state */
  get readOnly() {
    return !!h(this, "readonly");
  }
  /** Set field as required */
  set required(t) {
    a(this, "required", t);
  }
  /** Gets the field required state */
  get required() {
    return !!h(this, "required");
  }
  /** Accepted files setter https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/accept */
  set accept(t) {
    o(this, "accept", t);
  }
  /** Returns the current value of accept */
  get accept() {
    return h(this, "accept");
  }
  /** Toggle browse button */
  set noBrowse(t) {
    V(t) && (this.#c = !!t, this.#y());
  }
  /** Returns the current browse button state */
  get noBrowse() {
    return this.#c;
  }
  #y() {
    this.isConnected && a(this, "nobrowse", this.#c);
  }
  /** Min file size setter, accepts a number of bytes or a natural filesize string like 1MB */
  set minSize(t) {
    o(this, "min-size", t);
  }
  /** Returns the currently set min file size */
  get minSize() {
    return u(this, "min-size");
  }
  /** Max file size setter, accepts a number of bytes or a natural filesize string like 1MB */
  set maxSize(t) {
    o(this, "max-size", t);
  }
  /** Returns the currently set max file size */
  get maxSize() {
    return u(this, "max-size");
  }
  /** Min total file size setter, accepts a number of bytes or a natural filesize string like 1MB */
  set minListSize(t) {
    o(this, "min-list-size", t);
  }
  /** Returns the currently set min total file size */
  get minListSize() {
    return u(this, "min-list-size");
  }
  /** Max total file size setter, accepts a number of bytes or a natural filesize string like 1MB */
  set maxListSize(t) {
    o(this, "max-list-size", t);
  }
  /** Returns the currently set max total file size */
  get maxListSize() {
    return u(this, "max-list-size");
  }
  /** Min total entries setter, an integer, defaults to `0` */
  set minFiles(t) {
    o(this, "min-files", t);
  }
  /** Returns the currently set min total entries */
  get minFiles() {
    return parseInt(this.getAttribute("min-files") ?? "0", 10);
  }
  /** Max total entries setter, an integer, defaults to `Infinity` */
  set maxFiles(t) {
    t === 1 / 0 ? this.removeAttribute("max-files") : o(this, "max-files", t);
  }
  /** Returns the currently set max total entries */
  get maxFiles() {
    const t = this.getAttribute("max-files");
    return t ? parseInt(t, 10) : 1 / 0;
  }
  //#endregion
  //#region Element properties
  /** Set the current entries */
  set entries(t) {
    this.#t.entries = t;
  }
  /** Returns a `structuredClone` of the current entries array */
  get currentEntries() {
    return this.#t.entries;
  }
  /** Sets the locale */
  set locale(t) {
    this.#r = t, this.#e.propagateExtensionProperty("locale", t), this.#a(), this.checkValidity();
  }
  /** Returns the current locale object, so it's easier to extend or override */
  get locale() {
    return this.#r;
  }
  /** Sets custom extensions to load */
  set extensions(t) {
    this.#d = t, this.#e.extensions = t;
  }
  /** Update worker url */
  set workersURL(t) {
    this.#e.propagateExtensionProperty("workersURL", t);
  }
  //#endregion
  //#region Element methods
  /** Opens the system file browser */
  browse() {
    this.noBrowse || (this.querySelector(this.#u)?.focus({
      preventScroll: !0
    }), this.#s.click());
  }
  /** Subscribe to internal entryTree events */
  on = (t, e) => this.#t.on(t, e);
  /** Add one or more entries to the end of the list or insert them at a specific index */
  insertEntries(t, e) {
    return this.#t.insertEntries(t, e);
  }
  /** Find entries in the entry tree */
  findEntries(...t) {
    return this.#t.findEntries(...t);
  }
  /** Find entries in the entry tree */
  removeEntries(...t) {
    return this.#t.removeEntries(...t);
  }
  /** Sorts the entry tree using the passed sorting function */
  sortEntries(t) {
    this.#t.sortEntries(t);
  }
  /** Update an entry */
  updateEntry(t, ...e) {
    this.#t.updateEntry(t, ...e);
  }
  /** Update an entry state */
  updateEntryState(t, ...e) {
    this.#t.updateEntry(t, {
      state: e
    });
  }
  /** Move entry from current location to new index */
  moveEntry(t, e) {
    return this.#t.moveEntry(t, e);
  }
  /** Replace entry with one or more entries */
  replaceEntry(t, ...e) {
    return this.#t.replaceEntry(t, ...e);
  }
  //#endregion
  /** Called when the custom element is created */
  constructor(t) {
    super();
    const { styles: e = [] } = t || {};
    this.#l = this.attachShadow({ mode: "open", delegatesFocus: !0 }), this.#l.adoptedStyleSheets = [D, ...e].map(P), this.#n = d("div"), this.#n.tabIndex = -1, this.#l.append(this.#n), this.#o = d("slot"), this.#o.addEventListener("slotchange", () => {
      this.#g(), a(
        this.#o,
        "data-has-children",
        !!this.#o.assignedNodes().filter(_).length
      );
    }), this.#n.append(this.#o), this.#s = d("input", {
      type: "file",
      "aria-hidden": !0,
      hidden: !0,
      multiple: !0,
      tabIndex: -1
    }), this.#n.prepend(this.#s), this.#i = this.attachInternals(), this.#t = R({
      // handles one or multiple files state
      beforeInsertEntries: (i, s) => this.maxFiles < 1 / 0 && s.length + i.length > this.maxFiles ? i.toSpliced(this.maxFiles - s.length) : i
    }), this.#e = k({ entryTree: this.#t }), this.#e.on("setExtensions", ({ extensionNames: i }) => {
      this.#p.filter((s) => !i.includes(s)).forEach((s) => {
        delete this[s];
      }), i.forEach((s) => {
        Object.defineProperty(this, s, {
          // getter / setter
          set(f) {
            this.#e.setExtensionProperties(s, f);
          },
          get() {
            return this.#e.getExtensionProperties(s);
          },
          // so we can delete this proxy later
          configurable: !0
        });
      }), this.#p = i, this.checkValidity();
    }), this.#e.on("updateExtensionState", () => {
      this.checkValidity();
    }), this.#t.on(
      "updateEntries",
      p(() => {
        this.locale && this.#a();
      })
    ), this.#e.extensions = [M, j];
  }
  // This updates the aria-description attribute.
  // It describes the element similar to how other input elements are described(label_name: field type, role, validation state)
  #a() {
    if (!this.isConnected)
      return;
    const t = this.#t.entries.length, e = {
      multiple: `${this.multiple}`,
      name: t === 1 ? this.#t.entries[0].name || "Untitled" : null,
      count: t,
      maxFiles: this.maxFiles,
      maxFilesUnit: "unitFiles"
    };
    if (!this.#r)
      return;
    const i = t === 0 ? "ariaNoEntries" : t === 1 ? "ariaSingleEntry" : "ariaMultipleEntries", s = [
      // field status
      m(this.#r[i], e, this.#r),
      // current validation message
      this.validationMessage,
      // is required?
      this.required ? this.#r.ariaRequired : !1
    ];
    this.setAttribute("aria-description", E(s).join(", "));
  }
  #g() {
    const t = this.#o.assignedElements({ flatten: !0 }).filter((i) => i.matches('input[type="file"]')), e = [...G, ...S];
    for (const i of e) {
      const s = b(i, ...t, this);
      s !== void 0 && (this[i] = s);
    }
    t.length && (this.multiple = !!b("multiple", ...t)), t.forEach((i) => i.remove());
  }
  /** Called each time the element is added to the document */
  connectedCallback() {
    this.#g(), this.#y(), this.#a(), this.#d && (this.#e.extensions = this.#d);
    const t = (e) => {
      this.#i.setFormValue(
        e.length > 0 ? $(this.name ?? "filepond", e) : null
      ), this.checkValidity(), c(this, "change");
    };
    this.#e.setExtensionProperties("FileInputSource", {
      element: this.#s,
      resetFilesOnAdd: !0
    }), this.#e.setExtensionProperties("ValueCallbackStore", {
      required: this.required,
      onChange: t
    }), this.#S(), this.#h.push(
      L(this, "click", (e) => {
        e.composedPath()[0].closest(this.#u) && (e.stopPropagation(), e.preventDefault(), this.browse());
      }),
      // fire update events
      this.#t.on("updateEntries", () => {
        this.#e.propagateExtensionProperty(
          "preventAddEntries",
          this.currentEntries.length === this.maxFiles
        ), c(this, "entrieschange", { detail: this.currentEntries });
      })
    ), c(this, "connected");
  }
  /** Called each time the element is removed from the document. */
  disconnectedCallback() {
    this.#e.destroy(), this.#h.forEach((t) => t()), this.#h = [], c(this, "disconnected");
  }
  //#region Form integration and validation
  /** This makes the element associable with its parent form */
  static formAssociated = !0;
  /** Sets the current field name */
  set name(t) {
    o(this, "name", t);
  }
  /** Returns the current field name */
  get name() {
    return this.getAttribute("name") ?? void 0;
  }
  /** Proxy for Element internals `form` getter */
  get form() {
    return this.#i.form ?? void 0;
  }
  /**
   * Sets/Updates the value of the the entry manager
   *
   * Will also remember this value for when form is reset
   */
  set value(t) {
    let e = [];
    g(t) && (e = t.split(",").map((i) => i.trim()).map((i) => ({
      src: i
    }))), this.#f = e, this.entries = e;
  }
  /** Proxy for `entries` getter */
  get value() {
    return this.currentEntries;
  }
  /** Sets up the field for validation */
  #S() {
    this.#h.push(
      this.#t.on(
        "updateEntries",
        p(() => this.checkValidity())
      ),
      this.#e.on(
        "updateExtensionState",
        p(() => this.checkValidity())
      )
    ), this.checkValidity();
  }
  /** Validates the current state of the field */
  checkValidity() {
    const { validationInvalidBusy: t = "", validationInvalidState: e = "" } = this.#r || {};
    if (N(this.currentEntries)) {
      if (this.#i.validity.customError === !0)
        return;
      this.#m({ customError: !0 }, m(t));
      return;
    }
    const i = {
      // add generic item state, for when an extension doesn't set a generic state on the extension manager (this allows for more extension specific error messages like "not all items have been stored")
      ...U(this.currentEntries) ? {
        FilePondItemValidator: {
          status: {
            type: "error",
            code: "VALIDATION_INVALID_ENTRIES",
            meta: null,
            values: []
          }
        }
      } : {},
      // overwrite with specific extension states
      ...this.#e.getState()
    }, s = {};
    for (const { status: r } of Object.values(i)) {
      if (!r || r.type !== T.Error)
        continue;
      const { flag: l = "customError" } = r?.meta ?? {}, y = this.#r ? O(
        {
          ...r,
          values: {
            // error state values
            ...r.values,
            // append input state
            multiple: this.multiple
          }
        },
        this.#r
      ) : q(r.code);
      s[l] = y || m(e) || "";
    }
    if (Object.keys(s).length === 0)
      return this.#m();
    const v = E(x.map((r) => s[r])).at(
      0
    ), A = x.reduce(
      (r, l) => (r[l] = !!s[l], r),
      {}
    );
    return this.#m(A, v);
  }
  /** Sets the validity state on the element internals. Returns `true` if valid, `false` if invalid */
  #m(t, e) {
    let i = !0;
    return t ? (this.#i.setValidity(t, e || "error", this.#n), i = !1) : this.#i.setValidity({}), this.#a(), i;
  }
  /** Proxy for element internals `reportValidity()` method */
  reportValidity() {
    this.#i.reportValidity();
  }
  /** Proxy for element internals `validity` getter */
  get validity() {
    return this.#i.validity;
  }
  /** Proxy for element internals `validationMessage` getter */
  get validationMessage() {
    return this.#i.validationMessage;
  }
  /** Called when element or parent element (for example a `<fieldset>`) is set to disabled */
  formDisabledCallback(t) {
    this.#e.propagateExtensionProperty("disabled", t), this.#s.disabled = t, [...this.querySelectorAll(this.#u)].forEach(
      (e) => e.disabled = t
    );
  }
  /**
   * Called when user resets form. Resets field to initial state. The initial state is either
   * empty or set to what the developer has set to the `.entries` prop. This tries to mimic the
   * workings of `setAttribute` on default form fields.
   *
   * https://developer.mozilla.org/en-US/docs/Web/API/HTMLFormElement/reset
   */
  formResetCallback() {
    this.entries = this.#f ?? [];
  }
  /** Called when user returns to form with back button */
  formStateRestoreCallback(t, e) {
  }
  //#endregion
}
export {
  nt as FilePondInputElement
};
