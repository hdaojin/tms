/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { FilePondSvelteComponentElement as t } from "../FilePondSvelteComponent/index-svelte.js";
import r from "./index-svelte.js";
import { registerShadowRoot as s } from "../common/extendStyles.js";
import i from "../styles/defaults.css.js";
import e from "./index.css.js";
import { setBooleanAttribute as l } from "../../utils/dom.js";
const n = [
  "disabled",
  "assets",
  "locale",
  "template",
  "propResourceMap",
  "animations",
  "springDefaults",
  "beforeRenderNode",
  "sources",
  "propResourceMap"
];
class P extends t {
  constructor() {
    super(r, {
      styles: [e],
      properties: n
    }), s(this._root, i + e);
  }
  connectedCallback() {
    super.connectedCallback(), this.addListener("sourceschange", (o) => {
      l(this, "empty", o.detail === 0);
    });
  }
}
export {
  n as COMPONENT_PROPS,
  P as FilePondSourceListElement
};
