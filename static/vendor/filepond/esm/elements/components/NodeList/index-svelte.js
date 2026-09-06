/*!
* FilePond v5.0.0-beta.66
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { get as n, untrack as Q } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { noop as x } from "../../../vendor/svelte/src/internal/shared/utils.js";
import { push as ve, pop as _e } from "../../../vendor/svelte/src/internal/client/context.js";
import { first_child as C } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { template_effect as be } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { proxy as xe } from "../../../vendor/svelte/src/internal/client/proxy.js";
import { user_derived as w } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as Ne } from "../../../vendor/svelte/src/internal/client/render.js";
import { comment as O, append as N, text as Re } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as q } from "../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { each as ne, index as Se } from "../../../vendor/svelte/src/internal/client/dom/blocks/each.js";
import { component as Ce } from "../../../vendor/svelte/src/internal/client/dom/blocks/svelte-component.js";
import { element as se } from "../../../vendor/svelte/src/internal/client/dom/blocks/svelte-element.js";
import { attribute_effect as ie } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { transition as Oe } from "../../../vendor/svelte/src/internal/client/dom/elements/transitions.js";
import { bind_this as ue } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as F, spread_props as ye } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { isSwitchNode as U, isComponentNode as ke, isElementNode as we, isTemplateNode as Pe } from "../../common/nodeTree.js";
import { isString as X, isFunction as z } from "../../../utils/test.js";
import { withResources as fe, stringReplaceVariables as je } from "../../common/string.js";
import { passthrough as Y, noop as ae } from "../../../utils/placeholder.js";
import { Spring as Te } from "../../../vendor/svelte/src/motion/spring.js";
import { arrayWrap as D } from "../../../utils/array.js";
import { getSuspensionObserver as We } from "../../common/dom.js";
function Z(ce, P) {
  ve(P, !0);
  const $ = (t, r = x, e = x, o = x, u = x, k = x, p = x, g = x, v = x, f = x) => {
    var j = O(), d = C(j);
    {
      var T = (s) => {
        var i = O(), _ = C(i);
        {
          const R = (b, h = x) => {
            {
              let S = w(() => f() ? [f()] : p()), B = w(() => K()(f() ? h() : { ...g(), ...h() })), l = w(() => f() ? {} : y());
              Z(b, {
                get nodes() {
                  return n(S);
                },
                get context() {
                  return n(B);
                },
                get routes() {
                  return n(l);
                },
                get sharedContext() {
                  return c();
                },
                get beforeSetProps() {
                  return K();
                },
                get beforeRenderNode() {
                  return M();
                }
              });
            }
          };
          let W = w(() => ({
            context: g(),
            routes: y(),
            sharedContext: c(),
            beforeSetProps: K(),
            beforeRenderNode: M()
          }));
          Ce(_, u, (b, h) => {
            ue(
              h(b, ye(k, v, {
                get nodeContext() {
                  return n(W);
                },
                children: R,
                $$slots: { default: !0 }
              })),
              function(S) {
                G[r()] = S;
              },
              ae
            );
          });
        }
        N(s, i);
      }, a = (s) => {
        var i = O(), _ = C(i);
        se(_, e, !1, (R, W) => {
          ue(
            R,
            function(l) {
              G[r()] = l;
            },
            ae
          ), ie(R, () => ({ ...o(), ...v() }));
          var b = O(), h = C(b);
          {
            var S = (l) => {
              var L = O(), I = C(L);
              ne(I, 17, () => g().items, Se, (J, he) => {
                Z(J, {
                  get nodes() {
                    return f();
                  },
                  get context() {
                    return n(he);
                  },
                  get routes() {
                    return y();
                  },
                  get sharedContext() {
                    return c();
                  },
                  get beforeSetProps() {
                    return K();
                  },
                  get beforeRenderNode() {
                    return M();
                  }
                });
              }), N(l, L);
            }, B = (l) => {
              Z(l, {
                get nodes() {
                  return p();
                },
                get context() {
                  return g();
                },
                get routes() {
                  return y();
                },
                get sharedContext() {
                  return c();
                },
                get beforeSetProps() {
                  return K();
                },
                get beforeRenderNode() {
                  return M();
                }
              });
            };
            q(h, (l) => {
              f() ? l(S) : p() && l(B, 1);
            });
          }
          N(W, b);
        }), N(s, i);
      }, m = (s) => {
        var i = Re();
        be(() => Ne(i, p())), N(s, i);
      };
      q(d, (s) => {
        u() ? s(T) : e() ? s(a, 1) : p() && s(m, 2);
      });
    }
    N(t, j);
  };
  let E = F(P, "context", 19, () => ({})), c = F(P, "sharedContext", 19, () => ({})), y = F(P, "routes", 19, () => ({})), K = F(P, "beforeSetProps", 3, Y), M = F(P, "beforeRenderNode", 3, Y);
  const G = {}, V = xe({}), ee = w(() => V ? Object.entries(V).reduce(
    (t, [r, { spring: e, transform: o }]) => (t[r] = o(e.current), t),
    {}
  ) : null), A = w(() => n(ee) === null ? E() : { ...E(), ...n(ee) });
  function H(t, r) {
    return t && z(t) ? t(r, c()) : t;
  }
  function te(t, r, e) {
    if (!t)
      return;
    const o = H(t, r);
    return fe(o, c().propResourceMap, e);
  }
  function pe(t, r, e) {
    let { label: o } = fe({ label: t }, c().propResourceMap, e);
    if (o.includes("{{")) {
      const u = r ? H(r, { ...n(A) }) : n(A);
      return je(o, u, e.locale);
    }
    return o;
  }
  function me(t, r) {
    return z(t.if.test) && t.if.test(r) ? D(t.if.then) : t.elseif && z(t.elseif.test) && t.elseif.test(r) ? D(t.elseif.then) : Pe(t.else) ? D(t.else) : [];
  }
  function re(t, r) {
    let e = [];
    for (const o of me(t, r))
      U(o) ? e.push(...re(o, r)) : e.push(o);
    return e;
  }
  const le = w(() => {
    const t = [];
    for (const e of D(P.nodes))
      if (e) {
        if (U(e)) {
          const o = re(e, E());
          t.push(...o);
          continue;
        }
        if (X(e)) {
          t.push(e);
          continue;
        }
        t.push(e);
      }
    function r(e, o) {
      return `${e ?? o}`;
    }
    return t.map((e, o) => {
      if (X(e))
        return { key: o, children: e };
      if (!U(e) && z(e.spring)) {
        const a = Object.entries(e.spring(E()));
        Q(() => {
          a.forEach(([m, { value: s, config: i, transform: _ = Y }]) => {
            V[m] ? V[m].spring.set(s, { instant: !c().enableAnimations }) : V[m] = { transform: _, spring: new Te(s, i) };
          });
        });
      }
      const {
        key: u,
        routes: k,
        children: p,
        transition: g,
        context: v
      } = e;
      k && Q(() => {
        Object.assign(y(), Object.entries(k).reduce(
          (a, [m, s]) => {
            const [i, _] = m.split(":"), [R, W] = s.split(".");
            return a[R] = {}, a[i] = {
              [`on${_}`]: (...b) => {
                a[R].getRoot()[W]?.(...b);
              }
            }, a;
          },
          {}
        ));
      });
      let f = {};
      Q(() => {
        u && y()?.[u] && (Object.assign(y()[u], {
          getRoot() {
            return G[u];
          }
        }), f = { ...y()[u] });
      });
      const j = v ? H(v, n(A)) : n(A), d = { ...n(A), ...j }, T = X(p) ? pe(p, d, c().resources) : p;
      if (ke(e)) {
        const { component: a, item: m, props: s } = e;
        return M()(
          {
            key: r(u, o),
            component: a,
            props: K()(te(s, d, c().resources)),
            item: m,
            children: T,
            context: d,
            transition: g,
            routes: f
          },
          E(),
          c()
        );
      }
      if (we(e)) {
        const { attrs: a, item: m, tag: s } = e;
        return M()(
          {
            key: r(u, o),
            tag: s,
            attrs: te(a, d, c().resources),
            item: m,
            children: T,
            context: d,
            transition: g,
            routes: f
          },
          E(),
          c()
        );
      }
    }).filter(Boolean);
  }), de = We();
  var oe = O(), ge = C(oe);
  ne(
    ge,
    17,
    () => n(le),
    ({
      key: t,
      tag: r,
      attrs: e,
      component: o,
      props: u,
      children: k,
      context: p,
      routes: g,
      item: v,
      transition: f
    }) => t,
    (t, r) => {
      let e = () => n(r).key, o = () => n(r).tag, u = () => n(r).attrs, k = () => n(r).component, p = () => n(r).props, g = () => n(r).children, v = () => n(r).context, f = () => n(r).routes, j = () => n(r).item, d = () => n(r).transition;
      var T = O(), a = C(T);
      {
        var m = (i) => {
          var _ = O(), R = C(_);
          {
            var W = (h) => {
              var S = O(), B = C(S);
              se(B, () => "div", !1, (l, L) => {
                var I = (J) => {
                  de.suspend(J.currentTarget);
                };
                ie(l, () => ({ onoutrostart: I })), Oe(3, l, () => d().fn, d), $(L, e, o, u, k, p, g, v, f, j);
              }), N(h, S);
            }, b = w(() => d()?.when(v()));
            q(R, (h) => {
              n(b) && h(W);
            });
          }
          N(i, _);
        }, s = (i) => {
          $(i, e, o, u, k, p, g, v, f, j);
        };
        q(a, (i) => {
          d() ? i(m) : i(s, -1);
        });
      }
      N(t, T);
    }
  ), N(ce, oe), _e();
}
export {
  Z as default
};
