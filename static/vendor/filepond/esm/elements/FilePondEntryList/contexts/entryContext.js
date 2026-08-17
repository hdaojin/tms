/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { setContext as e, getContext as o } from "../../../vendor/svelte/src/internal/client/context.js";
const t = {};
function x(n) {
  e(t, n);
}
function C() {
  return o(t);
}
export {
  C as getEntryContext,
  x as setEntryContext
};
