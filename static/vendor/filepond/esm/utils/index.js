/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { isBlob as o, isBlobOrFile as t, isDirectoryEntry as l, isFile as n, isFileEntry as r, isImageFile as s, isVideoFile as m } from "./test.js";
import { supportsInvokerCommands as p } from "./support.js";
import { blobToFile as x, cloneBlob as d, cloneFile as E, cloneFileWithOptions as b, getExtensionFromFilename as g, getExtensionFromMimeType as y, getFilenameWithoutExtension as c, sanitizeFilename as f, updateFileType as u, updateFilename as h } from "./file.js";
import { addListener as T, getAsElement as I, h as O } from "./dom.js";
export {
  T as addListener,
  x as blobToFile,
  d as cloneBlob,
  E as cloneFile,
  b as cloneFileWithOptions,
  I as getAsElement,
  g as getExtensionFromFilename,
  y as getExtensionFromMimeType,
  c as getFilenameWithoutExtension,
  O as h,
  o as isBlob,
  t as isBlobOrFile,
  l as isDirectoryEntry,
  n as isFile,
  r as isFileEntry,
  s as isImageFile,
  m as isVideoFile,
  f as sanitizeFilename,
  p as supportsInvokerCommands,
  u as updateFileType,
  h as updateFilename
};
