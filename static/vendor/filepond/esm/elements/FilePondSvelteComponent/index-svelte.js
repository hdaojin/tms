/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as o } from "../../vendor/svelte/src/internal/client/runtime.js";
import { proxy as a } from "../../vendor/svelte/src/internal/client/proxy.js";
import { state as p } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { mount as l, unmount as m } from "../../vendor/svelte/src/internal/client/render.js";
import { HTMLElementSafe as f } from "../../common/ssr.js";
import { createStyleSheet as b, addListener as h, dispatchCustomEvent as v } from "../../utils/dom.js";
import { arrayRemoveFalsy as g } from "../../utils/array.js";
const E = ["locale", "reducedMotionPreference", "springOptions"], C = ["reduced-motion"];
class A extends f {
  #r;
  #t;
  #e;
  #i = [];
  #o;
  #s = [];
  #n;
  /** Protected props */
  get _app() {
    return this.#t;
  }
  get _root() {
    return this.#r;
  }
  /** Attributes being observed for changes */
  static get observedAttributes() {
    return C;
  }
  attributeChangedCallback(t, r, e) {
    if (t === "reduced-motion") {
      o(this.#e).reducedMotionPreference = e;
      return;
    }
    o(this.#e)[t] = e;
  }
  constructor(t, r) {
    super();
    const { styles: e = [], properties: c = [], methods: d = [], events: u = [] } = r || {};
    this.#n = t, this.#r = this.attachShadow({ mode: "open" }), this.#r.adoptedStyleSheets = g(e).map(b), this.#e = p(a({
      // this cannot be a $state.raw because then the Svelte component doesn't respond to prop updates
      root: this,
      springOptions: void 0,
      locale: void 0,
      reducedMotionPreference: this.getAttribute("reduced-motion") || "auto"
    })), [
      .../* @__PURE__ */ new Set([...E, ...c])
    ].forEach((s) => {
      Object.defineProperty(this, s, {
        get() {
          return o(this.#e)[s];
        },
        set(i) {
          o(this.#e)[s] = i;
        }
      });
    }), Object.defineProperties(this, d.reduce(
      (s, i) => (s[i] = {
        value: function(...n) {
          if (!this.#t) {
            this.#i.push([i, n]);
            return;
          }
          return this.#t[i](...n);
        },
        writable: !1,
        configurable: !1
      }, s),
      {}
    )), this.#o = u;
  }
  addListener(t, r) {
    if (!this._root.children[0])
      return;
    const e = h(this._root.children[0], t, r);
    return this.#s.push(e), e;
  }
  connectedCallback() {
    this.#t || (this.#t = l(this.#n, { target: this.#r, props: o(this.#e) }), this.#o.forEach((t) => {
      const r = h(this._root.children[0], t, (e) => {
        v(this, t, { bubbles: !0, detail: e.detail });
      });
      this.#s.push(r);
    }), this.#i.forEach(([t, r]) => {
      this.#t[t](...r);
    }), this.#i.length = 0, this.dispatchEvent(new CustomEvent("connected")));
  }
  disconnectedCallback() {
    this.#s.forEach((t) => t()), this.#s.length = 0, this.#t && (m(this.#t), this.#t = null), this.dispatchEvent(new CustomEvent("disconnected"));
  }
}
export {
  E as COMPONENT_PROPS,
  A as FilePondSvelteComponentElement
};
