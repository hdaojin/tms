/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { h as t } from "../utils/dom.js";
import { createSourceExtension as n } from "./common/createSourceExtension.js";
const p = n({
  name: "URLInputSource",
  props: {
    sourceIcon: "link"
  },
  factory: ({ props: r }) => {
    function e() {
      const { placeholder: o } = r;
      return t("input", { type: "url", placeholder: o });
    }
    return {
      createSourceElement: e
    };
  }
});
export {
  p as URLInputSource
};
