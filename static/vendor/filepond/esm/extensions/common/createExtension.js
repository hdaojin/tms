/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { warn as K } from "../../common/console.js";
import { copyDescriptors as q, isObjectValuesEqual as w } from "../../utils/object.js";
import { isString as C, isObject as D } from "../../utils/test.js";
function T(m) {
  const { name: n, type: u, props: a, factory: x } = m || {}, c = (f) => {
    (!C(n) || !n) && K("Extension name missing or invalid");
    function p(t) {
      return t.extensionState?.[n] ?? {};
    }
    function y(t, e) {
      f.updateEntry(t, {
        extensionState: {
          [n]: e
        }
      });
    }
    function l(t, e) {
      y(t, { status: e });
    }
    function o(t) {
      return p(t).status ?? {};
    }
    function g(t) {
      const e = o(t), { type: s, code: P } = e ?? o(t);
      return ({ lengthComputable: v, loaded: h, total: k }) => {
        l(t, {
          type: s,
          code: P,
          progress: v ? h / k : 1 / 0
        });
      };
    }
    let r = Object.entries(a).reduce((t, [e, s]) => (s === void 0 || (t[e] = s), t), {});
    const S = Object.keys(a);
    let E = [];
    function b(t) {
      E.push(t), t(i());
    }
    const d = x(
      // instance
      {
        // reference to current props so extension always has latest values
        props: r,
        // called when props updated (when setProps called and on init)
        didSetProps: b,
        // return name of this extension
        extensionName: n,
        // return type of this extension
        extensionType: u
      },
      {
        // merge extension manager with extension context
        ...f,
        getEntryExtensionState: p,
        setEntryExtensionState: y,
        setEntryExtensionStatus: l,
        getEntryExtensionStatus: o,
        createProgressHandler: g
      }
    );
    function j(t) {
      D(t) && (w(t, r) || (Object.assign(r, t), E.forEach((e) => e(i()))));
    }
    function i() {
      return { ...r };
    }
    function O() {
      return S;
    }
    return q(d, {
      setProps: j,
      getProps: i,
      getPropertyKeys: O,
      get name() {
        return n;
      },
      destroy() {
        d.destroy();
      }
    });
  };
  return Object.defineProperties(c, {
    name: { value: n, writable: !1 },
    type: { value: u, writable: !1 }
  }), c;
}
export {
  T as createExtension
};
