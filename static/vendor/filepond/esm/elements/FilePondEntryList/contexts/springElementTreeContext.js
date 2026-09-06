/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { getContext as t, setContext as o } from "../../../vendor/svelte/src/internal/client/context.js";
const e = {};
function i(n) {
  o(e, n);
}
function x() {
  return t(e);
}
function g() {
  return t(e) !== void 0;
}
export {
  x as getSpringElementTreeContext,
  g as hasSpringElementTreeContext,
  i as setSpringElementTreeContext
};
