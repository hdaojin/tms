/*!
* FilePond v5.0.0-beta.78
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createTest as s, isSafari as n } from "./test.js";
const l = s(
  () => "requestFullscreen" in document.documentElement
), d = s(() => "requestVideoFrameCallback" in document.createElement("video")), c = s(
  // @ts-ignore
  () => !!globalThis.scheduler?.yield
), a = s(() => "CommandEvent" in window), r = s(() => {
  const e = document.createElement("div");
  e.style.transition = "display 1s allow-discrete", document.body.append(e);
  const t = getComputedStyle(e);
  t.display, e.style.display = "none";
  const o = t.display !== "none";
  return e.remove(), o;
}), u = s(() => r() && !n());
export {
  u as supportsDialogCloseTransition,
  r as supportsDisplayTransition,
  a as supportsInvokerCommands,
  l as supportsRequestFullscreen,
  d as supportsRequestVideoFrameCallback,
  c as supportsYieldScheduler
};
