/* Search: series matching a code or Persian text. No DOM. */
import { latinDigits, norm } from "./text.js";

/* series matching a query: [series, rank, the chain that matched] */
export function search(M, q) {
  const raw = q.trim();
  if (!raw) return null;
  const ascii = latinDigits(raw);
  const m = ascii.match(/^(\d+)(?:-(\d{4}))?$/);
  const out = [];
  if (m) {
    const d = m[1], cands = new Set([d]);
    if (d.length === 5 || d.length === 3) cands.add("0" + d);
    for (const s of M.SER) {
      const hit = [...s.chains].reverse().find(c => [...cands].some(x => c.code.startsWith(x)) && (!m[2] || c.id.endsWith(m[2])));
      if (hit) out.push([s, cands.has(hit.code) ? 0 : 1, hit]);
    }
    return out;
  }
  const toks = raw.split(/\s+/).map(norm).filter(Boolean);
  for (const s of M.SER) {
    if (!toks.every(t => s.key.includes(t))) continue;
    const hit = [...s.chains].reverse().find(c => toks.every(t => c.key0.includes(t)))
      || [...s.chains].reverse().find(c => toks.every(t => c.key.includes(t))) || s.chains[s.chains.length - 1];
    out.push([s, (toks.every(t => hit.key0.includes(t)) ? 0 : 2) + (hit.key0.startsWith(toks[0]) ? 0 : 1), hit]);
  }
  return out;
}
