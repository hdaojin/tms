import assert from "node:assert/strict";
import test from "node:test";
import { initializePdfPreview } from "../static/js/pdf-preview.mjs";

function fixture({ error, renderError } = {}) {
  const nodes = Object.fromEntries(
    ["canvas", "viewport", "previous", "next", "page", "status"].map((name) => [
      name,
      {
        disabled: true,
        hidden: true,
        clientWidth: 360,
        setAttribute() {},
        getContext: () => ({}),
        addEventListener(event, handler) {
          this[event] = handler;
        },
      },
    ]),
  );
  const calls = [];
  let options;
  const root = {
    dataset: {
      pdfUrl: "/private/preview/",
      pdfWorker: "/static/worker.mjs",
      pdfAssets: "/static/pdfjs/",
    },
    querySelector: (selector) => nodes[selector.slice(10, -1)],
  };
  const pdfjs = {
    GlobalWorkerOptions: {},
    getDocument(value) {
      options = value;
      return {
        promise: error
          ? Promise.reject(error)
          : Promise.resolve({
              numPages: 2,
              async getPage(number) {
                calls.push(number);
                return {
                  getViewport: ({ scale }) => ({
                    width: 600 * scale,
                    height: 800 * scale,
                  }),
                  render: () => ({
                    promise: renderError
                      ? Promise.reject(renderError)
                      : Promise.resolve(),
                  }),
                  cleanup() {},
                };
              },
            }),
      };
    },
  };
  return { nodes, calls, root, pdfjs, options: () => options };
}

// Node has no location; provide only the same-origin browser context required here.
globalThis.location = {
  href: "https://tms.example/detail/",
  origin: "https://tms.example",
};
globalThis.devicePixelRatio = 3;

test("renders and navigates a private PDF with bounded canvas and strict CSP options", async () => {
  const f = fixture();
  await initializePdfPreview(f.root, f.pdfjs);
  assert.deepEqual(f.calls, [1]);
  assert.equal(f.nodes.previous.disabled, true);
  assert.equal(f.nodes.next.disabled, false);
  assert.equal(f.nodes.canvas.hidden, false);
  assert.ok(f.nodes.canvas.width * f.nodes.canvas.height <= 4_000_000);
  assert.equal(f.options().url, "https://tms.example/private/preview/");
  assert.equal(f.options().isEvalSupported, false);
  assert.equal(f.options().disableFontFace, true);
  assert.equal(f.options().useWasm, false);
  f.nodes.next.click();
  f.nodes.next.click(); // A second click during rendering must not skip a page.
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(f.calls, [1, 2]);
  assert.equal(f.nodes.next.disabled, true);
  assert.equal(f.nodes.previous.disabled, false);
  f.nodes.previous.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(f.calls, [1, 2, 1]);
});

test("loading and password failures retain useful download guidance", async () => {
  for (const error of [new Error("403"), { name: "PasswordException" }]) {
    const f = fixture({ error });
    await initializePdfPreview(f.root, f.pdfjs);
    assert.match(f.nodes.status.textContent, /下载/);
    assert.equal(f.nodes.previous.disabled, true);
    assert.equal(f.nodes.next.disabled, true);
  }
});

test("render failure hides incomplete canvas and releases navigation", async () => {
  const f = fixture({ renderError: new Error("invalid page") });
  await initializePdfPreview(f.root, f.pdfjs);
  assert.equal(f.nodes.canvas.hidden, true);
  assert.match(f.nodes.status.textContent, /加载失败/);
  assert.equal(f.nodes.next.disabled, false);
});

test("rejects a cross-origin document before loading", async () => {
  const f = fixture();
  f.root.dataset.pdfUrl = "https://other.example/private.pdf";
  await initializePdfPreview(f.root, f.pdfjs);
  assert.equal(f.options(), undefined);
  assert.match(f.nodes.status.textContent, /下载/);
});
