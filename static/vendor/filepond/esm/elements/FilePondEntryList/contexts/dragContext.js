/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { getContext as n, setContext as o } from "../../../vendor/svelte/src/internal/client/context.js";
const t = {};
function x(e) {
  o(t, e);
}
function g() {
  return n(t);
}
export {
  g as getDragContext,
  x as setDragContext
};
