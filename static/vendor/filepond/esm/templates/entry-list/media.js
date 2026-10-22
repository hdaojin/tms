/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import "../../elements/FilePondEntryList/components/MediaVideo/index.js";
import { createEntryMatcher as M, createButton as d, hasExtensionWithStatusCode as m, createDefaultSpringElement as a, createSpringPane as l, whenEntryIs as f, whenEntryHasAction as R, whenEntryNotHasStatus as T, getExtensionByAction as O, hasExtensionWithProp as A } from "../common/index.js";
import "../../elements/components/RangeInput/index.js";
import { supportsRequestFullscreen as v } from "../../utils/support.js";
import { toTime as C } from "../../utils/date.js";
import { withNodeTree as c } from "../../elements/common/nodeTree.js";
import { boolToAttributeValue as b } from "../../utils/dom.js";
import "../../elements/FilePondEntryList/components/EntryActivityIndicator/index.js";
import "../../elements/FilePondEntryList/components/MediaImage/index.js";
import "../../elements/components/ElementPane/index.js";
import "../../elements/components/TimeIndicator/index.js";
import { passthrough as u } from "../../utils/placeholder.js";
import { EMPTY_OBJECT as y } from "../../utils/object.js";
import P from "../../elements/FilePondEntryList/components/EntryActivityIndicator/index-svelte.js";
import _ from "../../elements/FilePondEntryList/components/MediaVideo/index-svelte.js";
import F from "../../elements/components/ElementPane/index-svelte.js";
import B from "../../elements/FilePondEntryList/components/MediaImage/index-svelte.js";
import I from "../../elements/components/RangeInput/index-svelte.js";
import N from "../../elements/components/TimeIndicator/index-svelte.js";
function k(e) {
  const { action: t = "editMedia" } = e ?? {};
  return {
    key: "button-media-edit",
    component: P,
    props: ({ id: n, entry: r }, { updateEntryState: i }) => ({
      buttonPart: "media-button",
      states: [
        {
          // waiting for transform
          codes: [
            "TRANSFORM_IDLE",
            "TRANSFORM_CANCEL",
            "TRANSFORM_COMPLETE",
            "TRANSFORM_BUSY",
            "TRANSFORM_ERROR"
          ],
          button: d("button-transform-activate", {
            icon: "mediaEdit",
            disabled: m(r, [
              "STORE_QUEUED",
              "STORE_BUSY",
              "TRANSFORM_BUSY"
            ]),
            onclick: () => i?.(n, { [t]: !0 })
          })
        },
        {
          codes: ["TRANSFORM_PREPARE"],
          progress: !0,
          button: d("button-transform-abort", {
            icon: "abort",
            disabled: m(r, [
              "STORE_QUEUED",
              "STORE_BUSY",
              "TRANSFORM_BUSY",
              "TRANSFORM_ERROR"
            ]),
            onclick: () => i(n, {
              [t]: null
            })
          })
        }
      ]
    })
  };
}
function E(e) {
  const { action: t = "editMedia" } = e ?? {};
  return d("button-media-reset", {
    props: ({ id: n, entry: r }, { updateEntryState: i }) => ({
      part: "media-button",
      disabled: m(r, [
        "STORE_QUEUED",
        "STORE_BUSY",
        "TRANSFORM_PREPARE",
        "TRANSFORM_BUSY"
      ]) || !O(r, t)?.input,
      icon: "mediaReset",
      label: "reset",
      title: "reset",
      onclick: () => i?.(n, { [t]: !1 })
    })
  });
}
function h(e) {
  return {
    key: e,
    component: F,
    data: (t) => t ? { ...t, ...g(t) } : {},
    spring: ({ visualRect: t, media: n }) => ({
      opacity: {
        instant: n?.isCached,
        value: t?.height > 0 ? 1 : 0,
        config: {
          stiffness: 0.1,
          damping: 0.85,
          precision: 0.1
        }
      }
    }),
    props: ({ visualRect: t, opacity: n }) => ({
      part: "media-pane",
      class: "media-pane",
      width: t.width,
      height: t.height,
      opacity: n
    })
  };
}
function U(e) {
  const { objectFit: t = void 0 } = e ?? {};
  return a({
    key: "entry-image-spring",
    props: {
      class: "entry-media",
      part: "entry-media",
      // propagate visualRect
      beforeRenderChildren: u
    },
    children: [
      {
        key: "entry-image",
        component: B,
        data: !1,
        props: e
      },
      {
        if: {
          test: () => t === "contain",
          then: h("entry-image-pane")
        }
      },
      l({
        key: "entry-image-overlay",
        class: "media-overlay",
        part: "media-overlay"
      })
    ]
  });
}
function g({ entry: e }) {
  const { media: t, video: n } = e.extensionState.EntryListView || {};
  return {
    media: t,
    video: n
  };
}
function w(e) {
  const { objectFit: t = void 0 } = e ?? {};
  return a({
    key: "entry-video-spring",
    props: {
      class: "entry-media",
      part: "entry-media",
      beforeRenderChildren: u
    },
    children: [
      {
        key: "entry-video",
        component: _,
        props: e
      },
      {
        if: {
          test: () => t === "contain",
          then: h("entry-video-pane")
        }
      },
      l({
        key: "entry-video-overlay",
        class: "media-overlay",
        part: "media-overlay"
      })
    ]
  });
}
function V(e) {
  const { key: t, justifyContent: n } = e || {}, r = "media-control-group" + (n ? ` justify-content-${n}` : "");
  return c(
    a({
      key: t,
      props: {
        subtag: "element-stack",
        class: r,
        // pass visualRect to children
        beforeRenderChildren: u
      },
      children: [
        l({
          key: "media-control-group-background",
          class: "media-control-pane"
        })
      ]
    })
  );
}
function p(e) {
  const { key: t } = e || {};
  return c(
    a({
      key: t,
      props: {
        subtag: "element-stack",
        class: "media-control",
        // pass visualRect to children
        beforeRenderChildren: u
      },
      children: [
        l({
          key: "media-control-background",
          class: "media-control-pane"
        })
      ]
    })
  );
}
function S(e) {
  const { key: t = "media-controls", justifyContent: n } = e || {}, r = "entry-media-controls" + (n ? ` justify-content-${n}` : "");
  return c({
    if: {
      test: ({ entry: i }) => {
        const { media: o } = g({ entry: i });
        return o && o.isReady;
      },
      then: {
        key: t,
        tag: "element-stack",
        data: (i = y) => ({ ...i, ...g(i) }),
        attrs: (i) => {
          const { media: o, video: s } = i;
          return {
            class: r,
            part: "media-controls",
            "data-media-is-visible": b(o?.isVisible),
            "data-media-is-playing": b(s?.isPlaying)
          };
        }
      }
    }
  });
}
function L() {
  return a({
    key: "toggle-playback-spring",
    props: {
      class: "toggle-playback"
    },
    children: d("toggle-playback", ({ video: e }) => ({
      part: "media-button",
      icon: e?.isPaused ? "mediaPlay" : "mediaPause"
    }))
  });
}
function Y() {
  return a({
    key: "toggle-audio-spring",
    props: {
      class: "toggle-audio"
    },
    children: d("toggle-audio", ({ video: e }) => ({
      part: "media-button",
      icon: e?.isMute ? "mediaSilent" : e?.isMuted ? "mediaUnmute" : "mediaMute",
      disabled: e?.isMute
    }))
  });
}
function de() {
  return {
    // only added when fullscreen is supported
    if: {
      test: v,
      then: a({
        key: "toggle-fullscreen-spring",
        props: {
          class: "toggle-fullscreen"
        },
        children: d("toggle-fullscreen", {
          part: "media-button",
          icon: "mediaFullscreen"
        })
      })
    }
  };
}
function j() {
  return a({
    key: "media-scrubber-spring",
    props: {
      class: "media-scrubber"
    },
    children: [
      {
        key: "media-scrubber",
        component: I,
        data: ({ video: e } = y) => ({ video: e }),
        props: ({ video: e }) => ({
          part: "media-scrubber",
          step: e?.framesPerSecond,
          value: e?.time,
          min: 0,
          max: e?.duration
        })
      }
    ]
  });
}
function ce() {
  return {
    key: "media-scrubber-title",
    tag: "time",
    data: ({ hoverValue: e }) => ({
      time: C(e)
    }),
    attrs: ({ time: e }) => ({
      datetime: e
    }),
    children: "{{time}}"
  };
}
function x() {
  return a({
    key: "media-time-indicator-spring",
    props: {
      class: "media-time-indicator"
    },
    children: {
      key: "media-time-indicator",
      component: N,
      data: ({ video: e } = y) => ({ video: e }),
      props: ({ video: e }) => ({
        timeISO: e?.timeISO,
        timeLabel: e?.timeLabel,
        durationISO: e?.durationISO,
        durationLabel: e?.durationLabel
      })
    }
  });
}
const Q = M("image");
function pe(e, t) {
  const { enableEdit: n = !0, enableReset: r = !0, ...i } = t ?? {}, o = n || r;
  return c(e).find("entry").append(
    f((s) => Q(s) || A(s, "poster")).append(
      U(i),
      o && R("editMedia").append(
        S({ justifyContent: "end" }).append(
          r && p().append(E()),
          n && p().append(k())
        )
      )
    )
  ), e;
}
function le(e, t) {
  const { enableEdit: n = !0, enableReset: r = !0, ...i } = t ?? {}, o = n || r;
  return c(e).update("entry", (s) => {
    s.routes = {
      "toggle-playback:click": "entry-video.togglePlayback",
      "toggle-audio:click": "entry-video.toggleAudio",
      "toggle-fullscreen:click": "entry-video.toggleFullscreen",
      "media-scrubber:input": "entry-video.setCurrentTime"
    };
  }).append(
    f("video").append(
      w(i),
      T("error").append(
        S().append(
          V({ key: "video-controls" }).append(
            L(),
            j(),
            x(),
            Y()
          ),
          o && R("editMedia").append(
            r && p().append(E()),
            n && p().append(k())
          )
        )
      )
    )
  ), e;
}
export {
  pe as appendEntryImageView,
  le as appendEntryVideoView,
  k as createEditMediaButton,
  U as createImageView,
  p as createMediaControl,
  V as createMediaControlGroup,
  S as createMediaControls,
  j as createMediaScrubber,
  ce as createMediaScrubberTitle,
  x as createMediaTimeIndicator,
  E as createResetMediaButton,
  Y as createToggleAudioButton,
  de as createToggleFullscreenButton,
  L as createTogglePlaybackButton,
  w as createVideoView
};
