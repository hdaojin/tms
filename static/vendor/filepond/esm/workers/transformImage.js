/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
function r(e, t, m, c) {
  const l = t ? [e, ...Object.values(t), m] : [e, m];
  createImageBitmap.apply(null, l).then((a) => {
    c(null, a, [a]);
  }).catch((a) => {
    c(a);
  });
}
r.fileName = "transformImage";
export {
  r as transformImage
};
