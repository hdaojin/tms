import { defineFilePond } from "../vendor/filepond/esm/index.js";
import {
  ClipboardSource,
  FileSizeValidator,
  ListCountValidator,
  ListSizeValidator,
} from "../vendor/filepond/esm/extensions/index.js";
import {
  appendEntryImageView,
  createFilePondEntryList,
  withNodeTree,
} from "../vendor/filepond/esm/templates/index.js";
import { locale } from "../vendor/filepond/esm/locales/zh-cn.js";
import {
  claimInitialization,
  dataTransferHasFiles,
  eventPathHasInteractiveElement,
  isPasteEnabled,
  nextDragDepth,
  shouldHandleFilePaste,
  syncSingleFileAddEntryState,
  withImageEntryPart,
} from "./filepond-policy.js";

const filePondSelector = "file-pond[data-tms-file-upload]";
const wrapperSelector = "[data-tms-file-upload-wrapper]";
const configuredPonds = new WeakSet();
const workersURL = new URL("../vendor/filepond/esm/workers", import.meta.url);
const addEntryStateExtensions = [
  "FileInputSource",
  "ClipboardSource",
  "EntryListView",
  "SourceDescriptionView",
  "SourceListView",
];
const browseLabel = '<span part="browse-label">浏览文件</span>';
const previewTemplate = appendEntryImageView(createFilePondEntryList(), {
  enableEdit: false,
  enableReset: false,
  maximumPixels: 262144,
  objectFit: "cover",
});

function addImagePart(template, nodeKey, partName) {
  withNodeTree(template).update(nodeKey, (node) => {
    node.props = withImageEntryPart(node.props, partName);
  });
}

for (const [nodeKey, partName] of [
  ["entry", "image-entry"],
  ["entry-load-state", "image-entry-load-state"],
  ["entry-info", "image-entry-info"],
  ["entry-store-state", "image-entry-store-state"],
  ["entry-status", "image-entry-status"],
  ["entry-image-spring", "image-entry-media"],
]) {
  addImagePart(previewTemplate, nodeKey, partName);
}
const plainTemplate = createFilePondEntryList();
const tmsLocale = {
  ...locale,
  descriptionBrowse: `[${browseLabel}]`,
  descriptionBrowseDrop: `将文件拖放到此处，或[${browseLabel}]`,
  descriptionBrowseDropSelect: `将文件拖放到此处、[${browseLabel}]，或从以下选项中选择`,
  descriptionBrowseSelect: `[${browseLabel}]，或从以下选项中选择文件`,
};

defineFilePond({
  locale: tmsLocale,
  workersURL,
  extensions: [
    ClipboardSource,
    FileSizeValidator,
    ListCountValidator,
    ListSizeValidator,
  ],
  ClipboardSource: { preventAddEntries: true },
  EntryListView: { template: previewTemplate },
});

function collectFilePonds(root = document) {
  const ponds = [];
  if (root?.matches?.(filePondSelector)) ponds.push(root);
  if (root?.querySelectorAll)
    ponds.push(...root.querySelectorAll(filePondSelector));
  return ponds;
}

function configureValidation(pond) {
  const maxSize = Number(pond.dataset.uploadMaxSizeMb);
  if (Number.isFinite(maxSize) && maxSize >= 0) pond.maxSize = `${maxSize}MB`;

  const maxFiles = Number(pond.dataset.uploadMaxFiles);
  if (Number.isFinite(maxFiles) && maxFiles >= 0) pond.maxFiles = maxFiles;

  const maxTotalSize = Number(pond.dataset.uploadMaxTotalSizeMb);
  if (Number.isFinite(maxTotalSize) && maxTotalSize >= 0)
    pond.maxListSize = `${maxTotalSize}MB`;
}

function configurePreview(pond) {
  pond.EntryListView = {
    template:
      String(pond.dataset.uploadPreview || "true").toLowerCase() === "false"
        ? plainTemplate
        : previewTemplate,
  };
}

function configurePaste(pond, wrapper) {
  const mode = pond.dataset.uploadPaste || "auto";
  const controls = wrapper.querySelector("[data-tms-upload-enhanced]");
  const hint = wrapper.querySelector("[data-tms-upload-paste-hint]");
  const enabled = isPasteEnabled(mode);

  if (controls) controls.hidden = false;
  if (hint) hint.hidden = !enabled;
  pond.ClipboardSource = {
    preventAddEntries: false,
    shouldHandlePaste: (event) =>
      shouldHandleFilePaste({
        mode,
        wrapper,
        pond,
        event,
        activeElement: document.activeElement,
      }),
  };
}

function configureSingleFileRecovery(pond) {
  const syncAddEntryState = () => {
    syncSingleFileAddEntryState(
      pond,
      addEntryStateExtensions,
      pond.maxFiles,
      pond.currentEntries?.length ?? 0,
    );
  };

  pond.addEventListener("entrieschange", syncAddEntryState);
  syncAddEntryState();
}

function configureFocus(pond, wrapper) {
  wrapper.addEventListener("pointerdown", (event) => {
    if (
      event.button !== 0 ||
      pond.disabled ||
      eventPathHasInteractiveElement(event)
    )
      return;
    pond.focus({ preventScroll: true });
  });
}

function configureDragState(pond, wrapper) {
  let dragDepth = 0;

  const updateState = (event) => {
    if (event.type === "drop") {
      dragDepth = 0;
      wrapper.dataset.dragActive = "false";
      return;
    }
    if (!dataTransferHasFiles(event.dataTransfer)) return;
    dragDepth = nextDragDepth(dragDepth, event.type);
    wrapper.dataset.dragActive =
      dragDepth > 0 && !pond.disabled ? "true" : "false";
  };

  wrapper.addEventListener("dragenter", updateState);
  wrapper.addEventListener("dragleave", updateState);
  wrapper.addEventListener("drop", updateState);
  wrapper.addEventListener("dragend", (event) => {
    dragDepth = nextDragDepth(dragDepth, event.type);
    wrapper.dataset.dragActive = "false";
  });
}

function configureFilePond(pond) {
  if (!pond.isConnected) return;

  const wrapper = pond.closest(wrapperSelector);
  if (!wrapper || !claimInitialization(configuredPonds, pond)) return;

  configureValidation(pond);
  configurePreview(pond);
  configurePaste(pond, wrapper);
  configureSingleFileRecovery(pond);
  configureFocus(pond, wrapper);
  configureDragState(pond, wrapper);
  wrapper.dataset.tmsFilepondReady = "true";
}

export function initFilePonds(root = document) {
  collectFilePonds(root).forEach(configureFilePond);
}

customElements.whenDefined("file-pond").then(() => initFilePonds());
document.addEventListener("htmx:afterSwap", (event) =>
  initFilePonds(event.target),
);
