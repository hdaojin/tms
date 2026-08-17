/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createTest as t } from "./test.js";
const r = t(
  () => "requestFullscreen" in document.documentElement
), d = t(() => "requestVideoFrameCallback" in document.createElement("video")), c = t(() => "CommandEvent" in window), i = t(() => {
  const e = document.createElement("div");
  e.style.transition = "display 1s allow-discrete", document.body.append(e);
  const n = getComputedStyle(e);
  n.display, e.style.display = "none";
  const o = n.display !== "none";
  return e.remove(), o;
});
export {
  i as supportsDisplayTransition,
  c as supportsInvokerCommands,
  r as supportsRequestFullscreen,
  d as supportsRequestVideoFrameCallback
};
