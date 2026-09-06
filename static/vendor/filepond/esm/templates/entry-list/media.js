/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import "../../elements/FilePondEntryList/components/MediaVideo/index.js";
import { createEntryMatcher as S, createButton as s, hasExtensionWithStatusCode as u, createDefaultSpringElement as a, createSpringPane as l, whenEntryIs as y, whenEntryHasAction as b, whenEntryNotHasStatus as M, getExtensionByAction as h, hasExtensionWithProp as T } from "../common/index.js";
import "../../elements/components/RangeInput/index.js";
import { supportsRequestFullscreen as O } from "../../utils/support.js";
import { toTime as A } from "../../utils/date.js";
import { withNodeTree as c } from "../../elements/common/nodeTree.js";
import { boolToAttributeValue as m } from "../../utils/dom.js";
import "../../elements/FilePondEntryList/components/MediaTimeIndicator/index.js";
import "../../elements/FilePondEntryList/components/EntryActivityIndicator/index.js";
import "../../elements/FilePondEntryList/components/MediaImage/index.js";
import "../../elements/components/ElementPane/index.js";
import v from "../../elements/FilePondEntryList/components/EntryActivityIndicator/index-svelte.js";
import F from "../../elements/FilePondEntryList/components/MediaVideo/index-svelte.js";
import P from "../../elements/components/ElementPane/index-svelte.js";
import _ from "../../elements/FilePondEntryList/components/MediaImage/index-svelte.js";
import I from "../../elements/components/RangeInput/index-svelte.js";
import B from "../../elements/FilePondEntryList/components/MediaTimeIndicator/index-svelte.js";
function f(e) {
  const { action: t = "editMedia" } = e ?? {};
  return {
    key: "button-media-edit",
    component: v,
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
          button: s("button-transform-activate", {
            icon: "mediaEdit",
            disabled: u(r, [
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
          button: s("button-transform-abort", {
            icon: "abort",
            disabled: u(r, [
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
function R(e) {
  const { action: t = "editMedia" } = e ?? {};
  return s("button-media-reset", {
    props: ({ id: n, entry: r }, { updateEntryState: i }) => ({
      part: "media-button",
      disabled: u(r, [
        "STORE_QUEUED",
        "STORE_BUSY",
        "TRANSFORM_PREPARE",
        "TRANSFORM_BUSY"
      ]) || !h(r, t)?.input,
      icon: "mediaReset",
      label: "reset",
      title: "reset",
      onclick: () => i?.(n, { [t]: !1 })
    })
  });
}
function k(e) {
  return {
    key: e,
    component: P,
    spring: ({ visualRect: t }) => ({
      opacity: {
        value: t.height > 0 ? 1 : 0,
        config: {
          stiffness: 0.02,
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
function N(e) {
  const { objectFit: t = void 0 } = e ?? {};
  return a({
    key: "entry-image-spring",
    props: {
      class: "entry-media",
      part: "entry-media"
    },
    children: [
      {
        key: "entry-image",
        component: _,
        props: e
      },
      {
        if: {
          test: () => t === "contain",
          then: k("entry-image-pane")
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
function U(e) {
  const { objectFit: t = void 0 } = e ?? {};
  return a({
    key: "entry-video-spring",
    props: {
      class: "entry-media",
      part: "entry-media"
    },
    children: [
      {
        key: "entry-video",
        component: F,
        props: e
      },
      {
        if: {
          test: () => t === "contain",
          then: k("entry-video-pane")
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
function C(e) {
  const { key: t, justifyContent: n } = e || {}, r = "media-control-group" + (n ? ` justify-content-${n}` : "");
  return c(
    a({
      key: t,
      props: {
        subtag: "element-stack",
        class: r
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
        class: "media-control"
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
function E(e) {
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
        context: g,
        attrs: ({ media: i, video: o }) => ({
          class: r,
          part: "media-controls",
          "data-media-is-visible": m(i?.isVisible),
          "data-media-is-playing": m(o?.isPlaying)
        })
      }
    }
  });
}
function w() {
  return a({
    key: "toggle-playback-spring",
    props: {
      class: "toggle-playback"
    },
    children: s("toggle-playback", ({ video: e }) => ({
      part: "media-button",
      icon: e?.isPaused ? "mediaPlay" : "mediaPause"
    }))
  });
}
function V() {
  return a({
    key: "toggle-audio-spring",
    props: {
      class: "toggle-audio"
    },
    children: s("toggle-audio", ({ video: e }) => ({
      part: "media-button",
      icon: e?.isMute ? "mediaSilent" : e?.isMuted ? "mediaUnmute" : "mediaMute",
      disabled: e?.isMute
    }))
  });
}
function ie() {
  return {
    // only added when fullscreen is supported
    if: {
      test: O,
      then: a({
        key: "toggle-fullscreen-spring",
        props: {
          class: "toggle-fullscreen"
        },
        children: s("toggle-fullscreen", {
          part: "media-button",
          icon: "mediaFullscreen"
        })
      })
    }
  };
}
function x() {
  return a({
    key: "media-scrubber-spring",
    props: {
      class: "media-scrubber"
    },
    children: [
      {
        key: "media-scrubber",
        component: I,
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
function ae() {
  return {
    key: "media-scrubber-title",
    tag: "time",
    context: ({ hoverValue: e }) => ({
      time: A(e)
    }),
    attrs: ({ time: e }) => ({
      datetime: e
    }),
    children: "{{time}}"
  };
}
function L() {
  return a({
    key: "media-time-indicator-spring",
    props: {
      class: "media-time-indicator"
    },
    children: {
      key: "media-time-indicator",
      component: B,
      props: ({ video: e }) => ({
        timeISO: e?.timeISO,
        timeLabel: e?.timeLabel,
        durationISO: e?.durationISO,
        durationLabel: e?.durationLabel
      })
    }
  });
}
const j = S("image");
function oe(e, t) {
  const { enableEdit: n = !0, enableReset: r = !0, ...i } = t ?? {}, o = n || r;
  return c(e).find("entry").append(
    y((d) => j(d) || T(d, "poster")).append(
      N(i),
      o && b("editMedia").append(
        E({ justifyContent: "end" }).append(
          r && p().append(R()),
          n && p().append(f())
        )
      )
    )
  ), e;
}
function se(e, t) {
  const { enableEdit: n = !0, enableReset: r = !0, ...i } = t ?? {}, o = n || r;
  return c(e).update("entry", (d) => {
    d.routes = {
      "toggle-playback:click": "entry-video.togglePlayback",
      "toggle-audio:click": "entry-video.toggleAudio",
      "toggle-fullscreen:click": "entry-video.toggleFullscreen",
      "media-scrubber:input": "entry-video.setCurrentTime"
    };
  }).append(
    y("video").append(
      U(i),
      M("error").append(
        E().append(
          C({ key: "video-controls" }).append(
            w(),
            x(),
            L(),
            V()
          ),
          o && b("editMedia").append(
            r && p().append(R()),
            n && p().append(f())
          )
        )
      )
    )
  ), e;
}
export {
  oe as appendEntryImageView,
  se as appendEntryVideoView,
  f as createEditMediaButton,
  N as createImageView,
  p as createMediaControl,
  C as createMediaControlGroup,
  E as createMediaControls,
  x as createMediaScrubber,
  ae as createMediaScrubberTitle,
  L as createMediaTimeIndicator,
  R as createResetMediaButton,
  V as createToggleAudioButton,
  ie as createToggleFullscreenButton,
  w as createTogglePlaybackButton,
  U as createVideoView
};
