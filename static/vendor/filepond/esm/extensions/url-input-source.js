/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import "../common/ssr.js";
import "../elements/FilePondSourceList/index-svelte.js";
import { createSourceExtension as n } from "./common/createSourceExtension.js";
const a = n({
  name: "URLInputSource",
  props: {
    sourceIcon: "link"
  },
  factory: ({ props: r }) => {
    function t(e) {
      const { placeholder: o } = r;
      return [
        {
          key: "url-input",
          tag: "input",
          attrs: {
            ...e,
            type: "url",
            placeholder: o
          }
        }
      ];
    }
    return {
      createSourceTemplate: t
    };
  }
});
export {
  a as URLInputSource
};
