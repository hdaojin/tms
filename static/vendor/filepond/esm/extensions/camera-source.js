/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { defineCustomElement as d, h } from "../utils/dom.js";
import { CameraInputElement as I } from "../elements/FilePondCameraInput/index.js";
import { createSourceExtension as g } from "./common/createSourceExtension.js";
const e = "2-digit", y = new Intl.DateTimeFormat("sv-SE", {
  year: "numeric",
  month: e,
  day: e,
  hour: e,
  minute: e,
  second: e,
  hour12: !1
}), O = g({
  name: "CameraSource",
  props: {
    // icons and labels
    sourceLabel: "camera",
    sourceIcon: "camera",
    sourceIconError: "cameraOff",
    sourceType: "select",
    // use date time by default
    filename: () => y.format(/* @__PURE__ */ new Date()).replace(" ", "_").replaceAll(":", "-")
  },
  factory: ({ props: o }, { on: n, setExtensionSourceState: a }) => {
    function t() {
      return d("camera-input", I), h("camera-input");
    }
    function c(i) {
      const { sourceIcon: u, sourceIconError: s, mediaConstraints: l, filename: p } = o, r = i.querySelector("camera-input");
      r && (r.filename = p, r.requestCameraAccess(l).then(() => {
        a({
          icon: u,
          title: void 0
        });
      }).catch((f) => {
        a({
          icon: s,
          title: f.message
        });
      }));
    }
    const m = n("dialogOpened", c);
    return {
      createSourceElement: t,
      destroy() {
        m();
      }
    };
  }
});
export {
  O as CameraSource
};
