/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as o } from "../../vendor/svelte/src/internal/client/runtime.js";
import { proxy as p } from "../../vendor/svelte/src/internal/client/proxy.js";
import { state as d } from "../../vendor/svelte/src/internal/client/reactivity/sources.js";
import { mount as l, unmount as m } from "../../vendor/svelte/src/internal/client/render.js";
import { HTMLElementSafe as f } from "../../common/ssr.js";
import { createStyleSheet as b, addListener as h, dispatchCustomEvent as v } from "../../utils/dom.js";
import { arrayRemoveFalsy as g } from "../../utils/array.js";
const E = ["animations"], C = ["animations", "springDefaults"];
class L extends f {
  #s;
  #t;
  #e;
  #i = [];
  #o;
  #r = [];
  #n;
  /** Protected props */
  get _app() {
    return this.#t;
  }
  get _root() {
    return this.#s;
  }
  /** Attributes being observed for changes */
  static get observedAttributes() {
    return E;
  }
  attributeChangedCallback(t, e, s) {
    Object.assign(o(this.#e), { [t]: s });
  }
  constructor(t, e) {
    super();
    const { styles: s = [], properties: a = [], methods: u = [], events: c = [] } = e || {};
    this.#n = t, this.#s = this.attachShadow({ mode: "open" }), this.#s.adoptedStyleSheets = g(s).map(b), this.#e = d(p({
      root: this,
      springDefaults: void 0,
      animations: this.getAttribute("animations") || void 0
    })), [
      .../* @__PURE__ */ new Set([...C, ...a])
    ].forEach((i) => {
      Object.defineProperty(this, i, {
        get() {
          return o(this.#e)[i];
        },
        set(r) {
          o(this.#e)[i] = r;
        }
      });
    }), Object.defineProperties(this, u.reduce(
      (i, r) => (i[r] = {
        value: function(...n) {
          if (!this.#t) {
            this.#i.push([r, n]);
            return;
          }
          return this.#t[r](...n);
        },
        writable: !1,
        configurable: !1
      }, i),
      {}
    )), this.#o = c;
  }
  addListener(t, e) {
    if (!this._root.children[0])
      return;
    const s = h(this._root.children[0], t, e);
    return this.#r.push(s), s;
  }
  connectedCallback() {
    this.#t = l(this.#n, { target: this.#s, props: o(this.#e) }), this.#o.forEach((t) => {
      const e = h(this._root.children[0], t, (s) => {
        v(this, t, { bubbles: !0, detail: s.detail });
      });
      this.#r.push(e);
    }), this.#i.forEach(([t, e]) => {
      this.#t[t](...e);
    }), this.#i.length = 0, this.dispatchEvent(new CustomEvent("connected"));
  }
  disconnectedCallback() {
    this.#r.forEach((t) => t()), m(this.#t), this.#t = null, this.dispatchEvent(new CustomEvent("disconnected"));
  }
}
export {
  L as FilePondSvelteComponentElement
};
