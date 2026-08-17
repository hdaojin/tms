import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const policySource = await readFile(
  new URL("../static/js/filepond-policy.js", import.meta.url),
  "utf8",
);
const policy = await import(
  `data:text/javascript;base64,${Buffer.from(policySource).toString("base64")}`
);

function makeNode(parent = null) {
  return {
    parent,
    contains(candidate) {
      for (let current = candidate; current; current = current.parent) {
        if (current === this) return true;
      }
      return false;
    },
  };
}

function makePasteEvent({ files = 0, items = [], path = [] } = {}) {
  return {
    clipboardData: { files: { length: files }, items },
    composedPath: () => path,
  };
}

test("paste is enabled by default and can be explicitly disabled", () => {
  assert.equal(policy.isPasteEnabled(undefined), true);
  assert.equal(policy.isPasteEnabled("auto"), true);
  assert.equal(policy.isPasteEnabled("true"), true);
  assert.equal(policy.isPasteEnabled("false"), false);
});

test("pure text paste is never handled", () => {
  const wrapper = makeNode();
  const pond = makeNode(wrapper);
  assert.equal(
    policy.shouldHandleFilePaste({
      mode: "auto",
      wrapper,
      pond,
      event: makePasteEvent(),
      activeElement: pond,
    }),
    false,
  );
});

test("file paste requires focus inside the target upload wrapper", () => {
  const wrapper = makeNode();
  const pond = makeNode(wrapper);
  const outside = makeNode();
  const event = makePasteEvent({ files: 1, path: [outside] });

  assert.equal(
    policy.shouldHandleFilePaste({
      mode: "auto",
      wrapper,
      pond,
      event,
      activeElement: outside,
    }),
    false,
  );
  assert.equal(
    policy.shouldHandleFilePaste({
      mode: "auto",
      wrapper,
      pond,
      event,
      activeElement: pond,
    }),
    true,
  );
});

test("only the focused upload wrapper handles a file paste", () => {
  const firstWrapper = makeNode();
  const firstPond = makeNode(firstWrapper);
  const secondWrapper = makeNode();
  const secondPond = makeNode(secondWrapper);
  const event = makePasteEvent({ items: [{ kind: "file" }] });

  assert.equal(
    policy.shouldHandleFilePaste({
      mode: "auto",
      wrapper: firstWrapper,
      pond: firstPond,
      event,
      activeElement: firstPond,
    }),
    true,
  );
  assert.equal(
    policy.shouldHandleFilePaste({
      mode: "auto",
      wrapper: secondWrapper,
      pond: secondPond,
      event,
      activeElement: firstPond,
    }),
    false,
  );
});

test("disabled paste mode rejects file clipboard data", () => {
  const wrapper = makeNode();
  const pond = makeNode(wrapper);
  assert.equal(
    policy.shouldHandleFilePaste({
      mode: "false",
      wrapper,
      pond,
      event: makePasteEvent({ files: 1, path: [pond, wrapper] }),
      activeElement: pond,
    }),
    false,
  );
});

test("file drag depth remains stable across nested elements", () => {
  assert.equal(policy.dataTransferHasFiles({ types: ["text/plain"] }), false);
  assert.equal(policy.dataTransferHasFiles({ types: ["Files"] }), true);
  let depth = policy.nextDragDepth(0, "dragenter");
  depth = policy.nextDragDepth(depth, "dragenter");
  depth = policy.nextDragDepth(depth, "dragleave");
  assert.equal(depth, 1);
  assert.equal(policy.nextDragDepth(depth, "drop"), 0);
});

test("initialization registry can claim each pond only once", () => {
  const registry = new WeakSet();
  const pond = {};
  assert.equal(policy.claimInitialization(registry, pond), true);
  assert.equal(policy.claimInitialization(registry, pond), false);
});

test("image part wrapper forwards every FilePond props argument", () => {
  const context = { entry: { file: { type: "image/png" } } };
  const actions = {
    updateEntryState() {},
    removeEntries() {},
  };
  const originalProps = (receivedContext, receivedActions) => {
    assert.equal(receivedContext, context);
    assert.equal(receivedActions, actions);
    return { part: "entry-load-state", actions: receivedActions };
  };

  const props = policy.withImageEntryPart(
    originalProps,
    "image-entry-load-state",
  )(context, actions);

  assert.equal(props.actions, actions);
  assert.equal(props.part, "entry-load-state image-entry-load-state");
});

test("single-file add state reopens whenever the queue becomes empty", () => {
  const extensionNames = [
    "FileInputSource",
    "ClipboardSource",
    "EntryListView",
  ];
  const pond = Object.fromEntries(
    extensionNames.map((name) => [name, { preventAddEntries: true }]),
  );

  assert.equal(
    policy.syncSingleFileAddEntryState(pond, extensionNames, 2, 0),
    null,
  );
  assert.equal(
    policy.syncSingleFileAddEntryState(pond, extensionNames, 1, 1),
    true,
  );

  for (const removalReason of ["valid", "invalid", "form-reset"]) {
    assert.equal(
      policy.syncSingleFileAddEntryState(pond, extensionNames, 1, 0),
      false,
      removalReason,
    );
    for (const extensionName of extensionNames) {
      assert.equal(pond[extensionName].preventAddEntries, false);
    }
  }
});

test("adapter keeps native browse UI and avoids internal input polling", async () => {
  const adapterSource = await readFile(
    new URL("../static/js/filepond.js", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(
    adapterSource,
    /queueMicrotask|shadowRoot|FileInputStore/,
  );
  assert.match(adapterSource, /workersURL/);
  assert.match(adapterSource, /part="browse-label"/);
  assert.match(adapterSource, /maximumPixels: 262144/);
  assert.match(adapterSource, /"image-entry-media"/);
  assert.match(adapterSource, /configureSingleFileRecovery/);
  assert.match(adapterSource, /addEventListener\("entrieschange"/);
  assert.doesNotMatch(adapterSource, /pond\.browse\(\)/);
});

test("upload styles reuse form tokens and keep emphasis narrowly scoped", async () => {
  const cssSource = await readFile(
    new URL("../static/css/main.css", import.meta.url),
    "utf8",
  );

  assert.match(cssSource, /--default-border-radius: var\(--radius-field\)/);
  assert.match(cssSource, /--default-border: var\(--border\) solid/);
  assert.match(cssSource, /::part\(browse-label\)/);
  assert.match(
    cssSource,
    /\.tms-upload-paste-active[\s\S]*var\(--color-info\)/,
  );
  assert.match(
    cssSource,
    /::part\(image-entry-media\)[\s\S]*width: 4rem;[\s\S]*height: 4rem;/,
  );
  assert.doesNotMatch(
    cssSource,
    /::part\(source-description-element\)[^{]*\{[^}]*background-color/,
  );
});
