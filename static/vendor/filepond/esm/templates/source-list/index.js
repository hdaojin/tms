/*!
* FilePond v5.0.0-beta.63
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
              onclick: t,
              command: e,
              commandfor: n,
              onopen: u,
              onopened: f,
              onclose: d,
              onclosed: i
            } = s;
            const { dialog: o, disabled: g } = l;
            return t || (e = e || "show-modal", n = n || o, t = function(h) {
              o.ontransitionend = function(r) {
                if (p() && !o.open && r.propertyName === "display") {
                  i?.(o);
                  return;
                }
                if (r.propertyName === "opacity" && r.pseudoElement === "" && o.open) {
                  f?.(o);
                  return;
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
              command: e,
              commandfor: n,
              onclick: t
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
