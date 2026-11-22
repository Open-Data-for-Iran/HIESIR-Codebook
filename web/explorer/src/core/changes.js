/* Changes by year: what each questionnaire changed. No DOM.
 *
 * Every change is one event: its kind, year, section (where its items sit
 * that year) and the number of items it involves: 1 for a new, dropped,
 * recoded or reworded item, the larger side of a merge, split or regrouping
 * (99 merges that took in 261 items count 261), one per link between group
 * headings and one per correction.
 */

const isScope = r => r.rel === "same" && r.detail && r.detail !== "minor";
const prevOf = (M, y) => M.YEARS[M.YEARS.indexOf(y) - 1];

export const KINDS = ["added", "dropped", "recoded", "merged", "split", "regrouped", "scope", "groups", "corr"];
export const DEFAULT_KINDS = KINDS.filter(k => k !== "groups" && k !== "corr");

/* the chain a correction is about, in its year */
export function corrChain(M, k) {
  const y = +k.year;
  for (const cd of [k.value, k.expenditure_code]) {
    const cs = M.byCode.get(cd) || [];
    const c = cs.find(x => x.years.includes(y)) || cs[0];
    if (c) return c;
  }
  return null;
}
/* the section a correction is in */
export function corrSec(M, k) {
  if (k.action === "add_section") return +k.description;
  const c = corrChain(M, k);
  if (c) return c.secAt(+k.year);
  const g = M.G.find(g => g[0] === k.expenditure_code || g[0] === k.value);
  return g ? g[3] : null;
}
/* every event, computed once per model (kept on M.events) */
export function events(M) {
  if (M.events) return M.events;
  const EV = (M.events = []);
  for (const r of M.DATA.relations) {
    const kind = r.rel === "same" ? (isScope(r) ? "scope" : null) : r.rel;
    if (!kind) continue;
    const tgt = M.CH.get(r.to[0]), src = M.CH.get(r.from[0]);
    EV.push({ kind, y: r.year, sec: tgt ? tgt.secAt(r.year) : src ? src.secAt(prevOf(M, r.year)) : null, n: Math.max(r.from.length, r.to.length), r });
  }
  for (const c of M.DATA.chains) {
    const y = c.years[0], last = c.years[c.years.length - 1];
    if (y !== M.YEARS[0] && !c.ins.some(r => r.year === y)) EV.push({ kind: "added", y, sec: c.secAt(y), n: 1, c });
    const next = M.YEARS[M.YEARS.indexOf(last) + 1];
    if (next && !c.outs.some(r => r.year === next)) EV.push({ kind: "dropped", y: next, sec: c.secAt(last), n: 1, c });
  }
  for (const g of M.DATA.groupLinks || []) EV.push({ kind: "groups", y: g[3], sec: M.G[g[1]][3], n: 1, g });
  for (const k of M.DATA.corrections) EV.push({ kind: "corr", y: +k.year, sec: corrSec(M, k), n: 1, k });
  return EV;
}
