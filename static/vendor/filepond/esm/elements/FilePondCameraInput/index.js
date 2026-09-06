/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { FilePondSvelteComponentElement as i } from "../FilePondSvelteComponent/index-svelte.js";
import s from "./index-svelte.js";
import { registerShadowRoot as r } from "../common/extendStyles.js";
import a from "../styles/defaults.css.js";
import e from "./index.css.js";
import { setStringAttribute as l, setBooleanAttribute as o, getAttribute as n } from "../../utils/dom.js";
class g extends i {
  /** This makes the element associable with its parent form */
  static formAssociated = !0;
  /** Internal value */
  #e;
  /** This Has a reference to the element form internals */
  #t;
  /** Sets the current field name */
  set name(t) {
    l(this, "name", t);
  }
  /** Returns the current field name */
  get name() {
    return this.getAttribute("name") ?? void 0;
  }
  /** Gets value */
  get value() {
    return this.#e;
  }
  /** Sets value */
  set value(t) {
    this.#e = t;
  }
  /** Proxy for element internals `validity` getter */
  get validity() {
    return this.#t.validity;
  }
  /** Proxy for element internals `validationMessage` getter */
  get validationMessage() {
    return this.#t.validationMessage;
  }
  /** Set field as required */
  set required(t) {
    o(this, "required", t);
  }
  /** Gets the field required state */
  get required() {
    return !!n(this, "required");
  }
  constructor() {
    super(s, {
      styles: [e],
      properties: ["filename", "oncapture", "onreset"],
      methods: ["requestCameraAccess"]
    }), this.#t = this.attachInternals(), r(this._root, a + e);
  }
  connectedCallback() {
    super.connectedCallback(), this.oncapture = (t) => {
      this.#e = t, this.#t.setFormValue(t), this.checkValidity();
    }, this.onreset = () => {
      this.#e = void 0, this.#t.setFormValue(null), this.checkValidity();
    }, this.tabIndex = -1, this.checkValidity();
  }
  checkValidity() {
    if (this.required && !this.#e) {
      this.#t.setValidity(
        {
          valueMissing: !0
        },
        // TODO: translate
        "Please fill in this field"
      );
      return;
    }
    this.#t.setValidity({});
  }
  /**
   * Called when user resets form. Resets field to initial state.
   *
   * https://developer.mozilla.org/en-US/docs/Web/API/HTMLFormElement/reset
   */
  formResetCallback() {
    this.#e = void 0, this.#t.setFormValue(null);
  }
}
export {
  g as CameraInputElement
};
