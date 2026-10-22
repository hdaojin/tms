/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import "../../elements/components/Button/index.js";
import { supportsDisplayTransition as s } from "../../utils/support.js";
import { getAsButtonProps as y } from "../common/index.js";
import b from "../../elements/components/Button/index-svelte.js";
function w() {
  return [
    {
      tag: "ul",
      attrs: {
        role: "list",
        part: "source-list"
      },
      item: {
        tag: "li",
        attrs: {
          role: "listitem",
          part: "source-list-item"
        },
        children: {
          component: b,
          props: (l, t) => {
            let {
              disabled: a,
              icon: m,
              label: u,
              title: c,
              onclick: e,
              command: i,
              commandfor: n,
              onopen: f,
              onopened: d,
              onclose: g,
              onclosed: p
            } = l;
            const { dialog: o } = t;
            return e || (i = i || "show-modal", n = n || o, e = function(h) {
              o.ontransitionend = function(r) {
                if (r.target === o) {
                  if (s() && !o.open && r.propertyName === "display") {
                    p?.(t);
                    return;
                  }
                  if (r.propertyName === "opacity" && r.pseudoElement === "" && o.open) {
                    d?.(t);
                    return;
                  }
                }
              }, o.ontoggle = function() {
                o.open ? f?.(t) : (g?.(t), s() || p?.(t));
              };
            }), {
              ...y({
                icon: m,
                label: u,
                title: c
              }),
              disabled: a,
              part: "source-button",
              command: i,
              commandfor: n,
              onclick: e
            };
          }
        }
      }
    }
  ];
}
export {
  w as createFilePondSourceList
};
