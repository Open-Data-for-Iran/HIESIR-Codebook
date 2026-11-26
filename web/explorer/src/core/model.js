/* The data model: data.json (see data.d.ts) indexed for the views. No DOM.
 *
 * model(DATA) adds to each chain its years, pages and boxes by year, its
 * groups and section by year, its changes in and out and its search keys;
 * joins chains that continuing changes link into series (an item reworded or recoded)
 * and groups continued under another code into heading nodes; and returns
 * the indexes the views use, with caches for compare() and gcompare().
 */
import { norm } from "./text.js";

/* a continuing change: the same item, maybe reworded or recoded */
export const is11 = r => (r.rel === "same" || r.rel === "recoded") && r.from.length === 1 && r.to.length === 1;

export function model(DATA) {
  const YEARS = DATA.years, LAST = YEARS[YEARS.length - 1];
  const CH = new Map(DATA.chains.map(c => [c.id, c])), G = DATA.groups || [];
  for (const c of DATA.chains) {
    const miss = new Set(c.miss);
    c.years = YEARS.filter(y => y >= c.first && y <= c.last && !miss.has(y));
    c.page = new Map(c.years.map((y, i) => [y, c.pg ? c.pg[i] : null]));
    c.box = new Map(c.years.map((y, i) => [y, c.bx ? c.bx[i] : null]));
    // its groups (indexes into DATA.groups, outermost first) in year y
    c.groupsAt = y => { let g = []; for (const [y0, p] of c.gp || []) if (y0 <= y) g = p; return g; };
    // its section in year y: some items moved (124113 and the insurance items
    // went from section 12 to 13); c.s is the section of its first year
    c.secAt = y => { const g = c.groupsAt(y); return (g.length && G[g[0]] && G[g[0]][3]) || c.s; };
    c.ins = []; c.outs = [];
    c.key = norm(c.text + " " + c.path.map(p => p[1]).join(" "));
    c.key0 = norm(c.text);
  }
  for (const r of DATA.changes) {
    for (const id of r.to) CH.get(id)?.ins.push(r);
    for (const id of r.from) CH.get(id)?.outs.push(r);
  }
  const byCode = new Map();
  for (const c of DATA.chains) (byCode.get(c.code) || byCode.set(c.code, []).get(c.code)).push(c);
  // series: chains joined by continuing changes (the same item reworded, or recoded)
  const serOf = new Map(), SER = [];
  for (const c of DATA.chains) {
    if (serOf.has(c.id)) continue;
    const comp = [], todo = [c], seen = new Set([c.id]);
    while (todo.length) {
      const x = todo.pop(); comp.push(x);
      for (const r of [...x.ins, ...x.outs]) {
        if (!is11(r)) continue;
        for (const id of [r.from[0], r.to[0]]) {
          const y = CH.get(id);
          if (y && !seen.has(y.id)) { seen.add(y.id); todo.push(y); }
        }
      }
    }
    comp.sort((a, b) => a.first - b.first || a.last - b.last);
    // its id, as in output/3_items/series.csv: I-, the code and first year of its first chain
    const s = { id: `I-${comp[0].code}-${comp[0].first}`, chains: comp, years: [...new Set(comp.flatMap(x => x.years))].sort((a, b) => a - b) };
    s.last = s.years[s.years.length - 1];
    s.key = comp.map(x => x.key).join(" ");
    s.at = y => s.chains.find(x => x.years.includes(y));
    comp.forEach(x => serOf.set(x.id, s));
    serOf.set(s.id, s);
    SER.push(s);
  }
  const RELS = DATA.changes.slice().sort((a, b) => a.year - b.year);
  // the wording printed in year y (y null: the latest)
  const runAt = (runs, y, latest) => { if (!runs || y == null) return latest; let l = runs[0][1]; for (const [y0, v] of runs) if (y0 <= y) l = v; return l; };
  const groupLabel = (gi, y) => runAt(G[gi] && G[gi][4], y, G[gi] ? G[gi][1] : "");
  const sectionTitle = (n, y) => runAt((DATA.sectionYears || {})[n], y, DATA.sections[n] || "");
  /* heading pages: a group joined with the groups it continues as (a
     "continued" change: the same heading recoded or reworded), and each
     section; members(y): the chains printed under it in year y */
  const GIDS = DATA.groupIds || [];
  const MEM = G.map(() => new Map()), SMEM = new Map();
  const put = (m, y, id) => (m.get(y) || m.set(y, new Set()).get(y)).add(id);
  for (const c of DATA.chains) {
    for (const y of c.years) {
      for (const gi of c.groupsAt(y)) put(MEM[gi], y, c.id);
      const sn = c.secAt(y);
      put(SMEM.get(sn) || SMEM.set(sn, new Map()).get(sn), y, c.id);
    }
  }
  const yearsOf = ms => YEARS.filter(y => ms.some(m => m.get(y)?.size));
  const union = (ms, y) => { const u = new Set(); for (const m of ms) for (const id of m.get(y) || []) u.add(id); return u; };
  const GY = MEM.map(m => yearsOf([m]));
  const up = G.map((_, i) => i), root = i => (up[i] === i ? i : (up[i] = root(up[i])));
  for (const [a, b, rel] of DATA.groupChanges || []) if (rel === "continued") up[root(b)] = root(a);
  const byRoot = new Map();
  G.forEach((_, i) => { const r = root(i); (byRoot.get(r) || byRoot.set(r, []).get(r)).push(i); });
  const NODES = new Map(), nodeOfG = [];
  for (const gis of byRoot.values()) {
    gis.sort((a, b) => (GY[a][0] || 0) - (GY[b][0] || 0));
    const ms = gis.map(i => MEM[i]), years = yearsOf(ms);
    if (!years.length) continue;
    const n = { kind: "g", gis, id: GIDS[gis[0]] || `g${gis[0]}`, years, last: years[years.length - 1], members: y => union(ms, y) };
    // the group printed in year y (the latest one when it is not printed)
    n.giAt = y => gis.find(i => MEM[i].get(y)?.size) ?? gis[gis.length - 1];
    NODES.set(n.id, n);
    gis.forEach(i => { nodeOfG[i] = n; });
  }
  for (const [sn, m] of [...SMEM].sort((a, b) => a[0] - b[0])) {
    const years = yearsOf([m]);
    NODES.set(`s${sn}`, { kind: "s", sec: sn, id: `s${sn}`, years, last: years[years.length - 1], members: y => m.get(y) || new Set() });
  }
  return { DATA, YEARS, LAST, CH, byCode, SER, serOf, RELS, G, GY, groupLabel, sectionTitle, NODES, nodeOfG, cmp: new Map(), gcmp: new Map(), events: null };
}
