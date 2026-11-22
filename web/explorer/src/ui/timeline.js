/* Comparability on screen: the states' colours, the list's strip, the
 * verdict box, the year-by-year timeline and its tooltips. */
import { compare } from "../core/compare.js";
import { is11 } from "../core/model.js";
import { esc } from "./html.js";

export function createTimeline(ctx) {
  const { M, t, fa, pdfBase, pdfUrl } = ctx;
  const { num, yr, ranges } = ctx.fmt;

  // a year's state as a number (0-3, "" not asked) and as classes
  const stOf = e => !e || e.st === null ? "" : e.st === "ref" ? 0 : e.st;
  const stCls = e => !e || e.st === null ? "" : e.st === "ref" ? "s0 ref" : `s${e.st}`;
  // a series in the list: one square per year
  function strip(s) {
    const cmp = compare(M, s, ctx.refOf(s));
    return `<span class="strip">` + M.YEARS.map(y => `<i class="${stCls(cmp.get(y))}"></i>`).join("") + `</span>`;
  }

  /* what the item and heading cards (and a heading's dot) share. byState:
     the years of each state; spans: those years as lines with a swatch */
  function byState(cmp) {
    const by = [[], [], [], []];
    for (const y of M.YEARS) { const e = cmp.get(y); if (e && e.st !== null) by[e.st === "ref" ? 0 : e.st].push(y); }
    return by;
  }
  const spans = (by, labels) => by.map((ys, k) => ys.length ? `<li><i class="sw s${k}"></i>${labels[k]}: ${ranges(ys)}</li>` : "").join("");
  // the verdict box: compared with year R, the years of each state (and extra lines)
  function verdictHtml(cmp, R, seenFrom, labels, extra = "") {
    const by = byState(cmp), cls = by[3].length ? "bad" : by[1].length || by[2].length ? "warn" : "ok";
    return `<div class="verdict ${cls}"><b>${seenFrom(`<span class="refy">${yr(R)}</span>`)}</b><ul class="spans">${spans(by, labels)}${extra}</ul></div>`;
  }
  /* the timeline and its legend. cell(y, e) gives a year's chains to open
     on the printed form, its tooltip, and for a year on no printed page
     np: true; the years in asked can be double-clicked to become R */
  function timelineHtml(cmp, R, asked, labels, cell) {
    let h = `<div class="timeline"><div class="tl" style="grid-template-columns:repeat(${M.YEARS.length},minmax(0,1fr))">`;
    // the reference year: its label a chip, its cell ringed, an arrow under it
    h += M.YEARS.map(y => `<div class="y${y === R ? " ref" : ""}"${y === R ? ` title="${esc(t.cm.ref)}"` : ""}><span>${yr(y).slice(2)}</span></div>`).join("");
    let np = false;
    h += M.YEARS.map(y => {
      const e = cmp.get(y), c = cell(y, e), dy = asked.includes(y) ? ` data-y="${y}"` : "";
      if (pdfBase && c.chains.length) {
        return `<a class="c ${stCls(e)}"${dy} href="${pdfUrl(c.chains[0], y)}" target="_blank" rel="noopener" data-pdf="${esc(c.chains.map(x => x.id).join(" "))}" data-year="${y}" data-st="${stOf(e)}" title="${esc(c.tip)} · ${t.cm.openForm}"></a>`;
      }
      if (c.np) np = true;
      return `<div class="c ${stCls(e)}${c.np ? " np" : ""}"${dy} title="${esc(c.tip)}${c.np ? ` · ${t.notPrinted}` : ""}"></div>`;
    }).join("");
    h += `<div class="refnote" style="grid-column:${M.YEARS.indexOf(R) + 1}" title="${esc(t.cm.ref)}" aria-label="${esc(t.cm.ref)}">▲</div>`;
    const present = new Set([...cmp.values()].map(e => (e.st === "ref" ? 0 : e.st)));
    return h + `</div></div><div class="legend">` +
      [0, 1, 2, 3].filter(k => present.has(k)).map(k => `<span><i class="sw s${k}"></i>${labels[k]}</span>`).join("") +
      (present.has(null) ? `<span><i class="sw"></i>${t.cm.na}</span>` : "") +
      (np ? `<span><i class="sw np"></i>${t.cm.np}</span>` : "") +
      `<span><i class="sw s0 ref"></i>${t.cm.ref}</span></div>`;
  }

  // a year's tooltip on an item's timeline
  function tip(y, e) {
    if (!e || e.st === null) return `${yr(y)}: ${t.cm.na}`;
    const codes = e.set.map(x => x.code);
    if (e.st === "ref") return `${yr(y)}: ${codes[0]} · ${t.cm.ref}`;
    if (e.st === 3) return `${yr(y)}: ${e.partial ? t.cm.partial(codes.join(" + ")) : t.cm.inside(codes.join(fa ? "، " : ", "))} · ${t.cm.st[3]}`;
    if (e.st === 2) return `${yr(y)}: ${t.cm.sum(codes.join(" + "))} · ${t.cm.st[2]}`;
    if (e.st === 1) return `${yr(y)}: ${codes[0]} · ${t.cm.st[1]} (${e.via.filter(is11).map(r => `${t.det[r.detail]} ${yr(r.year)}`).join(fa ? "، " : ", ")})`;
    return `${yr(y)}: ${codes[0]} · ${t.cm.st[0]}`;
  }
  // and on a heading's
  function gtip(y, e) {
    if (!e || e.st === null) return `${yr(y)}: ${t.cm.na}`;
    const k = e.st === "ref" ? 0 : e.st, parts = [`${yr(y)}: ${t.g.items(num(e.mem.length))}`];
    if (e.plus.length) parts.push(`+${num(e.plus.length)}`);
    if (e.moved.length + e.gone.length) parts.push(`−${num(e.moved.length + e.gone.length)}`);
    if (e.miss.length) parts.push(`${t.g.miss}: ${num(e.miss.length)}`);
    return parts.join(" · ") + ` · ${e.st === "ref" ? t.cm.ref : t.g.st[k]}`;
  }

  return { stOf, stCls, strip, byState, spans, verdictHtml, timelineHtml, tip, gtip };
}
