/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import "../../../common/ssr.js";
import "../../FilePondSourceList/index-svelte.js";
import { extendShadowRootStyles as t } from "../../common/extendStyles.js";
import e from "./index.css.js";
let o = 0;
function p() {
  return o++;
}
t(e);
export {
  p as getSkeletonInstanceIndex
};
