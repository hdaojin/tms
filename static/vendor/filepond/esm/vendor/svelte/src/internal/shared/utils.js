var p = Array.isArray, a = Array.prototype.indexOf, i = Array.prototype.includes, y = Array.from, c = Object.defineProperty, s = Object.getOwnPropertyDescriptor, f = Object.getOwnPropertyDescriptors, v = Object.prototype, _ = Array.prototype, u = Object.getPrototypeOf, d = Object.isExtensible;
function O(r) {
  return typeof r == "function";
}
const b = () => {
};
function j(r) {
  return typeof r?.then == "function";
}
function l(r) {
  for (var e = 0; e < r.length; e++)
    r[e]();
}
function g() {
  var r, e, t = new Promise((o, n) => {
    r = o, e = n;
  });
  return { promise: t, resolve: r, reject: e };
}
export {
  y as array_from,
  _ as array_prototype,
  g as deferred,
  c as define_property,
  s as get_descriptor,
  f as get_descriptors,
  u as get_prototype_of,
  i as includes,
  a as index_of,
  p as is_array,
  d as is_extensible,
  O as is_function,
  j as is_promise,
  b as noop,
  v as object_prototype,
  l as run_all
};
