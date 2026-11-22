/* An item's page: where it sits, its codes over the years, how each year
 * compares with the reference year, the codes to use, its wording history,
 * its merges and splits, other items under its codes, the corrections. */
import { compare } from "../core/compare.js";
import { is11 } from "../core/model.js";
import { codesSnippet } from "../core/snippets.js";
import { chainLink, code, esc, fat, gLink, locateBtns } from "./html.js";

export function createItemCard(ctx) {
  const { M, t, fa, pdfBase, pdfUrl, state: S } = ctx;
  const { num, yr, span, ylabel, ranges, ARROW } = ctx.fmt;
  const { relPills } = ctx.labels;
  const { stOf, verdictHtml, timelineHtml, tip } = ctx.timeline;

  /* the page of series sid (any of its chain ids) as HTML; null when there is none */
  function render(sid) {
    const s = M.serOf.get(sid);
    if (!s) return null;
    const R = ctx.refOf(s), cmp = compare(M, s, R), c = s.at(R);
    const inSer = new Set(s.chains.map(x => x.id));

    // the headings above it, each a link to its page
    const gs = c.groupsAt(R), sn = c.secAt(R);
    const above = gs.length ? gs.map(gi => M.nodeOfG[gi] ? gLink(M.nodeOfG[gi].id, esc(M.groupLabel(gi, R))) : esc(M.groupLabel(gi, R)))
      : c.path.map(p => esc(p[1]));
    let h = `<div class="crumbs fa">${[M.NODES.has(`s${sn}`) ? gLink(`s${sn}`, esc(M.sectionTitle(sn, R))) : esc(M.sectionTitle(sn, R)), ...above].filter(Boolean).map(x => `<span>${x}</span>`).join("")}</div>`;
    h += `<div class="title fa">${esc(c.text)}${locateBtns(t)}</div>`;
    // codes by period: 011837 1383–1385 → 011174 1386–1403
    const periods = [];
    for (const x of s.chains) {
      const p = periods[periods.length - 1];
      if (p && p.code === x.code) p.b = x.last; else periods.push({ code: x.code, a: x.first, b: x.last });
    }
    h += `<div class="ids">${periods.map(p => `${code(p.code)} <span class="yrs">${span(p.a, p.b)}</span>`).join(` <span class="arrow">${ARROW}</span> `)}` +
      ` <span class="pill">${t.section(yr(c.secAt(R)))}</span> <span class="pill" title="${t.chainId}">${esc(s.id)}</span></div>`;
    if (S.ref && !s.years.includes(S.ref)) h += `<div class="note">${t.cm.notInRef(yr(S.ref))}</div>`;

    // years asked but on no printed page: the codes come from a correction
    // (1383 section 2, copied from 1384 as that page of the PDF is blank)
    const np = M.YEARS.filter(y => { const e = cmp.get(y); return e && e.st !== null && e.set.every(x => !x.page.get(y)); });
    const why = [...new Set(np.flatMap(y => cmp.get(y).set.map(x => M.DATA.corrections.find(k =>
      +k.year === y && k.action === "add_section" && +k.description === x.secAt(y))).filter(Boolean)))];
    h += verdictHtml(cmp, R, t.cm.seenFrom, t.cm.st, np.length ? `<li class="np"><i class="sw np"></i>${t.cm.npLine(ranges(np))}${why.length ? ":" : "."}` +
      why.map(k => `<div class="why" dir="ltr">${esc(k.reason)}</div>`).join("") + `</li>` : "");

    // timeline
    h += `<h3>${t.timeline}</h3>`;
    h += `<div class="pdfhint">${pdfBase && s.chains.some(x => x.years.some(y => x.page.get(y))) ? t.pdfHint : t.refHint}</div>`;
    h += timelineHtml(cmp, R, s.years, t.cm.st, (y, e) => ({ chains: e ? e.set.filter(x => pdfUrl(x, y)) : [], tip: tip(y, e), np: np.includes(y) }));

    // codes to use, year by year
    const use = [];
    for (const y of M.YEARS) {
      const e = cmp.get(y);
      if (!e || e.st === null) continue;
      const k = e.st === "ref" ? 0 : e.st, codes = e.set.map(x => x.code).join(" + ");
      const last = use[use.length - 1];
      if (last && last.k === k && last.codes === codes && M.YEARS.indexOf(y) === M.YEARS.indexOf(last.ys[last.ys.length - 1]) + 1) last.ys.push(y);
      else use.push({ k, codes, ys: [y], e });
    }
    const py = codesSnippet(M.YEARS, cmp, `# HIESIR Codebook, series ${s.id}: the item as asked in ${R}`);
    h += `<h3>${t.cm.useTitle}</h3><div class="uses">` + use.map(u => `<div class="use"><span class="yrs">${ranges(u.ys)}</span>` +
      `<span class="codes">${u.k === 3 ? `<span class="muted">${esc(u.e.partial ? t.cm.partial(u.codes) : t.cm.inside(u.e.set.map(x => x.code).join(fa ? "، " : ", ")))}</span>` : u.codes.split(" + ").map(code).join(" + ")}</span>` +
      `<span class="st"><i class="sw s${u.k}"></i>${t.cm.st[u.k]}</span></div>`).join("") + `</div>` +
      `<div class="note">${t.cm.useNote(yr(R))}</div><button type="button" class="copy" data-copy="${esc(py)}">${t.cm.copy}</button>`;

    // wording history: the chains of the series
    if (s.chains.length > 1) {
      h += `<h3>${t.cm.history}</h3><div class="steps">`;
      for (const x of s.chains) {
        const l = x.ins.find(r => is11(r) && inSer.has(r.from[0]));
        const y0 = x.years.find(y => x.page.get(y));
        if (l) h += `<div class="link">${yr(l.year)} ${relPills(l)}</div>`;
        h += `<div class="step${x === c ? " cur" : ""}${x.id === S.focus ? " focus" : ""}"><div class="hd">${code(x.code)} <span class="pill">${ylabel(x)}</span>` +
          (pdfBase && y0 ? ` <a class="doc" href="${pdfUrl(x, y0)}" target="_blank" rel="noopener" data-pdf="${esc(x.id)}" data-year="${y0}" data-st="${stOf(cmp.get(y0))}" title="${esc(t.openPdf(yr(y0), num(x.page.get(y0))))}"></a>` : "") +
          `</div>${fat(x.text)}` + (l && l.note ? `<details class="note"><summary>${t.evidence}</summary>${esc(l.note)}</details>` : "") + `</div>`;
      }
      h += `</div>`;
    }

    // merges, splits and regroupings at the edges of the series
    const relBlock = r => {
      const side = ids => `<ul>${ids.map(i => { const x = M.CH.get(i); return x ? `<li class="${inSer.has(x.id) ? "me" : ""}">${inSer.has(x.id) ? code(x.code) : chainLink(x)}${fat(x.text)}</li>` : ""; }).join("")}</ul>`;
      return `<div class="rel"><div class="hd"><b>${yr(r.year)}</b> ${relPills(r)}</div><div class="sides">${side(r.from)}<span class="arrow">${ARROW}</span>${side(r.to)}</div>` +
        (r.note ? `<details class="note"><summary>${t.evidence}</summary>${esc(r.note)}</details>` : "") + `</div>`;
    };
    const before = [...new Set(s.chains.flatMap(x => x.ins.filter(r => !is11(r))))];
    const after = [...new Set(s.chains.flatMap(x => x.outs.filter(r => !is11(r))))];
    if (before.length) h += `<h3>${t.cameFrom}</h3>` + before.map(relBlock).join("");
    if (after.length) h += `<h3>${t.wentInto}</h3>` + after.map(relBlock).join("");

    const codes = [...new Set(s.chains.map(x => x.code))];
    const others = codes.flatMap(k => M.byCode.get(k) || []).filter(x => !inSer.has(x.id));
    if (others.length) {
      h += `<h3>${t.otherUnder(codes.map(code).join(fa ? "، " : ", "))}</h3>`;
      h += others.map(x => `<div class="link">${chainLink(x)} <span class="pill">${ylabel(x)}</span> ${fat(x.text)}</div>`).join("");
    }
    const corr = M.DATA.corrections.filter(k => codes.includes(k.expenditure_code) || codes.includes(k.value));
    if (corr.length) {
      h += `<h3>${t.corrections}</h3>`;
      h += corr.map(k => `<div class="rel"><div class="hd"><b>${yr(k.year)}</b> <span class="pill warn">${esc(k.action)}</span> ${code(k.expenditure_code)}${k.value ? ` ${ARROW} ${/^\d+$/.test(k.value) ? code(k.value) : fat(k.value)}` : ""}</div>${fat(k.description, "div")}<div class="note" dir="ltr">${esc(k.reason)}</div></div>`).join("");
    }
    return h;
  }
  return { render };
}
