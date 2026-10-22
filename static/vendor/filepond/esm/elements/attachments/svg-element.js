/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
const c = /* @__PURE__ */ new Map();
function o({ svg: t }) {
  let e = c.get(t);
  if (!e) {
    const n = document.createElement("div");
    n.innerHTML = t, e = n.children[0], c.set(t, e);
  }
  return (n) => {
    const r = e.cloneNode(!0);
    return n.append(r), () => {
      r?.remove();
    };
  };
}
export {
  o as svgElement
};
