/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { getContext as n, setContext as o } from "../../../vendor/svelte/src/internal/client/context.js";
const t = {};
function r(e) {
  o(t, e);
}
function x() {
  return n(t);
}
export {
  x as getAppContext,
  r as setAppContext
};
