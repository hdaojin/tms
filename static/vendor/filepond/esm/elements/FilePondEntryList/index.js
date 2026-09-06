/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { FilePondSvelteComponentElement as e } from "../FilePondSvelteComponent/index-svelte.js";
import { setBooleanAttribute as n } from "../../utils/dom.js";
import { registerShadowRoot as s } from "../common/extendStyles.js";
import i from "./index-svelte.js";
import a from "../styles/defaults.css.js";
import r from "./index.css.js";
const o = [
  "disabled",
  "assets",
  "locale",
  "template",
  "propResourceMap",
  "drag",
  "dragGrabTimeout",
  "dragDetachMargin",
  "dragSafetyMargin",
  "drop",
  "dropRoot",
  "dropPadding",
  "animations",
  "entryAnimationProps",
  "entryAnimationOriginMap",
  "entryAnimationStaggerInterval",
  "springDefaults",
  "byteUnits",
  "beforeRenderNode"
], p = [
  // update routes from model
  "onSetEntries",
  "onInsertEntry",
  "onRemoveEntry",
  // registered callbacks
  "setSetEntriesCallback",
  "setInsertEntriesCallback",
  "setRemoveEntriesCallback",
  "setUpdateEntryCallback",
  "setGetEntryExtensionStateCallback",
  "setSetEntryExtensionStateCallback",
  "setPushTaskCallback",
  "setAbortTaskCallback"
], l = ["entrydrag", "entrydragstart", "entrydragend", "placeholderchange"];
class E extends e {
  constructor() {
    super(i, {
      properties: o,
      methods: p,
      events: l
    }), s(this._root, a + r);
  }
  connectedCallback() {
    super.connectedCallback(), this.addListener("entrieschange", (t) => {
      n(this, "empty", t.detail === 0);
    });
  }
}
function O() {
  return {
    clipboard: "drop",
    drop: "rise",
    input: "slide",
    remote: "rise"
  };
}
function u() {
  return {
    stiffness: 0.1,
    damping: 0.495,
    precision: 1e-3
  };
}
function b() {
  return {
    // spring state when dragging outside list
    dissolve: {
      scale: 1,
      opacity: 0.5
    },
    // spring state while dragging
    lift: {
      translationSpringOptions: { stiffness: 0.1, damping: 0.4 },
      scaleSpringOptions: { stiffness: 0.1, damping: 0.35 },
      scale: 1.025,
      opacity: 1
    },
    release: {
      scale: 1,
      opacity: 1
    },
    // spring target when removed
    fall: {
      scaleSpringOptions: { stiffness: 0.1, damping: 0.9 },
      scale: 0.95,
      opacitySpringOptions: { stiffness: 0.25, damping: 0.95 },
      opacity: 0
    },
    // fade in from smaller size
    rise: {
      translationFrom: { x: 0, y: -5 },
      scaleSpringOptions: { stiffness: 0.1, damping: 0.31 },
      scaleFrom: 0.95,
      scale: 1,
      opacitySpringOptions: { stiffness: 0.1, damping: 0.6 },
      opacityFrom: 0,
      opacity: 1
    },
    // fade in from bigger size
    drop: {
      scaleSpringOptions: { stiffness: 0.1, damping: 0.31 },
      scaleFrom: 1.05,
      scale: 1,
      opacitySpringOptions: { stiffness: 0.1, damping: 0.6 },
      opacityFrom: 0,
      opacity: 1
    },
    // animating in from the top
    slide: {
      translationSpringOptions: { stiffness: 0.05, damping: 0.5 },
      translationFrom: {
        x: 0,
        y: -15
      },
      scaleSpringOptions: { stiffness: 0.1, damping: 0.31 },
      scaleFrom: 0.95,
      scale: 1,
      opacitySpringOptions: { stiffness: 0.1, damping: 0.6 },
      opacityFrom: 0,
      opacity: 1
    }
  };
}
export {
  o as COMPONENT_PROPS,
  E as FilePondEntryListElement,
  O as getDefaultEntryAnimationOriginMap,
  b as getDefaultEntryAnimationProps,
  u as getDefaultSpringOptions
};
