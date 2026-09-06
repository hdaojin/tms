/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
const i = {
  abort: "Przerwij",
  remove: "Usuń",
  reset: "Resetuj",
  undo: "Cofnij",
  cancel: "Anuluj",
  import: "Importuj",
  store: "Zapisz",
  revert: "Przywróć",
  busy: "Zajęte",
  loading: "Ładowanie",
  close: "Zamknij",
  // units
  unitB: {
    1: "bajt",
    else: "bajty"
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
    1: "piksel",
    else: "piksele"
  },
  unitFiles: {
    1: "plik",
    else: "pliki"
  },
  error: "Błąd",
  warning: "Ostrzeżenie",
  success: "Sukces",
  info: "Informacja",
  system: "System",
  // sources
  device: "Urządzenie",
  camera: "Aparat",
  link: "Link",
  // capabilities labels
  descriptionBrowse: "[Wybierz {{maxFilesUnit}}]",
  descriptionBrowseDrop: "Upuść tutaj {{maxFilesUnit}} lub [przeglądaj]",
  descriptionBrowseDropSelect: "Upuść tutaj {{maxFilesUnit}}, [przeglądaj] lub wybierz z:",
  descriptionBrowseSelect: "[Przeglądaj] lub wybierz {{maxFilesUnit}} z:",
  descriptionSelect: "Wybierz {{maxFilesUnit}} z:",
  fileMainTypeImage: "obraz",
  fileMainTypeVideo: "wideo",
  fileMainTypeAudio: "audio",
  fileMainTypeApplication: "plik",
  assistAbort: "Dotknij, aby anulować",
  assistUndo: "Dotknij, aby cofnąć",
  loadError: "Nie udało się załadować pliku.",
  loadDataTransferProgress: "Ładowanie plików",
  loadDataTransferInfo: "Przetworzono {{processedFiles}} z {{totalFiles}} plików",
  validationInvalid: "Nieprawidłowy plik.",
  validationFileNameMissing: "Brak nazwy pliku",
  validationInvalidEntries: "Lista plików zawiera nieprawidłowe elementy.",
  validationInvalidState: "Lista plików jest w nieprawidłowym stanie.",
  validationInvalidBusy: "Lista plików jest zajęta.",
  validationInvalidEmpty: {
    template: "Wybierz {{files}}.",
    variables: {
      files: {
        context: "multiple",
        map: {
          false: "plik",
          true: "co najmniej jeden plik"
        }
      }
    }
  },
  // screenreader accessibility
  ariaRequired: "wymagane",
  ariaNoEntries: "Nie wybrano {{maxFilesUnit}}",
  ariaSingleEntry: "Wybrano {{name}}",
  ariaMultipleEntries: "Wybrano {{count}} plików",
  ariaItemRoleDescription: "Możliwe sortowanie",
  ariaDragDescription: "Naciśnij spację, aby podnieść i upuścić element. Użyj klawiszy strzałek w górę i w dół, aby przenieść go na nową pozycję.",
  ariaDragStateDrop: "Upuszczono {{name}} na pozycji {{position}}",
  ariaDragStateGrab: "Podniesiono {{name}} na pozycji {{position}}",
  ariaDragStateSort: "Przeniesiono {{name}} na pozycję {{position}} z {{total}}"
}, e = {
  mediaEdit: "Edytuj",
  mediaPlay: "Odtwórz",
  mediaPause: "Pauza",
  mediaSilent: "Brak dźwięku",
  mediaUnmute: "Włącz dźwięk",
  mediaMute: "Wycisz",
  mediaFullscreen: "Pełny ekran",
  mediaLoadError: "Nie udało się załadować {{fileMainType}}.",
  mediaPlayError: "Nie udało się odtworzyć wideo."
}, a = {
  storeRestoreError: "Nie udało się załadować pliku.",
  storeRestoreProgress: "Ładowanie {{progress}}%",
  storeStorageQueued: "Oczekiwanie na przesłanie",
  storeStorageProgress: "Przesyłanie {{progress}}%",
  storeStorageComplete: "Przesyłanie zakończone",
  storeError: "Nie udało się zapisać pliku.",
  storeAwaitingCompletion: "Nie wszystkie pliki zostały zapisane."
}, t = {
  transformEditBusy: "Edycja danych pliku",
  transformError: "Nie udało się edytować danych pliku. Spróbuj ponownie."
}, o = {
  validationFileMimeTypeMismatch: {
    template: "Ten typ pliku jest niedozwolony. {{details}}.",
    variables: {
      details: {
        context: "count",
        map: {
          1: "Plik musi być typu {{accept}}",
          else: "Dozwolone typy: {{accept}}"
        }
      }
    }
  }
}, n = {
  validationFileExtensionMismatch: {
    template: "To rozszerzenie pliku jest niedozwolone. {{details}}.",
    variables: {
      details: {
        context: "count",
        map: {
          1: "Plik musi mieć rozszerzenie {{accept}}",
          else: "Dozwolone rozszerzenia: {{accept}}"
        }
      }
    }
  }
}, s = {
  validationFileNameMissing: "Brak nazwy pliku",
  validationFileNameMismatch: "Nazwa pliku jest nieprawidłowa."
}, l = {
  validationFileSizeUnderflow: "Ten plik jest za mały. Minimalny rozmiar to {{minSize}} {{minSizeUnit}}.",
  validationFileSizeOverflow: "Ten plik jest za duży. Maksymalny rozmiar to {{maxSize}} {{maxSizeUnit}}."
}, r = {
  validationListSizeUnderflow: "Łączny rozmiar plików jest za mały. Minimalny łączny rozmiar to {{minSize}} {{minSizeUnit}}.",
  validationListSizeOverflow: "Łączny rozmiar plików jest za duży. Maksymalny łączny rozmiar to {{maxSize}} {{maxSizeUnit}}."
}, d = {
  validationMediaSizeUnavailable: "Nie udało się odczytać rozmiaru multimediów.",
  validationMediaWidthRangeMismatch: "Szerokość {{fileMainType}} jest nieprawidłowa. Szerokość musi mieścić się między {{minWidth}} a {{maxWidth}} {{maxWidthUnit}}.",
  validationMediaWidthUnderflow: "{{fileMainType}} jest za mały. Minimalna szerokość to {{minWidth}} {{minWidthUnit}}.",
  validationMediaWidthOverflow: "{{fileMainType}} jest za duży. Maksymalna szerokość to {{maxWidth}} {{maxWidthUnit}}.",
  validationMediaHeightRangeMismatch: "Wysokość {{fileMainType}} jest nieprawidłowa. Wysokość musi mieścić się między {{minHeight}} a {{maxHeight}} {{maxHeightUnit}}.",
  validationMediaHeightUnderflow: "{{fileMainType}} jest za mały. Minimalna wysokość to {{minHeight}} {{minHeightUnit}}.",
  validationMediaHeightOverflow: "{{fileMainType}} jest za duży. Maksymalna wysokość to {{maxHeight}} {{maxHeightUnit}}.",
  validationMediaResolutionRangeMismatch: "Rozdzielczość jest nieprawidłowa. Musi być między {{minResolution}}MP a {{maxResolution}}MP.",
  validationMediaResolutionUnderflow: "Rozdzielczość jest zbyt niska. Minimum to {{minResolution}}MP.",
  validationMediaResolutionOverflow: "Rozdzielczość jest zbyt wysoka. Maksimum to {{maxResolution}}MP."
}, m = {
  validationListEntryCountUnderflow: "Na liście jest za mało plików. Minimum to {{minFiles}} {{minFilesUnit}}.",
  validationListEntryCountOverflow: "Na liście jest za dużo plików. Maksimum to {{maxFiles}} {{maxFilesUnit}}."
}, z = {
  ...l,
  ...o,
  ...n,
  ...s,
  ...d,
  ...r,
  ...m
}, p = {
  ...i,
  ...a,
  ...e,
  ...z,
  ...t
};
export {
  i as core,
  p as locale,
  e as media,
  a as store,
  t as transform,
  z as validation,
  n as validationFileExtension,
  o as validationFileMimeType,
  s as validationFileName,
  l as validationFileSize,
  m as validationListCount,
  r as validationListSize,
  d as validationMediaResolution
};
