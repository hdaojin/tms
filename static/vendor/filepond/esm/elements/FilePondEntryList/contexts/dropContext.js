/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { getContext as e, setContext as n } from "../../../vendor/svelte/src/internal/client/context.js";
const t = {};
function x(o) {
  n(t, o);
}
function p() {
  return e(t);
}
export {
  p as getDropContext,
  x as setDropContext
};
