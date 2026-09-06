/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { isBlob as i, isBlobOrFile as o, isDirectoryEntry as n, isFile as l, isFileEntry as r, isImageFile as s, isVideoFile as m } from "./test.js";
import { supportsInvokerCommands as a } from "./support.js";
import { blobToFile as b, cloneBlob as u, cloneFile as d, cloneFileWithOptions as g, getExtensionFromFilename as x, getExtensionFromMimeType as E, getFilenameWithoutExtension as y, sanitizeFilename as c, updateFileType as f, updateFilename as h } from "./file.js";
import { addListener as B, createStyleSheet as S, defineCustomElement as T, getAsElement as C, getAttribute as I, h as O, setBooleanAttribute as W, setStringAttribute as k } from "./dom.js";
export {
  B as addListener,
  b as blobToFile,
  u as cloneBlob,
  d as cloneFile,
  g as cloneFileWithOptions,
  S as createStyleSheet,
  T as defineCustomElement,
  C as getAsElement,
  I as getAttribute,
  x as getExtensionFromFilename,
  E as getExtensionFromMimeType,
  y as getFilenameWithoutExtension,
  O as h,
  i as isBlob,
  o as isBlobOrFile,
  n as isDirectoryEntry,
  l as isFile,
  r as isFileEntry,
  s as isImageFile,
  m as isVideoFile,
  c as sanitizeFilename,
  W as setBooleanAttribute,
  k as setStringAttribute,
  a as supportsInvokerCommands,
  f as updateFileType,
  h as updateFilename
};
