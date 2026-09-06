/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
const e = {
  abort: "Zrušit",
  remove: "Odstranit",
  reset: "Resetovat",
  undo: "Vrátit",
  cancel: "Zrušit",
  import: "Importovat",
  store: "Uložit",
  revert: "Obnovit",
  busy: "Zaneprázdněno",
  loading: "Načítání",
  close: "Zavřít",
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
    1: "pixel",
    else: "pixely"
  },
  unitFiles: {
    1: "soubor",
    else: "soubory"
  },
  error: "Chyba",
  warning: "Varování",
  success: "Úspěch",
  info: "Informace",
  system: "Systém",
  // sources
  device: "Zařízení",
  camera: "Fotoaparát",
  link: "Odkaz",
  // capabilities labels
  descriptionBrowse: "[Vybrat {{maxFilesUnit}}]",
  descriptionBrowseDrop: "Přetáhněte sem {{maxFilesUnit}} nebo [Procházet]",
  descriptionBrowseDropSelect: "Přetáhněte sem {{maxFilesUnit}}, [Procházet] nebo vyberte z těchto zdrojů:",
  descriptionBrowseSelect: "[Procházet] nebo vyberte {{maxFilesUnit}} z těchto zdrojů:",
  descriptionSelect: "Vyberte {{maxFilesUnit}} z těchto zdrojů:",
  fileMainTypeImage: "obrázek",
  fileMainTypeVideo: "video",
  fileMainTypeAudio: "audio",
  fileMainTypeApplication: "soubor",
  assistAbort: "Klepněte pro zrušení",
  assistUndo: "Klepněte pro vrácení",
  loadError: "Soubor se nepodařilo načíst.",
  loadDataTransferProgress: "Načítání souborů",
  loadDataTransferInfo: "Zpracováno {{processedFiles}} z {{totalFiles}} souborů",
  validationInvalid: "Neplatný soubor.",
  validationFileNameMissing: "Chybí název souboru",
  validationInvalidEntries: "Seznam obsahuje neplatné položky.",
  validationInvalidState: "Seznam souborů je v neplatném stavu.",
  validationInvalidBusy: "Seznam souborů je zaneprázdněn.",
  validationInvalidEmpty: {
    template: "Vyberte {{files}}.",
    variables: {
      files: {
        context: "multiple",
        map: {
          false: "soubor",
          true: "jeden nebo více souborů"
        }
      }
    }
  },
  // screenreader accessibility
  ariaRequired: "povinné",
  ariaNoEntries: "Nebyly vybrány žádné {{maxFilesUnit}}",
  ariaSingleEntry: "Vybráno {{name}}",
  ariaMultipleEntries: "Vybráno {{count}} souborů",
  ariaItemRoleDescription: "Seřaditelné",
  ariaDragDescription: "Stisknutím mezerníku položku zvednete a upustíte. Pomocí šipek nahoru a dolů ji přesunete na novou pozici.",
  ariaDragStateDrop: "Položka {{name}} byla umístěna na pozici {{position}}",
  ariaDragStateGrab: "Položka {{name}} byla uchopena na pozici {{position}}",
  ariaDragStateSort: "Položka {{name}} byla přesunuta na pozici {{position}} z {{total}}"
}, i = {
  mediaEdit: "Upravit",
  mediaPlay: "Přehrát",
  mediaPause: "Pozastavit",
  mediaSilent: "Bez zvuku",
  mediaUnmute: "Zapnout zvuk",
  mediaMute: "Vypnout zvuk",
  mediaFullscreen: "Celá obrazovka",
  mediaLoadError: "{{fileMainType}} se nepodařilo načíst.",
  mediaPlayError: "Video se nepodařilo přehrát."
}, o = {
  storeRestoreError: "Soubor se nepodařilo načíst.",
  storeRestoreProgress: "Načítání {{progress}}%",
  storeStorageQueued: "Čeká na nahrání",
  storeStorageProgress: "Nahrávání {{progress}}%",
  storeStorageComplete: "Nahrávání dokončeno",
  storeError: "Soubor se nepodařilo uložit.",
  storeAwaitingCompletion: "Ne všechny soubory byly uloženy."
}, a = {
  transformEditBusy: "Úprava dat souboru",
  transformError: "Nepodařilo se upravit data souboru. Zkuste to znovu."
}, t = {
  validationFileMimeTypeMismatch: {
    template: "Tento typ souboru není povolen. {{details}}.",
    variables: {
      details: {
        context: "count",
        map: {
          1: "Soubor musí být typu {{accept}}",
          else: "Povolené typy: {{accept}}"
        }
      }
    }
  }
}, n = {
  validationFileExtensionMismatch: {
    template: "Tato přípona není povolena. {{details}}.",
    variables: {
      details: {
        context: "count",
        map: {
          1: "Soubor musí mít příponu {{accept}}",
          else: "Povolené přípony: {{accept}}"
        }
      }
    }
  }
}, l = {
  validationFileNameMissing: "Chybí název souboru",
  validationFileNameMismatch: "Neplatný název souboru."
}, s = {
  validationFileSizeUnderflow: "Tento soubor je příliš malý. Minimální velikost je {{minSize}} {{minSizeUnit}}.",
  validationFileSizeOverflow: "Tento soubor je příliš velký. Maximální velikost je {{maxSize}} {{maxSizeUnit}}."
}, r = {
  validationListSizeUnderflow: "Celková velikost souborů je příliš malá. Minimální celková velikost je {{minSize}} {{minSizeUnit}}.",
  validationListSizeOverflow: "Celková velikost souborů je příliš velká. Maximální celková velikost je {{maxSize}} {{maxSizeUnit}}."
}, m = {
  validationMediaSizeUnavailable: "Nelze přečíst velikost média.",
  validationMediaWidthRangeMismatch: "Šířka {{fileMainType}} není platná. Šířka musí být mezi {{minWidth}} a {{maxWidth}} {{maxWidthUnit}}.",
  validationMediaWidthUnderflow: "{{fileMainType}} je příliš malý. Minimální šířka je {{minWidth}} {{minWidthUnit}}.",
  validationMediaWidthOverflow: "{{fileMainType}} je příliš velký. Maximální šířka je {{maxWidth}} {{maxWidthUnit}}.",
  validationMediaHeightRangeMismatch: "Výška {{fileMainType}} není platná. Výška musí být mezi {{minHeight}} a {{maxHeight}} {{maxHeightUnit}}.",
  validationMediaHeightUnderflow: "{{fileMainType}} je příliš malý. Minimální výška je {{minHeight}} {{minHeightUnit}}.",
  validationMediaHeightOverflow: "{{fileMainType}} je příliš velký. Maximální výška je {{maxHeight}} {{maxHeightUnit}}.",
  validationMediaResolutionRangeMismatch: "Rozlišení je neplatné. Musí být mezi {{minResolution}}MP a {{maxResolution}}MP.",
  validationMediaResolutionUnderflow: "Rozlišení je příliš nízké. Minimum {{minResolution}}MP.",
  validationMediaResolutionOverflow: "Rozlišení je příliš vysoké. Maximum {{maxResolution}}MP."
}, d = {
  validationListEntryCountUnderflow: "V seznamu je příliš málo souborů. Minimální počet je {{minFiles}} {{minFilesUnit}}.",
  validationListEntryCountOverflow: "V seznamu je příliš mnoho souborů. Maximální počet je {{maxFiles}} {{maxFilesUnit}}."
}, u = {
  ...s,
  ...t,
  ...n,
  ...l,
  ...m,
  ...r,
  ...d
}, p = {
  ...e,
  ...o,
  ...i,
  ...u,
  ...a
};
export {
  e as core,
  p as locale,
  i as media,
  o as store,
  a as transform,
  u as validation,
  n as validationFileExtension,
  t as validationFileMimeType,
  l as validationFileName,
  s as validationFileSize,
  d as validationListCount,
  r as validationListSize,
  m as validationMediaResolution
};
