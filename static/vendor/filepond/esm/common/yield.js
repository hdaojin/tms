/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { sleep as r } from "../utils/sleep.js";
import { supportsYieldScheduler as l } from "../utils/support.js";
const c = async function() {
  return await scheduler.yield();
}, d = async function() {
  return await r(0);
}, u = l() ? c : d;
export {
  u as yieldScheduler
};
