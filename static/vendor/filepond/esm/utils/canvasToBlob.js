/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
function l(t, o) {
  const { type: e, quality: r } = o || {};
  return new Promise((u, i) => {
    t.toBlob(
      (n) => {
        if (n === null)
          return i();
        u(n);
      },
      e,
      r
    );
  });
}
export {
  l as canvasToBlob
};
