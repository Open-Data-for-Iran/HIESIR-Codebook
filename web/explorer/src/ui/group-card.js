/* A heading's page (a group or a section): where it sits, its codes over
 * the years, how each year compares with the reference year, what differs
 * year by year, its subgroups and items, its links with other headings. */
import { gcompare } from "../core/compare.js";
import { codesSnippet } from "../core/snippets.js";
import { chainLink, code, esc, fat, gLink, locateBtns } from "./html.js";

export function createGroupCard(ctx) {
  const { M, t, pdfBase, pdfUrl, state: S } = ctx;
  const { num, yr, span, ylabel, ranges, ARROW } = ctx.fmt;
  const { secTitle, nodeLabel } = ctx.labels;
  const { verdictHtml, timelineHtml, gtip } = ctx.timeline;

  /* the page of heading node id as HTML; null when there is none */
  function render(id) {
    const n = M.NODES.get(id);
    if (!n) return null;
    const R = ctx.nodeRef(n), cmp = gcompare(M, n, R), memR = cmp.get(R).mem;
    const gi = n.kind === "g" ? n.giAt(R) : null, sec = n.kind === "s" ? n.sec : M.G[gi][3];
    // the headings above it, read from an item under it
    const path = gi !== null && memR.length ? memR[0].groupsAt(R) : [];
    const above = gi !== null ? path.slice(0, path.indexOf(gi)) : [];
    let h = `<div class="crumbs fa">` + (n.kind === "g" ? [gLink(`s${sec}`, esc(M.sectionTitle(sec, R))), ...above.map(i => M.nodeOfG[i] ? gLink(M.nodeOfG[i].id, esc(M.groupLabel(i, R))) : esc(M.groupLabel(i, R)))]
      .map(x => `<span>${x}</span>`).join("") : "") + `</div>`;
    h += `<div class="title fa">${esc(nodeLabel(n, R))}${locateBtns(t)}</div>`;
    // codes by period: 0444 1384–1389 → 0443 1390–1403
    const periods = [];
    if (n.kind === "g") {
      for (const i of n.gis) {
        if (!M.GY[i].length) continue;
        const p = periods[periods.length - 1], a = M.GY[i][0], b = M.GY[i][M.GY[i].length - 1];
        if (p && p.code === M.G[i][0]) p.b = b; else periods.push({ code: M.G[i][0], a, b });
      }
    } else periods.push({ code: String(n.sec), a: n.years[0], b: n.last });
    h += `<div class="ids">${periods.map(p => `${code(p.code)} <span class="yrs">${span(p.a, p.b)}</span>`).join(` <span class="arrow">${ARROW}</span> `)}` +
      ` <span class="pill">${n.kind === "g" ? t.g.kind.g(yr(M.G[gi][2])) : t.g.kind.s}</span>` +
      (n.kind === "g" ? ` <span class="pill">${t.section(yr(sec))}</span>` : "") +
      ` <span class="pill">${t.g.items(num(memR.length))}</span>` + (n.kind === "g" ? ` <span class="pill" title="${t.groupId}">${esc(n.id)}</span>` : "") + `</div>`;
    if (S.ref && !n.years.includes(S.ref)) h += `<div class="note">${t.cm.notInRef(yr(S.ref))}</div>`;

    h += verdictHtml(cmp, R, t.g.seenFrom, t.g.st);
    // timeline: a click opens its items on the printed form
    h += `<h3>${t.timeline}</h3><div class="pdfhint">${pdfBase ? t.g.hint : t.refHint}</div>`;
    h += timelineHtml(cmp, R, n.years, t.g.st, (y, e) => ({ chains: e ? e.mem.filter(x => pdfUrl(x, y)) : [], tip: gtip(y, e) }));

    // what differs, year by year: consecutive years with the same differences in one row
    const where = (c, y) => { const g = c.groupsAt(y); return g.length ? M.groupLabel(g[g.length - 1], y) : secTitle(c.secAt(y), y); };
    const rows = [];
    for (const y of M.YEARS) {
      const e = cmp.get(y);
      if (!e || e.st === null) continue;
      const k = e.st === "ref" ? 0 : e.st;
      const sig = [k, e.mem.length, ...[e.plus, e.moved, e.gone, e.miss].map(l => l.map(c => c.id).join())].join("|");
      const last = rows[rows.length - 1];
      if (last && last.sig === sig && M.YEARS.indexOf(y) === M.YEARS.indexOf(last.ys[last.ys.length - 1]) + 1) last.ys.push(y);
      else rows.push({ sig, k, ys: [y], e });
    }
    // a list of codes, folded after the first six; the years of each chain
    // where the same code can be two items (removed, or not asked)
    const list = (cs, y, label, sign, years = false) => {
      if (!cs.length) return "";
      const one = c => `<span title="${esc(`${c.text} · ${where(c, y)}`)}">${sign}${chainLink(c)}${years ? ` <span class="yrs">${ylabel(c)}</span>` : ""}</span>`;
      const head = cs.slice(0, 6).map(one).join(" "), rest = cs.slice(6);
      return `<div class="gdiff"><span class="muted">${label}</span> ${head}` +
        (rest.length ? ` <details class="more"><summary>${t.g.more(num(rest.length))}</summary>${rest.map(one).join(" ")}</details>` : "") + `</div>`;
    };
    // a label broadened or narrowed: the link and the item it reached
    const viaList = e => {
      if (!e.via.length) return "";
      const one = r => `<span class="via" title="${esc(`${t.det[r.detail]} ${yr(r.year)}`)}">${r.to.map(id => M.CH.get(id)).filter(Boolean).map(chainLink).join(" ")} <span class="yrs">${t.det[r.detail]} ${yr(r.year)}</span></span>`;
      const rest = e.via.slice(6);
      return `<div class="gdiff"><span class="muted">${t.g.via}</span> ${e.via.slice(0, 6).map(one).join(" · ")}` +
        (rest.length ? ` <details class="more"><summary>${t.g.more(num(rest.length))}</summary>${rest.map(one).join(" · ")}</details>` : "") + `</div>`;
    };
    h += `<h3>${t.g.useTitle}</h3><div class="uses">` + rows.map(u => {
      const y = u.ys[0], e = u.e;
      const body = e.st === 3 ? `<span class="muted">${t.g.inside}${e.broken ? `: ${e.broken.from.concat(e.broken.to).map(id => M.CH.get(id)).filter(Boolean).map(chainLink).join(" ")}` : ""}</span>`
        : list(e.plus, y, t.g.plus, "+") + list(e.moved, y, t.g.movedIn, "−") + list(e.gone, y, t.g.gone, "−", true) + list(e.miss, y, t.g.miss, "", true) + viaList(e);
      return `<div class="use"><span class="yrs">${ranges(u.ys)}</span><span class="codes gcodes">${t.g.items(num(e.mem.length))}${body}</span>` +
        `<span class="st"><i class="sw s${u.k}"></i>${e.st === "ref" ? t.cm.ref : t.g.st[u.k]}</span></div>`;
    }).join("") + `</div>`;
    const py = codesSnippet(M.YEARS, cmp, t.g.pyHead(n.id, R));
    h += `<div class="note">${t.g.useNote(yr(R))}</div><button type="button" class="copy" data-copy="${esc(py)}">${t.cm.copy}</button>`;

    // what is under it in the reference year: its subgroups, then its items
    const depth = gi !== null ? path.indexOf(gi) + 1 : 0, subs = new Map();
    for (const c of memR) {
      const g = c.groupsAt(R)[depth];
      if (g !== undefined && M.nodeOfG[g]) subs.set(g, (subs.get(g) || 0) + 1);
    }
    if (subs.size) {
      h += `<h3>${t.g.sub}</h3>` + [...subs].sort((a, b) => M.G[a[0]][0].localeCompare(M.G[b[0]][0]))
        .map(([g, k]) => `<div class="link">${gLink(M.nodeOfG[g].id, code(M.G[g][0]))} ${fat(M.groupLabel(g, R))} <span class="muted">${t.g.nItems(num(k))}</span></div>`).join("");
    }
    h += `<details class="members"${memR.length <= 40 ? " open" : ""}><summary><h3>${t.g.members(yr(R), num(memR.length))}</h3></summary>` +
      memR.map(c => `<div class="link">${chainLink(c)} ${fat(c.text)}</div>`).join("") + `</details>`;

    // links with other headings
    if (n.kind === "g") {
      const mine = new Set(n.gis);
      const gl = (M.DATA.groupLinks || []).filter(l => mine.has(l[0]) || mine.has(l[1])).sort((a, b) => a[3] - b[3]);
      if (gl.length) {
        const side = (i, y) => { const id = M.nodeOfG[i]?.id, lab = `${code(M.G[i][0])} ${fat(M.groupLabel(i, y))}`; return mine.has(i) || !id ? `<div class="me">${lab}</div>` : `<div>${gLink(id, lab)}</div>`; };
        h += `<h3>${t.g.links}</h3>` + gl.map(([a, b, rel, y, k]) => `<div class="rel"><div class="hd"><b>${yr(y)}</b> <span class="pill ${rel === "continued" ? "info" : "bad"}">${t.ch.grel[rel] || rel}</span>` +
          (k ? ` <span class="muted">${t.g.nItems(num(k))}</span>` : "") + `</div><div class="sides">${side(a, M.YEARS[M.YEARS.indexOf(y) - 1])}<span class="arrow">${ARROW}</span>${side(b, y)}</div></div>`).join("");
      }
    }
    return h;
  }
  return { render };
}
