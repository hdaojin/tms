/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
const e = {
  abort: "Abbrechen",
  remove: "Entfernen",
  reset: "Zurücksetzen",
  undo: "Rückgängig",
  cancel: "Abbrechen",
  import: "Importieren",
  store: "Speichern",
  revert: "Wiederherstellen",
  busy: "Beschäftigt",
  loading: "Laden",
  close: "Schließen",
  // units
  unitB: {
    1: "Byte",
    else: "Bytes"
  },
  unitKB: "KB",
  unitMB: "MB",
  unitGB: "GB",
  unitTB: "TB",
  unitPB: "PB",
  unitKiB: "KiB",
  unitMiB: "MiB",
  unitGiB: "GiB",
  unitTiB: "TiB",
  unitPiB: "PiB",
  unitPixels: {
    1: "Pixel",
    else: "Pixel"
  },
  unitFiles: {
    1: "Datei",
    else: "Dateien"
  },
  error: "Fehler",
  warning: "Warnung",
  success: "Erfolgreich",
  info: "Info",
  system: "System",
  // sources
  device: "Gerät",
  camera: "Kamera",
  link: "Link",
  // capabilities labels
  descriptionBrowse: "[{{maxFilesUnit}} auswählen]",
  descriptionBrowseDrop: "{{maxFilesUnit}} hier ablegen oder [durchsuchen]",
  descriptionBrowseDropSelect: "{{maxFilesUnit}} hier ablegen, [durchsuchen] oder aus folgenden Quellen auswählen:",
  descriptionBrowseSelect: "[Durchsuchen] oder {{maxFilesUnit}} aus folgenden Quellen auswählen:",
  descriptionSelect: "{{maxFilesUnit}} aus folgenden Quellen auswählen:",
  fileMainTypeImage: "Bild",
  fileMainTypeVideo: "Video",
  fileMainTypeAudio: "Audio",
  fileMainTypeApplication: "Datei",
  assistAbort: "Tippen zum Abbrechen",
  assistUndo: "Tippen zum Rückgängig machen",
  loadError: "Datei konnte nicht geladen werden.",
  loadDataTransferProgress: "Dateien werden geladen",
  loadDataTransferInfo: "{{processedFiles}} von {{totalFiles}} Dateien verarbeitet",
  validationInvalid: "Ungültige Datei.",
  validationFileNameMissing: "Dateiname fehlt",
  validationInvalidEntries: "Die Dateiliste enthält ungültige Elemente.",
  validationInvalidState: "Die Dateiliste befindet sich in einem ungültigen Zustand.",
  validationInvalidBusy: "Die Dateiliste ist beschäftigt.",
  validationInvalidEmpty: {
    template: "Bitte wählen Sie {{files}} aus.",
    variables: {
      files: {
        context: "multiple",
        map: {
          false: "eine Datei",
          true: "eine oder mehrere Dateien"
        }
      }
    }
  },
  // screenreader accessibility
  ariaRequired: "erforderlich",
  ariaNoEntries: "Keine {{maxFilesUnit}} ausgewählt",
  ariaSingleEntry: "Ausgewählt: {{name}}",
  ariaMultipleEntries: "{{count}} Dateien ausgewählt",
  ariaItemRoleDescription: "Sortierbar",
  ariaDragDescription: "Drücke die Leertaste, um ein Element aufzunehmen und abzulegen. Verwende die Pfeiltasten nach oben und unten, um es an eine neue Position zu verschieben.",
  ariaDragStateDrop: "„{{name}}“ an Position {{position}} abgelegt",
  ariaDragStateGrab: "„{{name}}“ an Position {{position}} aufgenommen",
  ariaDragStateSort: "„{{name}}“ an Position {{position}} von {{total}} verschoben"
}, i = {
  mediaEdit: "Bearbeiten",
  mediaPlay: "Abspielen",
  mediaPause: "Pause",
  mediaSilent: "Kein Audio",
  mediaUnmute: "Stumm aus",
  mediaMute: "Stumm",
  mediaFullscreen: "Vollbild",
  mediaLoadError: "{{fileMainType}} konnte nicht geladen werden.",
  mediaPlayError: "Video kann nicht abgespielt werden."
}, t = {
  storeRestoreError: "Datei konnte nicht geladen werden.",
  storeRestoreProgress: "{{progress}}% laden",
  storeStorageQueued: "Warten auf Upload",
  storeStorageProgress: "Hochladen {{progress}}%",
  storeStorageComplete: "Upload abgeschlossen",
  storeError: "Datei konnte nicht gespeichert werden.",
  storeAwaitingCompletion: "Nicht alle Dateien wurden gespeichert."
}, n = {
  transformEditBusy: "Datei wird bearbeitet",
  transformError: "Datei konnte nicht bearbeitet werden. Bitte erneut versuchen."
}, a = {
  validationFileMimeTypeMismatch: {
    template: "Dieser Dateityp ist nicht erlaubt. {{details}}.",
    variables: {
      details: {
        context: "count",
        map: {
          1: "Datei muss vom Typ {{accept}} sein",
          else: "Zulässige Typen: {{accept}}"
        }
      }
    }
  }
}, l = {
  validationFileExtensionMismatch: {
    template: "Diese Dateierweiterung ist nicht erlaubt. {{details}}.",
    variables: {
      details: {
        context: "count",
        map: {
          1: "Datei muss die Erweiterung {{accept}} haben",
          else: "Zulässige Erweiterungen: {{accept}}"
        }
      }
    }
  }
}, s = {
  validationFileNameMissing: "Dateiname fehlt",
  validationFileNameMismatch: "Dieser Dateiname ist ungültig."
}, r = {
  validationFileSizeUnderflow: "Diese Datei ist zu klein. Mindestgröße: {{minSize}} {{minSizeUnit}}.",
  validationFileSizeOverflow: "Diese Datei ist zu groß. Maximalgröße: {{maxSize}} {{maxSizeUnit}}."
}, o = {
  validationListSizeUnderflow: "Gesamtgröße zu klein. Die Mindestgesamtgröße beträgt {{minSize}} {{minSizeUnit}}.",
  validationListSizeOverflow: "Gesamtgröße zu groß. Die maximale Gesamtgröße beträgt {{maxSize}} {{maxSizeUnit}}."
}, d = {
  validationMediaSizeUnavailable: "Mediagröße konnte nicht gelesen werden.",
  validationMediaWidthRangeMismatch: "Die Breite des {{fileMainType}} ist ungültig. Die Breite muss zwischen {{minWidth}} und {{maxWidth}} {{maxWidthUnit}} liegen.",
  validationMediaWidthUnderflow: "Der {{fileMainType}} ist zu klein. Die minimale Breite beträgt {{minWidth}} {{minWidthUnit}}.",
  validationMediaWidthOverflow: "Der {{fileMainType}} ist zu groß. Die maximale Breite beträgt {{maxWidth}} {{maxWidthUnit}}.",
  validationMediaHeightRangeMismatch: "Die Höhe des {{fileMainType}} ist ungültig. Die Höhe muss zwischen {{minHeight}} und {{maxHeight}} {{maxHeightUnit}} liegen.",
  validationMediaHeightUnderflow: "Der {{fileMainType}} ist zu klein. Die minimale Höhe beträgt {{minHeight}} {{minHeightUnit}}.",
  validationMediaHeightOverflow: "Der {{fileMainType}} ist zu groß. Die maximale Höhe beträgt {{maxHeight}} {{maxHeightUnit}}.",
  validationMediaResolutionRangeMismatch: "Die Auflösung des {{fileMainType}} ist ungültig. Die Auflösung muss zwischen {{minResolution}}MP und {{maxResolution}}MP liegen.",
  validationMediaResolutionUnderflow: "Die Auflösung des {{fileMainType}} ist ungültig. Die minimale Auflösung beträgt {{minResolution}}MP.",
  validationMediaResolutionOverflow: "Die Auflösung des {{fileMainType}} ist ungültig. Die maximale Auflösung beträgt {{maxResolution}}MP."
}, u = {
  validationListEntryCountUnderflow: "Zu wenige Dateien in der Liste. Minimum: {{minFiles}} {{minFilesUnit}}.",
  validationListEntryCountOverflow: "Zu viele Dateien in der Liste. Maximum: {{maxFiles}} {{maxFilesUnit}}."
}, m = {
  ...r,
  ...a,
  ...l,
  ...s,
  ...d,
  ...o,
  ...u
}, g = {
  ...e,
  ...t,
  ...i,
  ...m,
  ...n
};
export {
  e as core,
  g as locale,
  i as media,
  t as store,
  n as transform,
  m as validation,
  l as validationFileExtension,
  a as validationFileMimeType,
  s as validationFileName,
  r as validationFileSize,
  u as validationListCount,
  o as validationListSize,
  d as validationMediaResolution
};
