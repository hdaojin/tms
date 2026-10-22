/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { isBrowser as y } from "../../utils/test.js";
import { createStyleSheet as r } from "../../utils/dom.js";
const h = [], n = [];
function S() {
  for (const { shadowRoot: t, styleSheet: o, key: s } of n)
    t.adoptedStyleSheets.push(
      // my styles
      o,
      ...h.filter((e) => !e.rootKeys.length || e.rootKeys.includes(s)).map((e) => e.styleSheet)
    );
}
function c(t, ...o) {
  y() && (h.push({ styleSheet: r(t), rootKeys: o }), S());
}
function d(t, o, s) {
  const e = r(s);
  n.push({ key: o, shadowRoot: t, styleSheet: e }), S();
}
export {
  c as extendShadowRootStyles,
  d as registerShadowRoot
};
