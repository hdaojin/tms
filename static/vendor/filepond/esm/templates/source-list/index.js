/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import "../../elements/components/Button/index.js";
import { supportsDisplayTransition as p } from "../../utils/support.js";
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
          props: (s, l) => {
            let {
              icon: a,
              label: c,
              title: m,
              onclick: e,
              command: n,
              commandfor: r,
              onopen: u,
              onopened: f,
              onclose: d,
              onclosed: i
            } = s;
            const { dialog: o, disabled: g } = l;
            return e || (n = n || "show-modal", r = r || o, e = function(h) {
              o.ontransitionend = function(t) {
                if (t.target === o) {
                  if (p() && !o.open && t.propertyName === "display") {
                    i?.(o);
                    return;
                  }
                  if (t.propertyName === "opacity" && t.pseudoElement === "" && o.open) {
                    f?.(o);
                    return;
                  }
                }
              }, o.ontoggle = function() {
                o.open ? u?.(o) : (d?.(o), p() || i?.(o));
              };
            }), {
              ...y({
                icon: a,
                label: c,
                title: m
              }),
              disabled: g,
              part: "source-button",
              command: n,
              commandfor: r,
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
