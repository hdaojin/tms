/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { roundPrecision as i } from "../../utils/math.js";
import { FilePondSvelteComponentElement as s } from "../FilePondSvelteComponent/index-svelte.js";
import a from "./index-svelte.js";
import r from "../components/ElementPane/index.css.js";
import m from "./index.css.js";
class C extends s {
  constructor() {
    super(a, {
      styles: [m, r]
    });
  }
  connectedCallback() {
    super.connectedCallback();
    let e, n;
    this._app.setComputeRectCallback((t) => {
      t && this.dispatchEvent(new CustomEvent("rectcompute", { detail: t }));
    }), this._app.setUpdateRectCallback((t) => {
      if (!t)
        return;
      const l = t ? i(t.width, 1) : null, o = t ? i(t.height, 1) : null;
      l === n && o === e || (n = l, e = o, this.dispatchEvent(new CustomEvent("rectchange", { detail: t })));
    });
  }
}
export {
  C as FilePondFrameElement
};
