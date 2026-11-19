/*!
* FilePond v5.0.0-beta.78
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import "../../elements/components/Button/index.js";
import { supportsDialogCloseTransition as p } from "../../utils/support.js";
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
          props: (s, t) => {
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
              onclosed: l
            } = s;
            const { dialog: o } = t;
            return e || (i = i || "show-modal", n = n || o, e = function(h) {
              o.ontransitionend = function(r) {
                if (r.target === o) {
                  if (p() && !o.open && r.propertyName === "display") {
                    l?.(t);
                    return;
                  }
                  if (r.propertyName === "opacity" && r.pseudoElement === "" && o.open) {
                    d?.(t);
                    return;
                  }
                }
              }, o.ontoggle = function() {
                o.open ? f?.(t) : (g?.(t), p() || l?.(t));
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
