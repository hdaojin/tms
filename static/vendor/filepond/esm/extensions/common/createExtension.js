/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { warn as K } from "../../common/console.js";
import { copyDescriptors as q, isObjectValuesEqual as w } from "../../utils/object.js";
import { isString as C, isObject as D } from "../../utils/test.js";
import { Status as H } from "../../common/status.js";
function z(E) {
  const { name: n, type: i, props: u, factory: d } = E || {}, a = (c) => {
    (!C(n) || !n) && K("Extension name missing or invalid");
    function f(t) {
      return t.extensionState?.[n] ?? {};
    }
    function p(t, e) {
      return c.updateEntry(t, {
        extensionState: {
          [n]: e
        }
      });
    }
    function y(t, e) {
      return p(t, { status: e });
    }
    function x(t) {
      return f(t).status ?? {};
    }
    function S(t, e) {
      const { type: s = H.System, code: P } = e;
      return ({ lengthComputable: v, loaded: h, total: k }) => {
        t = y(t, {
          type: s,
          code: P,
          progress: v ? h / k : 1 / 0
        });
      };
    }
    let r = Object.entries(u).reduce((t, [e, s]) => (s === void 0 || (t[e] = s), t), {});
    const g = Object.keys(u);
    let m = [];
    function b(t) {
      m.push(t), t(o());
    }
    const l = d(
      // instance
      {
        // reference to current props so extension always has latest values
        props: r,
        // called when props updated (when setProps called and on init)
        didSetProps: b,
        // return name of this extension
        extensionName: n,
        // return type of this extension
        extensionType: i
      },
      {
        // merge extension manager with extension context
        ...c,
        getEntryExtensionState: f,
        setEntryExtensionState: p,
        setEntryExtensionStatus: y,
        getEntryExtensionStatus: x,
        createProgressHandler: S
      }
    );
    function j(t) {
      D(t) && (w(t, r) || (Object.assign(r, t), m.forEach((e) => e(o()))));
    }
    function o() {
      return { ...r };
    }
    function O() {
      return g;
    }
    return q(l, {
      setProps: j,
      getProps: o,
      getPropertyKeys: O,
      get name() {
        return n;
      },
      destroy() {
        l.destroy();
      }
    });
  };
  return Object.defineProperties(a, {
    name: { value: n, writable: !1 },
    type: { value: i, writable: !1 }
  }), a;
}
export {
  z as createExtension
};
