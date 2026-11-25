/* The URL scheme: what the page shows lives in the location hash, so a link,
 * a reload or the language menu opens the same view. No DOM.
 *
 *   #item=I-011111-1383&ref=1390&q=برنج&sec=1&partial=1   an item (its series, or any chain of it)
 *   #group=G-0111-1383 / #group=s1                        a heading's page (a group, a section)
 *   #changes&year=1386&section=1&kinds=merged,split        changes by year
 *   #about
 * ref: the year compared with ("all": every item, any year; none: the latest).
 */
import { DEFAULT_KINDS, KINDS } from "../core/changes.js";

/* the items view: { item, group, ref, q, sec, partial } -> "#..." */
export function itemsHash(M, v) {
  const p = [];
  if (v.item) p.push("item=" + encodeURIComponent(v.item));
  else if (v.group) p.push("group=" + encodeURIComponent(v.group));
  if (v.ref === null) p.push("ref=all");
  else if (v.ref !== M.LAST) p.push("ref=" + v.ref);
  if (v.q) p.push("q=" + encodeURIComponent(v.q));
  if (v.sec) p.push("sec=" + v.sec);
  if (v.partial) p.push("partial=1");
  return "#" + p.join("&");
}

/* changes by year: { y, sec, kinds } -> "#changes..." */
export function changesHash(ch) {
  const p = ["changes"];
  if (ch.y !== null) p.push("year=" + ch.y);
  if (ch.sec !== null) p.push("section=" + ch.sec);
  const ks = KINDS.filter(k => ch.kinds.has(k));
  if (ks.join() !== DEFAULT_KINDS.join()) p.push("kinds=" + (ks.join(",") || "none"));
  return "#" + p.join("&");
}

/* "#..." -> the view, checked against the data:
     { view: "years", y, sec, kinds } | { view: "about" } |
     { view: "items", q, sec, partial, ref, id, series, group }
   (id: the series or chain id asked for, series: its series, group: a heading node) */
export function parseHash(M, hash) {
  const raw = hash.replace(/^#/, ""), p = new URLSearchParams(raw);
  if (p.has("changes") || p.has("year")) {
    const y = +p.get("year"), sc = +p.get("section"), ks = p.get("kinds");
    return {
      view: "years",
      y: M.YEARS.includes(y) ? y : null,
      sec: M.DATA.sections[sc] ? sc : null,
      kinds: new Set(ks === null ? DEFAULT_KINDS : ks.split(",").filter(k => KINDS.includes(k))),
    };
  }
  if (decodeURIComponent(raw) === "about") return { view: "about" };
  const q = p.get("q") || "", sec = M.DATA.sections[p.get("sec")] ? p.get("sec") : "", partial = p.get("partial") === "1";
  const id = p.get("item"), series = (id && M.serOf.get(id)) || null;
  const group = (!series && M.NODES.get(p.get("group") || "")) || null;
  let ref = p.get("ref") === "all" ? null : M.YEARS.includes(+p.get("ref")) ? +p.get("ref") : M.LAST;
  // a link to an item (or heading) not asked in the default year opens it among all items
  if ((series || group) && !p.has("ref") && !(series || group).years.includes(ref)) ref = null;
  return { view: "items", q, sec, partial, ref, id, series, group };
}
