/* Changes by year: the kinds as filter chips, the table of sections by
 * year, and the changes in the cell, row or column picked. */
import { KINDS, corrChain, events } from "../core/changes.js";
import { chainLink, code, esc, fat, gLink } from "./html.js";

export function createChangesView(ctx) {
  const { M, t, pdfBase, pdfUrl } = ctx;
  const { num, yr, span, ylabel, ARROW } = ctx.fmt;
  const { secTitle, secKind, relPills } = ctx.labels;
  const prevOf = y => M.YEARS[M.YEARS.indexOf(y) - 1];

  /* the view as HTML. ch, the selection: { sec, y } (a cell, a row, a column
     or nothing: null) and kinds, the set of kinds shown */
  function render(ch) {
    const inSel = e => (ch.sec === null || e.sec === ch.sec) && (ch.y === null || e.y === ch.y);
    const ev = events(M), secs = Object.keys(M.DATA.sections).map(Number), ys = M.YEARS;
    const on = ev.filter(e => ch.kinds.has(e.kind));
    const cnt = new Map(), rowT = new Map(), colT = new Map();
    let max = 1, total = 0;
    for (const e of on) {
      total += e.n;
      colT.set(e.y, (colT.get(e.y) || 0) + e.n);
      if (e.sec === null) continue;
      const key = `${e.sec}-${e.y}`, v = (cnt.get(key) || 0) + e.n;
      cnt.set(key, v); max = Math.max(max, v);
      rowT.set(e.sec, (rowT.get(e.sec) || 0) + e.n);
    }
    const shade = n => {
      if (!n) return "";
      const a = 0.12 + 0.88 * Math.sqrt(n / max);
      return `background:color-mix(in srgb, var(--accent) ${Math.round(a * 100)}%, var(--panel));color:${a > .55 ? "var(--on-accent)" : "var(--ink)"}`;
    };
    const selCls = (s, y) => {
      const c = [];
      if ((ch.sec === null || ch.sec === s) && (ch.y === null || ch.y === y) && (ch.sec !== null || ch.y !== null)) c.push(ch.sec !== null && ch.y !== null ? "sel" : "on");
      return c.join(" ");
    };
    // filter chips, with the count in the selection
    const inS = ev.filter(inSel);
    let h = `<div class="kinds" role="group" aria-label="${esc(t.ch.filter)}">` + KINDS.map(k => {
      const n = inS.filter(e => e.kind === k).reduce((a, e) => a + e.n, 0);
      return `<button type="button" class="kind${ch.kinds.has(k) ? " on" : ""}" data-hk="${k}" aria-pressed="${ch.kinds.has(k)}" title="${esc(`${t.ch.unit[k] || t.ch.unit.items} · ${t.ch.solo}`)}">${t.ch.kinds[k]} <b>${num(n)}</b></button>`;
    }).join("") + `<button type="button" class="kind reset" data-hk="">${t.ch.reset}</button></div>`;
    // the table
    h += `<div class="panel heat"><div class="cap">${t.ch.cap}</div><div class="heatwrap"><table>`;
    h += `<tr><th class="corner"><a data-hclear title="${esc(t.ch.clear)}">${ch.sec !== null || ch.y !== null ? "✕" : ""}</a></th>` +
      ys.map(y => `<th class="yh${y === ys[0] ? " base" : ""}${ch.y === y ? " on" : ""}" data-hy="${y}" title="${esc(y === ys[0] ? t.ch.base(yr(y)) : t.ch.pickYear(yr(prevOf(y)), yr(y)))}">${yr(y).slice(2)}</th>`).join("") +
      `<th class="yh tot">${t.ch.total}</th></tr>`;
    let band = "";
    for (const s of secs) {
      if (secKind(s) !== band) {
        band = secKind(s);
        const nums = secs.filter(x => secKind(x) === band);
        h += `<tr class="band"><th colspan="${ys.length + 2}"><b>${t.period.head[band]}</b> ${t.period.secs(span(nums[0], nums[nums.length - 1]))}</th></tr>`;
      }
      h += `<tr><th class="s${ch.sec === s ? " on" : ""}" data-hs="${s}" title="${esc(M.DATA.sections[s])}">${code(s)} ${fat(secTitle(s))}</th>`;
      for (const y of ys) {
        const n = cnt.get(`${s}-${y}`) || 0;
        h += `<td class="${n ? "" : "z"} ${selCls(s, y)}" data-hs="${s}" data-hy="${y}" title="${esc(`${yr(y)} · ${t.section(yr(s))}: ${num(n)}`)}" style="${shade(n)}">${n ? num(n) : ""}</td>`;
      }
      const rt = rowT.get(s) || 0;
      h += `<td class="tot${ch.sec === s && ch.y === null ? " on" : ""}" data-hs="${s}">${rt ? num(rt) : ""}</td></tr>`;
    }
    h += `<tr class="tots"><th class="s">${t.ch.total}</th>` + ys.map(y => `<td class="tot${ch.y === y && ch.sec === null ? " on" : ""}" data-hy="${y}">${colT.get(y) ? num(colT.get(y)) : ""}</td>`).join("") +
      `<td class="tot all">${num(total)}</td></tr></table></div>`;
    h += `<div class="heatleg"><span>${num(1)}</span><i></i><span>${num(max)}</span> ${t.ch.legend}</div></div>`;
    // the changes in the selection
    h += changeList(ch, inS.filter(e => ch.kinds.has(e.kind)));
    return h;
  }

  function changeList(ch, list) {
    if (ch.sec === null && ch.y === null) return `<div class="panel chlist empty">${t.ch.pick}</div>`;
    const where = ch.sec !== null ? `${t.section(yr(ch.sec))} · ${secTitle(ch.sec)}` : t.ch.allSections;
    const when = ch.y !== null ? (ch.y === M.YEARS[0] ? t.ch.base(yr(ch.y)) : `${yr(prevOf(ch.y))} ${ARROW} ${yr(ch.y)}`) : t.ch.allYears;
    const items = list.reduce((a, e) => a + e.n, 0);
    let h = `<div class="chhead"><h3 class="fa-mixed">${esc(where)} · ${when}</h3><span class="n">${t.ch.count(num(items), num(list.length))}</span></div>`;
    if (!list.length) return h + `<div class="panel chlist empty">${t.ch.none}</div>`;
    const many = ch.y === null, wide = ch.sec === null;
    const tag = e => (many ? `<span class="pill yr">${yr(e.y)}</span>` : "") + (wide && e.sec !== null ? `<span class="pill">${t.section(yr(e.sec))}</span>` : "");
    const item = c => `<div class="side">${chainLink(c)}${fat(c.text)}</div>`;
    const side = ids => `<div class="side">${ids.map(i => M.CH.get(i)).filter(Boolean).map(item).join("")}</div>`;
    const gside = (gi, y) => `<div class="side"><div class="gh">${M.nodeOfG[gi] ? gLink(M.nodeOfG[gi].id, code(M.G[gi][0])) : code(M.G[gi][0])}${fat(M.groupLabel(gi, y))}</div></div>`;
    const row = e => {
      if (e.r) return `<div class="yi">${side(e.r.from)}<span class="arrow">${ARROW}</span>${side(e.r.to)}<div class="reason">${tag(e)}${relPills(e.r)}</div></div>`;
      if (e.c) return `<div class="yi single">${chainLink(e.c)}<div>${fat(e.c.text)}</div><div class="reason">${tag(e)}<span class="pill">${ylabel(e.c)}</span></div></div>`;
      if (e.g) return `<div class="yi">${gside(e.g[0], prevOf(e.y))}<span class="arrow">${ARROW}</span>${gside(e.g[1], e.y)}<div class="reason">${tag(e)}<span class="pill info">${t.ch.grel[e.g[2]] || e.g[2]}</span> ${t.ch.moved(num(e.g[4]))}</div></div>`;
      const k = e.k, c = corrChain(M, k), y = +k.year, pg = c && c.page.get(y);
      return `<div class="yi single">${code(k.expenditure_code || "—")}<div><span class="pill warn">${esc(k.action)}</span> ${fat(k.description)}` +
        `${k.value ? ` ${ARROW} ${/^\d+$/.test(k.value) ? code(k.value) : fat(k.value)}` : ""}` +
        (pdfBase && pg ? ` <a class="doc" href="${pdfUrl(c, y)}" target="_blank" rel="noopener" data-pdf="${esc(c.id)}" data-year="${y}" title="${esc(t.openPdf(yr(y), num(pg)))}"></a>` : "") +
        `</div><div class="reason">${tag(e)}<span dir="ltr">${esc(k.reason)}</span></div></div>`;
    };
    for (const k of KINDS) {
      const es = list.filter(e => e.kind === k).sort((a, b) => a.y - b.y || (a.sec ?? 99) - (b.sec ?? 99));
      if (!es.length) continue;
      const n = es.reduce((a, e) => a + e.n, 0);
      const title = k === "dropped" ? (ch.y !== null ? t.groups.dropped(yr(prevOf(ch.y))) : t.ch.droppedAny) : k === "groups" ? t.ch.groupsTitle : t.groups[k];
      h += `<div class="panel group"><h3>${title} <span class="n">${n === es.length ? num(n) : t.ch.count(num(n), num(es.length))}</span></h3>${es.map(row).join("")}</div>`;
    }
    return h;
  }
  return { render };
}
