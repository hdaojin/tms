/*!
* FilePond v5.0.0-beta.63
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { createTaskScheduler as D } from "./taskScheduler.js";
import { pubsub as G } from "../utils/pubsub.js";
import { isArray as I } from "../utils/test.js";
import { arrayItemsEqual as H, arrayRemoveInPlace as J, arraySortByItemProp as L } from "../utils/array.js";
function Z(A) {
  const { entryTree: c } = A, { on: l, pub: p } = G(), a = [], { insertEntries: v, replaceEntry: C, updateEntry: j, removeEntries: q } = c, x = D({ log: void 0 }), u = {
    extension: {}
  };
  function S(n, s) {
    u.extension[n] = {
      ...g(n),
      ...s
    }, p("updateExtensionState", u.extension);
  }
  function g(n) {
    return u.extension[n] ?? {};
  }
  function M(n) {
    delete u.extension[n], p("updateExtensionState", u.extension);
  }
  function O(n, s) {
    S(n, { status: s });
  }
  function W(n) {
    return u.extension[n].status;
  }
  c.on("removeEntry", ({ entry: n }) => {
    x.abortTasks(n.id);
  });
  function B(n) {
    const s = (e, o) => e === "updateExtensionState" ? l(e, o) : c.on(e, o), i = [], t = { current: void 0 };
    t.current = n({
      // events
      on: s,
      // get root extension state
      setExtensionState: r((e) => {
        S(t.current.name, e);
      }),
      getExtensionState: r(() => g(t.current.name)),
      // get root extension status
      setExtensionStatus: r(
        (e) => O(t.current.name, e)
      ),
      // @ts-ignore
      getExtensionStatus: r(() => W(t.current.name)),
      pushTask: function(e, o, f) {
        const z = y(
          t.current.name
        );
        c.findEntries(e) && x.pushTask(e, o, {
          // set order to factor of 100 so in theory there's plenty room for adding manual order
          order: z.index * 100,
          // when params is a function it is called on run task
          params: () => [c.findEntries(e)],
          // add custom options
          ...f
        });
      },
      abortTask: function(e, o) {
        x.abortTask(e, o);
      },
      abortTasks: (e) => {
        x.abortTasks(e);
      },
      setEntries: function(e) {
        c.entries = e;
      },
      getEntries: () => c.entries,
      // manipulating entry list
      insertEntries: v,
      removeEntries: q,
      replaceEntry: C,
      updateEntry: j
    });
    function r(e) {
      return (...o) => {
        if (t.current)
          return e(...o);
        i.push([e, o]);
      };
    }
    return i.forEach(([e, o]) => {
      e(...o);
    }), t.current;
  }
  function h() {
    x.abortTasks(), a.map(P), a.length = 0;
  }
  function P(n) {
    n.instance.destroy(), M(n.instance.name);
  }
  const b = {
    // subscribe to events
    on: l,
    get extensions() {
      return a.map(({ factory: n }) => n);
    },
    set extensions(n) {
      if (!I(n))
        return;
      const s = n.map(
        (t) => Array.isArray(t) ? t[0] : t
      );
      if (H(s, b.extensions)) {
        for (const t of n) {
          if (!I(t))
            continue;
          const r = a.find((e) => t[0] === e.factory);
          E(r, t[1]);
        }
        return;
      }
      n.length === 0 && (d.clear(), h());
      for (const t of a)
        if (!s.includes(t.factory)) {
          P(t), J(a, (r) => r === t);
          continue;
        }
      for (const [t, r] of Object.entries(s)) {
        const e = parseInt(t, 10), o = a.find((f) => r === f.factory);
        if (o) {
          if (o.index = e, Array.isArray(n[e])) {
            const f = n[e][1];
            E(o, f);
          }
          continue;
        }
        if (a.push({
          index: e,
          factory: r,
          instance: B(r)
        }), Array.isArray(n[e])) {
          const f = n[e][1];
          E(a.at(-1), f);
        }
      }
      L(a, "index"), Object.entries(d.get("*") ?? []).forEach(
        ([t, r]) => {
          k(t, r);
        }
      );
      for (const [t, r] of d)
        t !== "*" && T(t, r);
      const i = a.map((t) => t.instance.name);
      p("setExtensions", { extensionNames: i }), c.entries = [...c.entries];
    },
    propagateExtensionProperty: k,
    setExtensionProperties: T,
    getExtensionProperties: K,
    // access manager state
    getState() {
      return u.extension;
    },
    // destroy FilePond instance
    destroy() {
      h();
    }
  };
  function k(n, s) {
    const i = { [n]: s }, t = R(n);
    for (const r of t)
      E(r, i);
    m("*", i);
  }
  function T(n, s) {
    const i = y(n);
    i ? E(i, s) : m(n, s);
  }
  function K(n) {
    const s = y(n);
    if (!s)
      return;
    const { instance: i } = s;
    if (i)
      return i.getProps();
  }
  function E(n, s) {
    s && (n.instance.setProps(s), m(n.instance.name, s));
  }
  function R(n) {
    return a.filter((s) => s.instance.getPropertyKeys().includes(n));
  }
  function y(n) {
    return a.find((s) => s.instance.name === n);
  }
  const d = /* @__PURE__ */ new Map();
  function m(n, s) {
    d.set(n, {
      ...d.get(n),
      ...s
    });
  }
  return b;
}
export {
  Z as createExtensionManager
};
