/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { withNodeTree as S } from "../../elements/common/nodeTree.js";
import { isDataTransferEntry as f, isFileEntry as g, isString as b, isNumber as U } from "../../utils/test.js";
import { bytesToNaturalFileSize as A } from "../../utils/file.js";
import { fade as D } from "../../elements/common/transition.js";
import { quadInOut as B } from "../../vendor/svelte/src/easing/index.js";
import { hasExtensionWithStatusCode as s, createDefaultSpringElement as E, createButton as l, hasExtensionWithAction as L, getExtensionStatusWithCode as R } from "../common/index.js";
import { cache as Y } from "../../utils/cache.js";
import "../../elements/components/BooleanInput/index.js";
import "../../elements/components/ElementSkeleton/index.js";
import "../../elements/components/FilenameInput/index.js";
import "../../elements/FilePondEntryList/components/EntryActivityIndicator/index.js";
import "../../elements/FilePondEntryList/components/EntryStatus/index.js";
import "../../elements/FilePondEntryList/components/EntryList/index.js";
import "../../elements/FilePondEntryList/components/EntryListItem/index.js";
import "../../elements/FilePondEntryList/components/Entry/index.js";
import $ from "../../elements/FilePondEntryList/components/EntryListItemPlaceholder/index-svelte.js";
import { toSpaceSeparatedString as u } from "../../elements/common/string.js";
import { EMPTY_OBJECT as c } from "../../utils/object.js";
import F from "../../elements/FilePondEntryList/components/EntryListItem/index-svelte.js";
import v from "../../elements/FilePondEntryList/components/EntryList/index-svelte.js";
import P from "../../elements/FilePondEntryList/components/Entry/index-svelte.js";
import M from "../../elements/FilePondEntryList/components/EntryStatus/index-svelte.js";
import d from "../../elements/components/ElementSkeleton/index-svelte.js";
import O from "../../elements/FilePondEntryList/components/EntryActivityIndicator/index-svelte.js";
import C from "../../elements/components/BooleanInput/index-svelte.js";
import N from "../../elements/components/FilenameInput/index-svelte.js";
function Tt() {
  return [
    {
      key: "entry-list",
      component: v,
      props: ({ entries: t }) => ({
        part: "entry-list",
        entries: t
      }),
      item: {
        if: {
          test: ({ isPlaceholder: t }) => t,
          then: {
            component: $,
            props: ({ id: t, index: e, onmeasureitem: r }) => ({
              id: t,
              index: e,
              part: "entry-list-item-placeholder",
              onmeasureitem: r
            })
          }
        },
        else: {
          key: "entry-list-item",
          component: F,
          props: ({
            id: t,
            index: e,
            entry: r,
            ariaId: n,
            isDetached: o,
            isRemoving: i,
            isDraggable: a,
            isDragging: T,
            isLastDraggedItem: _,
            translation: h,
            onmeasureitem: k
          }) => ({
            id: t,
            index: e,
            part: f(r) ? "entry-list-item data-transfer-item" : "entry-list-item file-item",
            class: "entry-list-item",
            entry: r,
            isDetached: o,
            isRemoving: i,
            isDraggable: a,
            isDragging: T,
            isLastDraggedItem: _,
            translation: h,
            onmeasureitem: k,
            ariaDescribedby: u(
              `${n}-status`,
              `${n}-store-info`
            )
          }),
          children: z()
        }
      }
    }
  ];
}
function z() {
  return {
    key: "entry",
    component: P,
    props: ({ entry: t, ariaId: e }) => ({
      legendId: `${e}-name`,
      part: f(t) ? "entry entry-data-transfer" : "entry"
    }),
    data: ({ id: t, ariaId: e, entry: r } = c) => ({
      id: t,
      ariaId: e,
      entry: r
    }),
    children: [
      Z(),
      {
        if: {
          test: ({ entry: t }) => f(t),
          then: x()
        },
        elseif: {
          test: ({ entry: t }) => g(t),
          then: I()
        }
      },
      w(),
      Q()
    ]
  };
}
function m(t, e, { main: r, sub: n }) {
  return {
    if: {
      test: ({ entry: o }) => s(o, e),
      then: {
        key: t,
        tag: "element-stack",
        attrs: {
          layout: "col"
        },
        children: [
          b(r) ? {
            key: `${t}-main`,
            tag: "div",
            attrs: {
              class: "entry-info-main"
            },
            children: r
          } : r,
          {
            key: `${t}-sub`,
            tag: "div",
            attrs: {
              class: "entry-info-sub"
            },
            children: n
          }
        ]
      }
    }
  };
}
function I() {
  return E({
    key: "entry-info",
    props: {
      class: "entry-info",
      part: "entry-info",
      subtag: "element-stack",
      subattrs: {
        layout: "split"
      }
    },
    children: [W(), q()]
  });
}
function x() {
  return E({
    key: "data-transfer-info",
    props: {
      class: "entry-info",
      part: "entry-info data-transfer-info",
      subtag: "element-stack",
      subattrs: {
        layout: "col"
      }
    },
    // adds { processedFiles, totalFiles } values to dataset
    data: ({ entry: t } = c) => {
      const e = R(t, "LOAD_BUSY");
      return {
        processedFiles: e?.values?.processed,
        totalFiles: e?.values?.total
      };
    },
    children: [
      {
        key: "data-transfer-info-main",
        tag: "div",
        attrs: {
          class: "entry-info-main"
        },
        children: "loadDataTransferProgress"
      },
      {
        key: "data-transfer-info-sub",
        tag: "div",
        attrs: {
          class: "entry-info-sub"
        },
        children: "loadDataTransferInfo"
      }
    ]
  });
}
function Q() {
  return {
    key: "entry-status",
    component: M,
    props: ({ ariaId: t }) => ({
      part: "entry-status",
      class: "entry-status",
      id: `${t}-status`
    })
  };
}
function W() {
  return {
    key: "file-info",
    tag: "element-stack",
    // adds { isWaiting, isFrozen } props to dataset
    data: (t = c) => {
      const { entry: e } = t, r = s(e, [
        "LOAD_QUEUED",
        "LOAD_BUSY",
        "STORE_RESTORE_BUSY"
      ]), n = s(e, [
        "LOAD_ERROR",
        "STORE_RESTORE_ERROR"
      ]);
      return {
        name: e.name,
        size: e.size,
        isWaiting: r,
        isFrozen: n
      };
    },
    attrs: {
      layout: "col"
    },
    children: [
      {
        key: "file-info-main",
        component: d,
        props: ({ isWaiting: t, isFrozen: e }) => ({
          class: "entry-info-main",
          part: "entry-info-main",
          isWaiting: t,
          isFrozen: e
        }),
        children: "{{name}}"
      },
      {
        key: "file-info-sub",
        component: d,
        // adds { size, sizeUnit } props to dataset and retains { isWaiting, isFrozen }
        data: ({ size: t, isWaiting: e, isFrozen: r } = c, { byteUnits: n } = c) => {
          if (!U(t))
            return c;
          const o = Y(A, [t, { byteUnits: n }]), [i, a] = o.split(" ");
          return {
            sizeNatural: i,
            sizeUnit: `unit${a}`,
            isWaiting: e,
            isFrozen: r
          };
        },
        props: ({ isWaiting: t, isFrozen: e }) => ({
          class: "entry-info-sub",
          part: "entry-info-sub",
          isWaiting: t,
          isFrozen: e
        }),
        children: "{{sizeNatural}} {{sizeUnit}}"
      }
    ]
  };
}
const p = ({ ariaId: t }) => ({
  id: `${t}-store-info`,
  class: "entry-info-main"
});
function q() {
  return E({
    key: "file-store-spring",
    props: {
      subtag: "element-stack",
      subattrs: {
        layout: "pile"
      }
    },
    transition: {
      fn: D,
      duration: 150,
      easing: B,
      when: ({ entry: t }) => s(t, [
        "STORE_QUEUED",
        "STORE_BUSY",
        "STORE_COMPLETE"
      ])
    },
    children: [
      m("file-store-queued-info", ["STORE_QUEUED"], {
        main: {
          key: "file-store-queued-info-main",
          tag: "div",
          attrs: p,
          children: "storeStorageQueued"
        },
        sub: "assistAbort"
      }),
      m("file-store-busy-info", ["STORE_BUSY"], {
        sub: "assistAbort",
        main: {
          key: "file-store-busy-info-main",
          tag: "div",
          data: ({ entry: t } = c) => {
            const { progress: e } = R(t, "STORE_BUSY") ?? {};
            return {
              progress: e
            };
          },
          spring: ({ progress: t }) => ({
            progress: {
              value: t === 1 / 0 ? 0 : t,
              transform: (e) => Math.round(e * 100)
            }
          }),
          attrs: p,
          children: "storeStorageProgress"
        }
      }),
      m("file-store-complete-info", ["STORE_COMPLETE"], {
        main: {
          key: "file-store-complete-info-main",
          tag: "div",
          attrs: p,
          children: "storeStorageComplete"
        },
        sub: "assistUndo"
      })
    ]
  });
}
function Z() {
  return {
    key: "entry-load-state",
    component: O,
    props: ({ id: t, ariaId: e, entry: r }, { updateEntryState: n, removeEntries: o }) => ({
      class: "entry-load-state",
      part: "entry-load-state",
      buttonPart: "entry-button",
      states: [
        {
          codes: ["LOAD_QUEUED", "LOAD_BUSY", "STORE_RESTORE_BUSY"],
          progress: !0,
          button: l("button-load-abort", {
            title: "abort",
            icon: "remove",
            disabled: s(r, ["TRANSFORM_BUSY"]),
            onclick: () => {
              n(t, { abort: !0 });
            },
            ariaDescribedby: `${e}-name`
          })
        },
        {
          codes: [
            // `null`: can still remove items without extensions, "dummy files"
            null,
            "LOAD_ERROR",
            "LOAD_COMPLETE",
            "STORE_RESTORE_COMPLETE",
            "STORE_RESTORE_ERROR"
          ],
          button: l("button-entry-remove", {
            icon: "remove",
            disabled: s(r, ["TRANSFORM_BUSY"]),
            onclick: () => {
              o(t);
            },
            ariaDescribedby: u(
              `${e}-name`,
              `${e}-status`
            )
          })
        }
      ]
    })
  };
}
function w() {
  return {
    key: "entry-store-state",
    component: O,
    props: ({ id: t, ariaId: e, entry: r }, { updateEntryState: n }) => ({
      class: "entry-store-state",
      part: "entry-store-state",
      buttonPart: "entry-button",
      states: [
        {
          codes: [
            "STORE_READY",
            "STORE_ABORT",
            "STORE_ERROR",
            "STORE_RELEASE_COMPLETE",
            "STORE_RELEASE_ABORT"
          ],
          button: l("button-store-idle", {
            icon: "store",
            disabled: s(r, ["TRANSFORM_BUSY"]),
            styles: y({
              intro: "translateY(0.125em)",
              idle: "translateY(0)",
              outro: "translateY(-0.125em)"
            }),
            onclick: () => {
              n(t, {
                store: !0
              });
            },
            ariaDescribedby: `${e}-name`
          })
        },
        {
          codes: ["STORE_QUEUED", "STORE_BUSY"],
          progress: !0,
          button: l("button-store-busy", {
            icon: "abort",
            disabled: s(r, ["TRANSFORM_BUSY"]),
            onclick: () => {
              n(t, {
                abort: !0
              });
            },
            ariaDescribedby: u(
              `${e}-name`,
              `${e}-store-info`
            )
          })
        },
        {
          codes: ["STORE_RELEASE_BUSY"],
          progress: {
            direction: "reverse"
          },
          button: l("button-store-busy", {
            icon: "abort",
            disabled: s(r, ["TRANSFORM_BUSY"]),
            onclick: () => {
              n(t, {
                abort: !0
              });
            },
            ariaDescribedby: `${e}-name`
          })
        },
        {
          codes: ["STORE_COMPLETE", "STORE_RESTORE_COMPLETE", "STORE_RELEASE_ABORT"],
          button: l("button-store-complete", {
            icon: "revert",
            styles: y({
              intro: "rotateZ(45deg)",
              idle: "rotateZ(0)",
              outro: "rotaetZ(-45deg)"
            }),
            disabled: s(r, ["TRANSFORM_BUSY"]),
            onclick: () => {
              n(t, {
                store: !1
              });
            },
            ariaDescribedby: u(
              `${e}-name`,
              `${e}-status`,
              `${e}-store-info`
            )
          })
        }
      ]
    })
  };
}
function y({ intro: t, idle: e, outro: r }) {
  const n = "--indicator-button-";
  return {
    [`${n}intro`]: t,
    [`${n}idle`]: e,
    [`${n}outro`]: r
  };
}
function J(t) {
  const { key: e = "entry-checkbox", stateKey: r = "checked" } = t ?? {};
  return {
    key: e,
    component: C,
    props: ({ id: n, entry: o }, { updateEntryState: i }) => ({
      class: e,
      part: e,
      icon: "check",
      label: "Select",
      labelIsImplicit: !0,
      checked: o.state[r],
      onchange: (a) => {
        i(n, {
          [r]: a
        });
      }
    })
  };
}
function K(t) {
  const { key: e = "file-rename", extensionAction: r = "renameFile" } = t ?? {};
  return {
    if: {
      test: ({ entry: n }) => b(n.name) && L(n, r),
      then: {
        key: e,
        component: N,
        props: ({ id: n, entry: o }, { updateEntryState: i }) => ({
          disabled: s(o, ["STORE_QUEUED", "STORE_BUSY"]),
          value: o.name,
          onconfirm: (a) => {
            i(n, {
              [r]: a
            });
          }
        })
      }
    },
    else: {
      key: e,
      tag: "span",
      children: "{{entry.name}}"
    }
  };
}
function _t(t) {
  return S(t).remove("entry-store-state").replace("entry-load-state", J()).update("entry-list-item", (e) => {
    const r = e.props;
    e.props = (n) => {
      const o = r(n);
      return {
        ...o,
        part: u(
          o.part,
          n.entry.state.checked ? "selected" : void 0
        )
      };
    };
  }), t;
}
function ht(t) {
  return S(t).update("file-info-main", (e) => {
    e.children = K();
  }), t;
}
export {
  _t as appendEntryCheckbox,
  ht as appendEntryRenameInput,
  J as createEntryCheckbox,
  x as createEntryDataTransferInfo,
  I as createEntryInfo,
  m as createEntryInfoBlock,
  Z as createEntryLoadState,
  Q as createEntryStatus,
  w as createEntryStoreState,
  W as createFileLoadInfo,
  z as createFilePondEntry,
  Tt as createFilePondEntryList,
  K as createFileRenameInput,
  q as createFileStoreInfo
};
