import assert from "node:assert/strict";
import test from "node:test";
import { initializePdfPreview } from "../static/js/pdf-preview.mjs";

function fixture({ error, renderError } = {}) {
  const nodes = Object.fromEntries(
    ["viewport", "status", "pages", "page-template"].map((name) => [
      name,
      {
        replaceChildren(...children) {
          this.children = children;
        },
      },
    ]),
  );
  nodes["page-template"].content = {
    firstElementChild: {
      cloneNode: () => ({
        dataset: {},
        style: {},
        clientWidth: 360,
        setAttribute() {},
        firstElementChild: { hidden: true, getContext: () => ({}) },
      }),
    },
  };
  const calls = [];
  let destroyed = false;
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
        async destroy() {
          destroyed = true;
        },
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
  return { nodes, calls, root, pdfjs, options: () => options, destroyed: () => destroyed };
}

// Node has no location; provide only the same-origin browser context required here.
globalThis.location = {
  href: "https://tms.example/detail/",
  origin: "https://tms.example",
};
globalThis.devicePixelRatio = 3;

let observer;
globalThis.IntersectionObserver = class {
  constructor(callback) {
    this.callback = callback;
    observer = this;
  }
  observe() {}
  unobserve() {}
  disconnect() {
    this.disconnected = true;
  }
};

async function intersect(visible, hidden = []) {
  observer.callback([
    ...visible.map((target) => ({ target, isIntersecting: true })),
    ...hidden.map((target) => ({ target, isIntersecting: false })),
  ]);
  await new Promise((resolve) => setImmediate(resolve));
}

test("renders nearby pages in document order and releases distant canvases", async () => {
  const f = fixture();
  await initializePdfPreview(f.root, f.pdfjs);
  const [first, second] = f.nodes.pages.children;
  assert.deepEqual(f.nodes.pages.children.map((page) => page.dataset.pageNumber), [1, 2]);
  assert.deepEqual(f.calls, []);
  await intersect([first, second]);
  assert.deepEqual(f.calls, [1, 2]);
  const canvas = first.firstElementChild;
  assert.equal(canvas.hidden, false);
  assert.equal(second.firstElementChild.hidden, false);
  assert.ok(canvas.width * canvas.height <= 4_000_000);
  await intersect([], [first]);
  assert.equal(canvas.width, 0);
  assert.equal(second.firstElementChild.hidden, false);
  await intersect([first]);
  assert.deepEqual(f.calls, [1, 2, 1]);
  assert.equal(f.options().url, "https://tms.example/private/preview/");
  assert.equal(f.options().isEvalSupported, false);
  assert.equal(f.options().disableFontFace, true);
  assert.equal(f.options().useWasm, false);
});

test("loading and password failures retain useful download guidance", async () => {
  for (const error of [new Error("403"), { name: "PasswordException" }]) {
    const f = fixture({ error });
    await initializePdfPreview(f.root, f.pdfjs);
    assert.match(f.nodes.status.textContent, /下载/);
  }
});

test("render failure keeps the placeholder and shows download guidance", async () => {
  const f = fixture({ renderError: new Error("invalid page") });
  await initializePdfPreview(f.root, f.pdfjs);
  const [first] = f.nodes.pages.children;
  await intersect([first]);
  assert.equal(first.firstElementChild.hidden, true);
  assert.match(f.nodes.status.textContent, /加载失败/);
  assert.equal(f.nodes.pages.children.length, 2);
});

test("rejects a cross-origin document before loading", async () => {
  const f = fixture();
  f.root.dataset.pdfUrl = "https://other.example/private.pdf";
  await initializePdfPreview(f.root, f.pdfjs);
  assert.equal(f.options(), undefined);
  assert.match(f.nodes.status.textContent, /下载/);
});

test("uses in-memory PDF bytes and destroys the loading task on invalidation", async () => {
  const f = fixture();
  const controller = new AbortController();
  const data = new Uint8Array([37, 80, 68, 70, 45]);
  await initializePdfPreview(f.root, f.pdfjs, { data, signal: controller.signal });
  assert.equal(f.options().data, data);
  assert.equal(f.options().url, undefined);
  const [first] = f.nodes.pages.children;
  await intersect([first]);
  assert.equal(first.firstElementChild.hidden, false);
  controller.abort();
  assert.equal(f.destroyed(), true);
  assert.equal(observer.disconnected, true);
  assert.equal(first.firstElementChild.width, 0);
  assert.deepEqual(f.nodes.pages.children, []);
});
