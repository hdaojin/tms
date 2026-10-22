/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { FilePondSvelteComponentElement as o } from "../FilePondSvelteComponent/index-svelte.js";
import t from "./index-svelte.js";
import { registerShadowRoot as r } from "../common/extendStyles.js";
import { setBooleanAttribute as s } from "../../utils/dom.js";
import i from "../styles/defaults.css.js";
import l from "./index.css.js";
const p = [
  "disabled",
  "assets",
  "template",
  "propResourceMap",
  "beforeRenderNode",
  "sources",
  "propResourceMap"
];
class P extends o {
  constructor() {
    super(t, {
      styles: [i],
      properties: p
    }), r(this._root, "source-list", l);
  }
  connectedCallback() {
    super.connectedCallback(), this.addListener("sourceschange", (e) => {
      s(this, "empty", e.detail === 0);
    });
  }
}
export {
  p as COMPONENT_PROPS,
  P as FilePondSourceListElement
};
