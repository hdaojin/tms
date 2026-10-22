/*!
* FilePond v5.0.0-beta.74
* Copyright (c) 2017-2026 Pqina B.V.
* Released under the MIT License
* https://filepond.com
*/
import { untrack as J, get as t } from "../../../vendor/svelte/src/internal/client/runtime.js";
import { noop as oe } from "../../../vendor/svelte/src/internal/shared/utils.js";
import { push as xe, pop as Me } from "../../../vendor/svelte/src/internal/client/context.js";
import { first_child as m } from "../../../vendor/svelte/src/internal/client/dom/operations.js";
import { user_effect as Oe, template_effect as be } from "../../../vendor/svelte/src/internal/client/reactivity/effects.js";
import { user_derived as s } from "../../../vendor/svelte/src/internal/client/reactivity/deriveds.js";
import { set_text as he } from "../../../vendor/svelte/src/internal/client/render.js";
import { comment as l, append as f, text as Ne } from "../../../vendor/svelte/src/internal/client/dom/template.js";
import { if_block as y } from "../../../vendor/svelte/src/internal/client/dom/blocks/if.js";
import { each as Se, index as De } from "../../../vendor/svelte/src/internal/client/dom/blocks/each.js";
import { component as ye } from "../../../vendor/svelte/src/internal/client/dom/blocks/svelte-component.js";
import { element as Q } from "../../../vendor/svelte/src/internal/client/dom/blocks/svelte-element.js";
import { attribute_effect as U } from "../../../vendor/svelte/src/internal/client/dom/elements/attributes.js";
import { transition as ke } from "../../../vendor/svelte/src/internal/client/dom/elements/transitions.js";
import { bind_this as X } from "../../../vendor/svelte/src/internal/client/dom/elements/bindings/this.js";
import { prop as Z, spread_props as Te } from "../../../vendor/svelte/src/internal/client/reactivity/props.js";
import { Spring as Ce } from "../../../vendor/svelte/src/motion/spring.js";
import { isTextNode as Ee, isComponentNode as je } from "../../common/nodeTree.js";
import { isFunction as z, isString as we } from "../../../utils/test.js";
import { passthrough as ae, noop as $ } from "../../../utils/placeholder.js";
import { withResources as ie, stringReplaceVariables as Ve } from "../../common/string.js";
import { getSuspensionObserver as Pe, isVoidElementTag as We } from "../../common/dom.js";
import { EMPTY_OBJECT as Ye, isObjectValuesEqual as G } from "../../../utils/object.js";
import H from "./index-svelte.js";
import { EMPTY_ARRAY as ue } from "../../../utils/array.js";
function ct(se, e) {
  xe(e, !0);
  const ee = (n, r = oe) => {
    var o = l(), a = m(o);
    {
      var c = (i) => {
        const v = s(() => r().component);
        var O = l(), S = m(O);
        {
          const E = (d, g = oe) => {
            var p = l(), R = m(p);
            {
              var F = (b) => {
                {
                  let W = s(() => [r().item]);
                  H(b, {
                    get reduceMotion() {
                      return k();
                    },
                    get springOptions() {
                      return e.springOptions;
                    },
                    get propResourceMap() {
                      return e.propResourceMap;
                    },
                    get resources() {
                      return e.resources;
                    },
                    get context() {
                      return e.context;
                    },
                    get beforeRenderNode() {
                      return h();
                    },
                    get nodes() {
                      return t(W);
                    },
                    get data() {
                      return g();
                    },
                    routes: void 0
                  });
                }
              }, D = (b) => {
                {
                  let W = s(() => ({ ...t(C), ...g() }));
                  H(b, {
                    get reduceMotion() {
                      return k();
                    },
                    get springOptions() {
                      return e.springOptions;
                    },
                    get propResourceMap() {
                      return e.propResourceMap;
                    },
                    get resources() {
                      return e.resources;
                    },
                    get context() {
                      return e.context;
                    },
                    get beforeRenderNode() {
                      return h();
                    },
                    get nodes() {
                      return t(q);
                    },
                    get data() {
                      return t(W);
                    },
                    get routes() {
                      return _().routes;
                    }
                  });
                }
              };
              y(R, (b) => {
                r().item ? b(F) : b(D, -1);
              });
            }
            f(d, p);
          };
          let P = s(() => ({
            data: t(C),
            routes: _().routes,
            context: e.context,
            beforeRenderNode: h(),
            springOptions: e.springOptions,
            reduceMotion: k(),
            propResourceMap: e.propResourceMap,
            resources: e.resources
          }));
          ye(S, () => t(v), (d, g) => {
            X(
              g(d, Te(() => r().props, () => r().routes, {
                get subNodeListProps() {
                  return t(P);
                },
                children: E,
                $$slots: { default: !0 }
              })),
              function(p) {
                r().props?.onmount?.(p), _().refs[r().key] = p;
              },
              $
            );
          });
        }
        f(i, O);
      }, u = (i) => {
        var v = l(), O = m(v);
        {
          var S = (d) => {
            var g = l(), p = m(g);
            Q(p, () => r().tag, !1, (R, F) => {
              X(
                R,
                function(D) {
                  r().attrs?.onconnected?.(D), _().refs[r().key] = D;
                },
                $
              ), U(R, () => ({ ...r().attrs, ...r().routes }));
            }), f(d, g);
          }, E = s(() => We(r().tag)), P = (d) => {
            var g = l(), p = m(g);
            Q(p, () => r().tag, !1, (R, F) => {
              X(
                R,
                function(x) {
                  r().attrs?.onconnected?.(x), _().refs[r().key] = x;
                },
                $
              ), U(R, () => ({ ...r().attrs, ...r().routes }));
              var D = l(), b = m(D);
              {
                var W = (x) => {
                  var ne = l(), pe = m(ne);
                  Se(pe, 17, () => t(C).items, De, (_e, Re) => {
                    H(_e, {
                      get reduceMotion() {
                        return k();
                      },
                      get springOptions() {
                        return e.springOptions;
                      },
                      get propResourceMap() {
                        return e.propResourceMap;
                      },
                      get resources() {
                        return e.resources;
                      },
                      get context() {
                        return e.context;
                      },
                      get beforeRenderNode() {
                        return h();
                      },
                      get nodes() {
                        return r().item;
                      },
                      get data() {
                        return t(Re);
                      },
                      get routes() {
                        return _().routes;
                      }
                    });
                  }), f(x, ne);
                }, ve = (x) => {
                  H(x, {
                    get reduceMotion() {
                      return k();
                    },
                    get springOptions() {
                      return e.springOptions;
                    },
                    get propResourceMap() {
                      return e.propResourceMap;
                    },
                    get resources() {
                      return e.resources;
                    },
                    get context() {
                      return e.context;
                    },
                    get beforeRenderNode() {
                      return h();
                    },
                    get nodes() {
                      return t(q);
                    },
                    get data() {
                      return t(C);
                    },
                    get routes() {
                      return _().routes;
                    }
                  });
                };
                y(b, (x) => {
                  r().item ? x(W) : t(q) && x(ve, 1);
                });
              }
              f(F, D);
            }), f(d, g);
          };
          y(O, (d) => {
            t(E) ? d(S) : d(P, -1);
          });
        }
        f(i, v);
      }, M = (i) => {
        var v = Ne();
        be(() => he(v, t(q))), f(i, v);
      };
      y(a, (i) => {
        r().component ? i(c) : r().tag ? i(u, 1) : i(M, -1);
      });
    }
    f(n, o);
  };
  function ce(n, r, o) {
    return z(n) ? n(r, o) : n;
  }
  function te(n, r, o, a, c) {
    if (!n)
      return;
    const u = ce(n, r, o);
    return ie(u, c, a);
  }
  function de(n, r, o, a) {
    const { label: c } = ie({ label: n }, a, o);
    return c.includes("{{") ? Ve(c, r, o.locale) : c;
  }
  let _ = Z(e, "scope", 7), h = Z(e, "beforeRenderNode", 3, ae), k = Z(e, "reduceMotion", 3, !1);
  const fe = Pe();
  let j;
  const Y = s(() => {
    if (e.data)
      return j && G(e.data, j) || (j = e.data), j;
  });
  let w;
  const A = s(() => {
    if (we(e.node) || !t(Y))
      return;
    if (!e.node.data)
      return e.node.data === !1 ? void 0 : t(Y);
    const n = z(e.node.data) ? e.node.data(t(Y), e.context) : { ...t(Y), ...e.node.data };
    return w && G(n, w) || (w = n), w;
  }), I = J(() => !!e.node?.spring), V = I ? J(() => {
    const n = {}, r = z(e.node.spring) ? Object.entries(e.node.spring(Ye)) : ue;
    for (const [o, a] of r) {
      const { value: c = null, config: u, transform: M = ae } = a;
      n[o] = {
        transform: M,
        spring: new Ce(c, u || e.springOptions)
      };
    }
    return n;
  }) : null;
  Oe(() => {
    if (!I || !t(A) || !V)
      return;
    const n = z(e.node.spring) ? Object.entries(e.node.spring(t(A))) : ue;
    J(() => {
      if (V)
        for (const [r, { value: o, instant: a = !1 }] of n)
          V[r].spring.set(o, { instant: k() || a });
    });
  });
  let K = {};
  const ge = s(() => {
    if (!V)
      return;
    const n = {};
    for (const [r, { spring: o, transform: a }] of Object.entries(V))
      n[r] = a(o.current);
    return G(n, K) ? K : (K = n, n);
  });
  let L = {};
  const N = s(() => {
    if (!I)
      return t(A);
    const n = { ...t(A), ...t(ge) };
    return G(n, L) || (L = n), L;
  }), T = s(() => {
    const n = `${e.node.key ?? e.index}`, { children: r, transition: o } = e.node;
    if (Ee(e.node))
      return {
        // no need for other props as text nodes are just strings
        children: de(e.node.children, t(N), e.resources, e.propResourceMap)
      };
    let a;
    if (J(() => {
      const i = _().routes;
      n && i?.[n] && (Object.assign(i[n], {
        getRoot() {
          return _().refs[n];
        }
      }), a = { ...i[n] });
    }), je(e.node)) {
      const { component: i, item: v, props: O } = e.node;
      return h()(
        {
          key: n,
          component: i,
          props: te(O, t(N), e.context, e.resources, e.propResourceMap),
          item: v,
          children: r,
          data: t(N),
          routes: a,
          transition: o
        },
        t(N),
        e.context
      );
    }
    const { attrs: c, item: u, tag: M } = e.node;
    return h()(
      {
        key: n,
        tag: M,
        attrs: te(c, t(N), e.context, e.resources, e.propResourceMap),
        item: u,
        children: r,
        data: t(N),
        routes: a,
        transition: o
      },
      t(N),
      e.context
    );
  }), q = s(() => t(T).children), C = s(() => t(T).data), B = s(() => t(T).transition);
  var re = l(), me = m(re);
  {
    var le = (n) => {
      var r = l(), o = m(r);
      {
        var a = (u) => {
          var M = l(), i = m(M);
          {
            var v = (S) => {
              var E = l(), P = m(E);
              Q(P, () => "div", !1, (d, g) => {
                var p = (R) => {
                  fe.suspend(R.currentTarget);
                };
                U(d, () => ({ onoutrostart: p })), ke(3, d, () => t(B).fn, () => t(B)), ee(g, () => t(T));
              }), f(S, E);
            }, O = s(() => t(B).when(t(C)));
            y(i, (S) => {
              t(O) && S(v);
            });
          }
          f(u, M);
        }, c = (u) => {
          ee(u, () => t(T));
        };
        y(o, (u) => {
          t(B) && t(C) ? u(a) : u(c, -1);
        });
      }
      f(n, r);
    };
    y(me, (n) => {
      t(T) && n(le);
    });
  }
  f(se, re), Me();
}
export {
  ct as default
};
