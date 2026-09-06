import { clsx as S } from "../../../../clsx/dist/clsx.js";
function L(f) {
  return typeof f == "object" ? S(f) : f ?? "";
}
const n = [...` 	
\r\f \v\uFEFF`];
function $(f, t, u) {
  var r = f == null ? "" : "" + f;
  if (u) {
    for (var i of Object.keys(u))
      if (u[i])
        r = r ? r + " " + i : i;
      else if (r.length)
        for (var h = i.length, g = 0; (g = r.indexOf(i, g)) >= 0; ) {
          var s = g + h;
          (g === 0 || n.includes(r[g - 1])) && (s === r.length || n.includes(r[s])) ? r = (g === 0 ? "" : r.substring(0, g)) + r.substring(s + 1) : g = s;
        }
  }
  return r === "" ? null : r;
}
function v(f, t = !1) {
  var u = t ? " !important;" : ";", r = "";
  for (var i of Object.keys(f)) {
    var h = f[i];
    h != null && h !== "" && (r += " " + i + ": " + h + u);
  }
  return r;
}
function j(f) {
  return f[0] !== "-" || f[1] !== "-" ? f.toLowerCase() : f;
}
function q(f, t) {
  if (t) {
    var u = "", r, i;
    if (Array.isArray(t) ? (r = t[0], i = t[1]) : r = t, f) {
      f = String(f).replaceAll(/\/\*.*?\*\//g, "").trim();
      var h = !1, g = 0, s = !1, l = [];
      r && l.push(...Object.keys(r).map(j)), i && l.push(...Object.keys(i).map(j));
      var p = 0, b = -1;
      const O = f.length;
      for (var c = 0; c < O; c++) {
        var o = f[c];
        if (s ? o === "/" && f[c - 1] === "*" && (s = !1) : h ? h === o && (h = !1) : o === "/" && f[c + 1] === "*" ? s = !0 : o === '"' || o === "'" ? h = o : o === "(" ? g++ : o === ")" && g--, !s && h === !1 && g === 0) {
          if (o === ":" && b === -1)
            b = c;
          else if (o === ";" || c === O - 1) {
            if (b !== -1) {
              var A = j(f.substring(p, b).trim());
              if (!l.includes(A)) {
                o !== ";" && c++;
                var a = f.substring(p, c).trim();
                u += " " + a + ";";
              }
            }
            p = c + 1, b = -1;
          }
        }
      }
    }
    return r && (u += v(r)), i && (u += v(i, !0)), u = u.trim(), u === "" ? null : u;
  }
  return f == null ? null : String(f);
}
export {
  L as clsx,
  $ as to_class,
  q as to_style
};
