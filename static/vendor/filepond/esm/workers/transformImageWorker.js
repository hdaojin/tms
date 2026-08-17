function r(e, t, m, c) {
  const l = t ? [e, ...Object.values(t), m] : [e, m];
  createImageBitmap.apply(null, l).then((a) => {
    c(null, a, [a]);
  }).catch((a) => {
    c(a);
  });
}
r.fileName = "transformImage";
self.onmessage = function (message) {r.apply(null, message.data.concat([function (err, response, transferList = []) {const message = { content: response, error: err };return self.postMessage(message, transferList);},{onprogress: function({ lengthComputable, loaded, total }) {self.postMessage({ type: 'progress', content: { lengthComputable, loaded, total }, error: null })}}]))}