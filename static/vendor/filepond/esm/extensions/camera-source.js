/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createSourceExtension as f } from "./common/createSourceExtension.js";
import "../elements/components/CameraInput/index.js";
import p from "../elements/components/CameraInput/index-svelte.js";
const o = "2-digit", C = new Intl.DateTimeFormat("sv-SE", {
  year: "numeric",
  month: o,
  day: o,
  hour: o,
  minute: o,
  second: o,
  hour12: !1
}), I = f({
  name: "CameraSource",
  props: {
    // icons and labels
    sourceLabel: "camera",
    sourceIcon: "camera",
    sourceIconError: "cameraOff",
    sourceType: "select",
    // use date time by default
    filename: () => C.format(/* @__PURE__ */ new Date()).replace(" ", "_").replaceAll(":", "-")
  },
  factory: ({ props: a }, { setExtensionSourceState: t }) => {
    function n(e) {
      const { mediaConstraints: r } = a;
      e.requestCameraAccess(r).then(m).catch(c);
    }
    function m() {
      const { sourceIcon: e } = a;
      t({
        icon: e,
        title: void 0
      });
    }
    function c(e) {
      const { sourceIconError: r } = a;
      t({
        icon: r,
        title: e.message
      });
    }
    function s(e) {
      return [
        {
          key: "camera-input",
          component: p,
          props: ({ filename: r }, u) => {
            const { capture: i, reset: l } = u.resources?.locale || {};
            return {
              ...e,
              filename: r,
              labelReset: l,
              labelCapture: i,
              onmount: n,
              onerror: c
            };
          }
        }
      ];
    }
    return {
      createSourceTemplate: s
    };
  }
});
export {
  I as CameraSource
};
