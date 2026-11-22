/* Comparability across years: how each year can express an item or a
 * heading as asked in a reference year. No DOM. */
import { is11 } from "./model.js";

/* How each year can express the target: the series' item as asked in year R.
   Every relation says its two sides cover the same ground. Walking away from
   R, a relation whose whole near side is in the target set swaps it for the
   far side (exact: add those codes up); one that takes only part of it buries
   the target inside items that also hold other things (not recoverable).
   st: "ref" | 0 strictly comparable | 1 scope changed | 2 recoverable by adding
   codes | 3 not recoverable | null not asked; set: the chains to add up (for 3:
   the chains it is buried in). */
const LEVEL = r => is11(r) ? (r.detail === "label_broadened" || r.detail === "label_narrowed" ? 1 : 0) : 2;
const byCodeOrder = (a, b) => a.code.localeCompare(b.code);
/* the chains ids (asked in year R) followed to every other year: for each
   year the set that covers the same ground (set), those asked that year
   (asked), the worst link crossed (lvl), the links that changed the scope
   (via) and the first link that took only part of the set (broken) */
export function trace(M, ids, R) {
  const out = new Map(), start = ids.map(id => M.CH.get(id)).filter(Boolean).sort(byCodeOrder);
  out.set(R, { set: start, asked: start, lvl: 0, via: [], broken: null });
  const walk = (years, rels, near, far, applies) => {
    const S = new Set(ids), via = [];
    let lvl = 0, broken = null, i = 0;
    for (const y of years) {
      while (i < rels.length && applies(rels[i], y)) {
        const r = rels[i++], hit = r[near].filter(id => S.has(id));
        if (!hit.length) continue;
        r[near].forEach(id => S.delete(id));
        r[far].forEach(id => S.add(id));
        if (broken) continue;
        if (hit.length === r[near].length) { lvl = Math.max(lvl, LEVEL(r)); if (LEVEL(r)) via.push(r); }
        else broken = r;
      }
      const set = [...S].map(id => M.CH.get(id)).filter(Boolean).sort(byCodeOrder);
      out.set(y, { set, asked: set.filter(x => x.years.includes(y)), lvl, via: [...via], broken });
    }
  };
  walk(M.YEARS.filter(y => y > R), M.RELS.filter(r => r.year > R), "from", "to", (r, y) => r.year <= y);
  walk(M.YEARS.filter(y => y < R).reverse(), M.RELS.filter(r => r.year <= R).reverse(), "to", "from", (r, y) => r.year > y);
  return out;
}
export function compare(M, s, R) {
  const key = `${s.id}|${R}`;
  if (M.cmp.has(key)) return M.cmp.get(key);
  const out = new Map(), target = s.at(R);
  M.cmp.set(key, out);
  if (!target) return out;
  for (const [y, e] of trace(M, [target.id], R)) {
    if (y === R) { out.set(y, { st: "ref", set: [target], via: [] }); continue; }
    if (!e.asked.length) { out.set(y, { st: null, set: [], via: [] }); continue; }
    const partial = !e.broken && e.asked.length < e.set.length;
    out.set(y, { st: e.broken || partial ? 3 : e.lvl, set: partial ? e.set : e.asked, via: e.via, broken: e.broken, partial });
  }
  return out;
}

/* How each year can express a heading (a group or a section) as printed
   in year R: its items that year are followed through the relations to
   every other year. Merges and splits inside the heading keep its total;
   what differs is the items asked that year under other headings (plus,
   to add), those under it that the reference year has elsewhere (moved)
   or not at all (gone), both to remove, and those not asked that year
   (miss). st: "ref" | 0 the same items | 1 scope changed (items not asked,
   or a label broadened or narrowed) | 2 recoverable by adding or removing
   codes | 3 not recoverable (an item split across its edge) | null */
export function gcompare(M, n, R) {
  const key = `${n.id}|${R}`;
  if (M.gcmp.has(key)) return M.gcmp.get(key);
  const out = new Map();
  M.gcmp.set(key, out);
  const T = [...n.members(R)];
  if (!T.length) return out;
  const tr = trace(M, T, R);
  for (const y of M.YEARS) {
    const Gy = n.members(y), e = tr.get(y);
    const mem = [...Gy].map(id => M.CH.get(id)).filter(Boolean).sort(byCodeOrder);
    if (y === R) { out.set(y, { st: "ref", set: mem, mem, plus: [], moved: [], gone: [], miss: [], via: [] }); continue; }
    const S = new Set(e.set.map(c => c.id));
    const plus = e.asked.filter(c => !Gy.has(c.id));
    const extra = mem.filter(c => !S.has(c.id));
    const moved = extra.filter(c => M.serOf.get(c.id).years.includes(R)), gone = extra.filter(c => !moved.includes(c));
    const miss = e.set.filter(c => !c.years.includes(y));
    const via = e.via.filter(r => is11(r) && LEVEL(r) === 1);
    if (!mem.length && !e.asked.length) { out.set(y, { st: null, set: [], mem, plus, moved, gone, miss, via }); continue; }
    const st = e.broken ? 3 : miss.length ? 1 : plus.length || moved.length || gone.length ? 2 : via.length ? 1 : 0;
    out.set(y, { st, set: e.asked, mem, plus, moved, gone, miss, via, broken: e.broken });
  }
  return out;
}
