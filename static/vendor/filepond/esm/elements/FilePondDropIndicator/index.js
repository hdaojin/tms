/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { FilePondSvelteComponentElement as i } from "../FilePondSvelteComponent/index-svelte.js";
import n from "./index-svelte.js";
import o from "./index.css.js";
import r from "../components/ElementPane/index.css.js";
import { setBooleanAttribute as t } from "../../utils/dom.js";
class m extends i {
  constructor() {
    super(n, { styles: [o, r] });
  }
  connectedCallback() {
    super.connectedCallback(), this.addListener("indicatorenter", () => {
      t(this, "indicating", !0);
    }), this.addListener("indicatorleave", () => {
      t(this, "indicating", !1);
    });
  }
  /** Updates the current location of the drop indicator */
  set indicatorRect(e) {
    this._app && this._app.setIndicatorRect(e);
  }
}
export {
  m as FilePondDropIndicatorElement
};
