const disabledPasteModes = new Set(["false", "0", "off", "no"]);

export function isPasteEnabled(mode) {
  return !disabledPasteModes.has(
    String(mode ?? "auto")
      .trim()
      .toLowerCase(),
  );
}

export function clipboardHasFiles(clipboardData) {
  if (!clipboardData) return false;
  if ((clipboardData.files?.length ?? 0) > 0) return true;
  return Array.from(clipboardData.items ?? []).some(
    (item) => item?.kind === "file",
  );
}

function containsNode(container, node) {
  return Boolean(
    container && node && (container === node || container.contains?.(node)),
  );
}

export function shouldHandleFilePaste({
  mode,
  wrapper,
  pond,
  event,
  activeElement,
}) {
  if (!isPasteEnabled(mode) || !clipboardHasFiles(event?.clipboardData))
    return false;

  const path =
    typeof event.composedPath === "function"
      ? event.composedPath()
      : [event.target];
  if (path.includes(pond) || path.includes(wrapper)) return true;
  return containsNode(wrapper, activeElement);
}

export function dataTransferHasFiles(dataTransfer) {
  return Array.from(dataTransfer?.types ?? []).includes("Files");
}

export function nextDragDepth(depth, eventType) {
  if (eventType === "dragenter") return depth + 1;
  if (eventType === "dragleave") return Math.max(0, depth - 1);
  if (eventType === "drop" || eventType === "dragend") return 0;
  return depth;
}

export function eventPathHasInteractiveElement(event) {
  const selector =
    'button, a, input, select, textarea, [contenteditable=""], [contenteditable="true"], [contenteditable="plaintext-only"], [role="button"]';
  const path =
    typeof event.composedPath === "function"
      ? event.composedPath()
      : [event.target];
  return path.some(
    (node) => typeof node?.matches === "function" && node.matches(selector),
  );
}

export function claimInitialization(registry, target) {
  if (registry.has(target)) return false;
  registry.add(target);
  return true;
}

export function withImageEntryPart(originalProps, partName) {
  return (...args) => {
    const [context] = args;
    const props =
      typeof originalProps === "function"
        ? originalProps(...args)
        : originalProps || {};
    const isImage = context?.entry?.file?.type?.startsWith("image/");
    return {
      ...props,
      part: [props.part, isImage ? partName : ""].filter(Boolean).join(" "),
    };
  };
}

export function singleFilePreventAddEntries(maxFiles, entryCount) {
  if (Number(maxFiles) !== 1) return null;
  return Number(entryCount) >= 1;
}

export function syncSingleFileAddEntryState(
  target,
  extensionNames,
  maxFiles,
  entryCount,
) {
  const preventAddEntries = singleFilePreventAddEntries(maxFiles, entryCount);
  if (preventAddEntries === null) return null;

  for (const extensionName of extensionNames) {
    const extension = target[extensionName];
    if (!extension || extension.preventAddEntries === preventAddEntries)
      continue;
    target[extensionName] = { ...extension, preventAddEntries };
  }
  return preventAddEntries;
}
