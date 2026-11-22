/* HIES explorer: search and browse the questionnaire items across years.
 *
 * Mounts into every element with class "hx". Attributes on that element:
 *   data-lang  "en" or "fa" (Farsi switches the whole component to right-to-left)
 *   data-root  URL prefix of the published files (3_items/, 2_corrected/)
 *   data-src   URL of data.json; omitted when window.HX_DATA is embedded
 *   data-docs  URL of the methods page (optional)
 *   data-pdf   URL prefix of the questionnaire PDFs (optional); items then link
 *              to the page they are printed on
 * Used both by the standalone page (output/explorer/index.html) and by the
 * MkDocs page (docs/explorer.md), so the two never drift apart. The text it
 * shows is in i18n/. An ES module: hiesir_codebook.explorer bundles it, with
 * what it imports, into one script for the two pages.
 */
import { STRINGS as T } from "./i18n/index.js";
import { DEFAULT_KINDS, KINDS, corrChain, events } from "./core/changes.js";
import { compare, gcompare } from "./core/compare.js";
import { is11, model } from "./core/model.js";
import { search } from "./core/search.js";
import { codesSnippet } from "./core/snippets.js";
import { FA_DIGITS, norm } from "./core/text.js";

const esc = s => String(s ?? "").replace(/[&<>"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));

/* ---------- PDF.js, loaded from the CDN on the first click ---------- */
const PDFJS = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/";
let pdfjsLib = null;
const pdfDocs = new Map();
async function pdfDoc(url) {
  if (!pdfjsLib) {
    pdfjsLib = await import(PDFJS + "pdf.min.mjs");
    pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS + "pdf.worker.min.mjs";
  }
  if (!pdfDocs.has(url)) {
    const task = pdfjsLib.getDocument({ url, isEvalSupported: false });
    pdfDocs.set(url, task.promise.catch(err => { pdfDocs.delete(url); throw err; }));
  }
  return pdfDocs.get(url);
}

/* ---------- one mounted component ---------- */
function mount(root, M) {
  const lang = root.dataset.lang === "fa" ? "fa" : "en";
  const t = T[lang], fa = lang === "fa";
  const filesRoot = root.dataset.root || "../";
  const docs = root.dataset.docs || "";
  const pdfBase = root.dataset.pdf || "";
  const pdfUrl = (c, y) => pdfBase && c.page.get(y) ? `${pdfBase}questionnaire_${y}.pdf#page=${c.page.get(y)}` : "";
  root.setAttribute("dir", fa ? "rtl" : "ltr");
  root.setAttribute("lang", lang);

  const num = n => Number(n).toLocaleString(fa ? "fa-IR" : "en-US");
  const yr = y => fa ? String(y).replace(/\d/g, d => FA_DIGITS[d]) : String(y);
  const yrs = ys => ys.map(yr).join(fa ? "، " : ", ");
  const span = (a, b) => a === b ? yr(a) : `${yr(a)}–${yr(b)}`;
  const ylabel = c => span(c.first, c.last);
  const ARROW = fa ? "←" : "→";
  const PERIOD = /\s*(?:خانوار\s*)?(?:در\s+(12|۱۲)?\s*ماه گذشته)?\s*$/;
  const secTitle = (s, y = null) => M.sectionTitle(s, y).replace(/^هزینه‌(های|ی) /, "").replace(PERIOD, "");
  const secPeriod = s => { const m = (M.DATA.sections[s] || "").match(/در\s+(12|۱۲)?\s*ماه گذشته\s*$/); return m ? (m[1] ? t.period.y : t.period.m) : ""; };
  const secHead = (s, y = null) => `${code(s)}${fat(secTitle(s, y), "span", "st")}`;
  // the period a section asks about: "m" last month, "y" last 12 months
  // (a section whose latest title names none goes with its neighbours)
  const secKind = s => /در\s+(12|۱۲)\s*ماه گذشته\s*$/.test(M.DATA.sections[s] || "") ? "y" : "m";
  const fat = (s, tag = "span", cls = "") => `<${tag} class="fa ${cls}">${esc(s)}</${tag}>`;
  const code = s => `<span class="code">${esc(s)}</span>`;
  const chainLink = c => `<a data-go="${esc(c.id)}">${code(c.code)}</a>`;

  function relPills(r) {
    let h = `<span class="pill ${r.rel === "same" || r.rel === "recoded" ? "info" : "bad"}">${t.rel[r.rel] || r.rel}</span>`;
    const d = r.detail && t.det[r.detail];
    if (d) h += ` <span class="pill ${r.detail === "label_broadened" || r.detail === "label_narrowed" ? "warn" : r.detail === "minor" ? "" : "info"}">${d}</span>`;
    return h + " " + verifPill(r);
  }
  function verifPill(r) {
    if (r.verified === "confirmed") return `<span class="pill ok" title="${t.v.confirmedTip}">${t.v.confirmed}</span>`;
    if (r.verified === "changed") return `<span class="pill info" title="${t.v.changedTip}">${t.v.changed}</span>`;
    if (r.verified === "added") return `<span class="pill info" title="${t.v.addedTip}">${t.v.added}</span>`;
    if (!r.check) return `<span class="pill ok" title="${t.v.definiteTip}">${t.v.definite}</span>`;
    return `<span class="pill bad">${t.v.unverified}</span>`;
  }
  const refOf = s => (ref && s.years.includes(ref) ? ref : s.last);
  // some year can express the item only with a scope change, by adding codes, or not at all
  const notFull = s => [...compare(M, s, refOf(s)).values()].some(e => e.st === 1 || e.st === 2 || e.st === 3);
  const stOf = e => !e || e.st === null ? "" : e.st === "ref" ? 0 : e.st;
  const stCls = e => !e || e.st === null ? "" : e.st === "ref" ? "s0 ref" : `s${e.st}`;
  function strip(s) {
    const cmp = compare(M, s, refOf(s));
    return `<span class="strip">` + M.YEARS.map(y => `<i class="${stCls(cmp.get(y))}"></i>`).join("") + `</span>`;
  }
  /* consecutive survey years as ranges: 1383–1389، 1391 */
  function ranges(list) {
    const idx = list.map(y => M.YEARS.indexOf(y)).sort((a, b) => a - b), parts = [];
    for (let i = 0; i < idx.length; i++) {
      let j = i;
      while (j + 1 < idx.length && idx[j + 1] === idx[j] + 1) j++;
      parts.push(span(M.YEARS[idx[i]], M.YEARS[idx[j]]));
      i = j;
    }
    return parts.join(fa ? "، " : ", ");
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

  /* skeleton */
  const sectionOpts = Object.keys(M.DATA.sections).map(n => `<option value="${n}">${yr(n)} · ${esc(secTitle(n).slice(0, 48))}${secPeriod(n) ? ` (${secPeriod(n)})` : ""}</option>`).join("");
  root.innerHTML = `
    <nav class="hx-tabs">
      <a data-tab="items" href="#">${t.tabs.items}</a>
      <a data-tab="years" href="#changes">${t.tabs.years}</a>
      <a data-tab="about" href="#about">${t.tabs.about}</a>
    </nav>
    <section class="hx-view" data-view="items">
      <div class="hx-search">
        <input class="hx-q" type="search" autocomplete="off" spellcheck="false" placeholder="${esc(t.placeholder)}" aria-label="${esc(t.placeholder)}">
        <select class="hx-sec"><option value="">${t.allSections}</option>${sectionOpts}</select>
        <label class="chip" title="${esc(t.notFullTip)}"><input type="checkbox" class="hx-linked"> ${t.notFull}</label>
        <label class="chip" title="${esc(t.cm.yearTip)}">${t.cm.yearLabel} <select class="hx-ref">${[...M.YEARS].reverse().map(y => `<option value="${y}">${yr(y)}</option>`).join("")}<option value="all">${t.cm.yearAll}</option></select></label>
      </div>
      <div class="hint">${t.hint}</div>
      <div class="split">
        <div class="panel hx-list"></div>
        <div class="panel hx-detail"></div>
      </div>
    </section>
    <section class="hx-view" data-view="years"></section>
    <section class="hx-view" data-view="about"><div class="panel about">${t.about(filesRoot, docs)}</div></section>`;
  const $ = s => root.querySelector(s);
  const elQ = $(".hx-q"), elSec = $(".hx-sec"), elLinked = $(".hx-linked"), elRef = $(".hx-ref");
  const elList = $(".hx-list"), elDetail = $(".hx-detail"), elYears = $('[data-view="years"]');
  let selected = null, focus = null, ref = M.LAST;  // null: all items
  let selGroup = null;  // the heading whose page is shown (a group or a section), instead of an item

  /* the list: sections, then the printed group headers (levels 2-4) as a
     tree, each item under its groups in the year it is compared with */
  /* what is open: a level (0 the sections only, 1 their groups, ...)
     and the headings opened or closed against it. Browsing and a search
     (or a list short enough to open whole) each keep their own; a new
     search starts fully open and keeps what is folded while typing */
  const LEVELS = [0, 1, 2, Infinity];
  const newFold = () => ({ level: null, base: 0, open: new Set(), closed: new Set() });
  const foldBrowse = newFold();
  let foldAuto = newFold(), fold = foldBrowse;
  const lvl = f => f.level ?? f.base;
  function setFold(key, open, depth) {
    const def = depth < lvl(fold);
    fold.open.delete(key); fold.closed.delete(key);
    if (open && !def) fold.open.add(key);
    if (!open && def) fold.closed.add(key);
  }
  /* a heading's dot: the colour of its least comparable year, as on its
     page; hovering it shows the whole timeline */
  const nodeCmp = id => { const n = M.NODES.get(id); if (!n) return null; const R = nodeRef(n); return { n, R, cmp: gcompare(M, n, R) }; };
  function gdot(id) {
    const x = id && nodeCmp(id);
    if (!x) return "";
    let w = 0;
    for (const e of x.cmp.values()) if (typeof e.st === "number") w = Math.max(w, e.st);
    return `<span class="gdot s${w}" data-gdot="${esc(id)}" title=""></span>`;
  }
  const pop = document.createElement("div");
  pop.className = "gpop"; pop.hidden = true; pop.setAttribute("role", "tooltip");
  root.appendChild(pop);
  function showPop(dt) {
    const x = nodeCmp(dt.dataset.gdot);
    if (!x) return;
    pop.innerHTML = `<div class="gp-h">${t.g.seenFrom(`<span class="refy">${yr(x.R)}</span>`)}</div>` +
      `<div class="gp-tl" style="grid-template-columns:repeat(${M.YEARS.length},1fr)">` +
      M.YEARS.map(y => `<i class="${stCls(x.cmp.get(y))}"></i>`).join("") +
      M.YEARS.map(y => `<span${y === x.R ? ` class="ref"` : ""}>${yr(y).slice(2)}</span>`).join("") + `</div>` +
      `<ul>${spans(byState(x.cmp), t.g.st)}</ul>`;
    pop.hidden = false;
    const r = dt.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    const left = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2));
    const top = r.bottom + 8 + h > innerHeight ? r.top - 8 - h : r.bottom + 8;
    pop.style.left = left + "px"; pop.style.top = top + "px";
  }
  elList.addEventListener("mouseover", e => { const dt = e.target.closest("[data-gdot]"); if (dt) showPop(dt); });
  elList.addEventListener("mouseout", e => { if (e.target.closest("[data-gdot]")) pop.hidden = true; });
  elList.addEventListener("scroll", () => { pop.hidden = true; }, { passive: true });

  function renderList() {
    const res = search(M, elQ.value), sec = elSec.value;
    const rows = (res || M.SER.map(s => [s, 0, null])).map(([s, rank, hit]) => [s, rank, hit, s.at(refOf(s))])
      .filter(([s, , , c]) => c && (!ref || s.years.includes(ref)) && (!sec || c.secAt(refOf(s)) == sec) && (!elLinked.checked || notFull(s)));
    const top = new Map();
    const node = (kids, key, extra) => kids.get(key) || kids.set(key, { key, kids: new Map(), items: [], n: 0, min: "~", ...extra }).get(key);
    for (const row of rows) {
      const c = row[3];
      const sn = c.secAt(refOf(row[0]));
      let n = node(top, `s${sn}`, { sec: sn });
      const trail = [n];
      for (const gi of c.groupsAt(refOf(row[0]))) { n = node(n.kids, `${n.key}/${gi}`, { g: M.G[gi], gi }); trail.push(n); }
      n.items.push(row);
      for (const x of trail) { x.n++; if (c.code < x.min) x.min = c.code; }
    }
    const auto = !!res || rows.length < 80;
    if (auto && fold !== foldAuto) foldAuto = newFold();
    fold = auto ? foldAuto : foldBrowse;
    fold.base = auto ? Infinity : sec || top.size === 1 ? 1 : 0;
    const isOpen = (n, depth) => fold.open.has(n.key) || (!fold.closed.has(n.key) && depth < lvl(fold));
    const item = ([s, , hit, c, past]) => `<div class="row${past ? " past" : ""}${selected === s.id && !past ? " sel" : ""}" data-id="${esc(s.id)}">${code(c.code)}${fat(c.text, "div")}` +
      (hit && hit !== c ? `<div class="was">${t.cm.earlier}: <span class="fa">${esc(hit.text)}</span></div>` : "") +
      `<div class="meta">${strip(s)}<span class="yrs">${span(s.years[0], s.last)}</span></div></div>`;
    const gLabel = n => M.groupLabel(n.gi, ref);
    const same = (a, b) => norm(a).includes(norm(b)) || norm(b).includes(norm(a));
    function draw(n, depth, label) {
      // a group alone under a parent of the same name adds nothing: show its contents
      if (n.g && label && n.kids.size === 1 && !n.items.length) {
        const only = [...n.kids.values()][0];
        if (same(gLabel(n), label)) return draw(only, depth, label);
      }
      // a group's heading: its code, its label, and the years it is printed
      // when that is not every year (most groups are printed in all of them)
      const gYears = n.g && M.nodeOfG[n.gi] && M.nodeOfG[n.gi].years.length < M.YEARS.length ? M.nodeOfG[n.gi].years : null;
      const head = n.sec ? secHead(n.sec, ref) : `${code(n.g[0])}${fat(gLabel(n))}` + (gYears ? `<span class="yrs">${ranges(gYears)}</span>` : "");
      const parts = [...n.kids.values()].map(k => [k.min, k]).concat(n.items.map(r => [r[3].code, r]));
      parts.sort((a, b) => a[0].localeCompare(b[0]) || (Array.isArray(a[1]) ? 1 : -1));
      const body = (n.movedTo ? `<div class="secnote">${t.period.movedFrom([...n.movedTo].sort((a, b) => a - b).map(yr).join(fa ? "، " : ", "), yr(n.until))}</div>` : "") +
        parts.map(([, x]) => Array.isArray(x) ? item(x) : draw(x, depth + 1, n.sec ? secTitle(n.sec, ref) : gLabel(n))).join("");
      // the fold button, or an empty slot of its width, so what is beside it lines up
      const fb = body.includes("<details") ? `<span class="fold" data-fold role="button" title="${esc(t.tree.fold)}" aria-label="${esc(t.tree.fold)}"></span>` : `<span class="fold none" aria-hidden="true"></span>`;
      const nid = n.sec ? `s${n.sec}` : M.nodeOfG[n.gi]?.id || "";
      return `<details class="${n.sec ? "sec" : "grp"}" data-key="${esc(n.key)}" data-d="${depth}" style="--d:${depth}"${isOpen(n, depth) ? " open" : ""}>` +
        `<summary${nid ? ` data-g="${esc(nid)}"` : ""}${nid && nid === selGroup ? ` class="sel"` : ""} title="${esc(`${n.g ? gLabel(n) : M.sectionTitle(n.sec, ref)} · ${t.tree.head}`)}">${head}${fb}${gdot(nid)}<span class="n">${num(n.n)}</span></summary>${body}</details>`;
    }
    const cur = lvl(fold);
    const levels = rows.length ? `<span class="levels" role="group" aria-label="${esc(t.tree.label)}">` + LEVELS.map((L, i) =>
      `<button type="button" data-level="${i}" class="${L === cur ? "on" : ""}" aria-pressed="${L === cur}" title="${esc(t.tree.tips[i])}">${t.tree.levels[i]}</button>`).join("") + `</span>` : "";
    let h = `<div class="count"><span>${t.count(num(rows.length), !!res)}</span>${levels}</div>`;
    if (!rows.length) h += `<div class="empty">${t.noMatch}</div>`;
    // two blocks, one per period asked about; a section with no item here
    // whose items are listed under another section says where they went
    const filtered = res || sec || elLinked.checked;
    const moved = new Map();
    if (!filtered) {
      for (const s of M.SER) {
        const y = refOf(s), c = s.at(y);
        if (!c || (ref && !s.years.includes(ref)) || top.has(`s${c.s}`)) continue;
        (moved.get(c.s) || moved.set(c.s, new Set()).get(c.s)).add(c.secAt(y));
      }
      /* under "All items" such a section (10 in 1383, whose two items are
         in section 13 from 1384) still lists its items, as last asked in
         it; they appear under their later section too ("past" rows: a
         link to the item goes to the other one) */
      if (ref === null) {
        for (const [sn, to] of moved) {
          for (const s of M.SER) {
            const y = [...s.years].reverse().find(y => s.at(y).secAt(y) === sn);
            if (y === undefined) continue;
            const c = s.at(y), sec0 = node(top, `s${sn}`, { sec: sn, movedTo: to, until: y });
            if (y > sec0.until) sec0.until = y;
            let n = sec0;
            const trail = [n];
            for (const gi of c.groupsAt(y)) { n = node(n.kids, `${n.key}/${gi}`, { g: M.G[gi], gi }); trail.push(n); }
            n.items.push([s, 0, null, c, true]);
            for (const x of trail) { x.n++; if (c.code < x.min) x.min = c.code; }
          }
          moved.delete(sn);
        }
      }
    }
    for (const kind of ["m", "y"]) {
      const nodes = [...top.values()].filter(n => secKind(n.sec) === kind).sort((a, b) => a.sec - b.sec);
      const gone = [...moved].filter(([n]) => secKind(n) === kind);
      if (!nodes.length && !gone.length) continue;
      const nums = nodes.map(n => n.sec);
      h += `<div class="perhead"><b>${t.period.head[kind]}</b>` +
        (nums.length ? `<span>${t.period.secs(span(nums[0], nums[nums.length - 1]))}</span>` : "") +
        // (a past section's items are counted under their later section)
        `<span class="n">${num(nodes.reduce((a, n) => a + (n.movedTo ? 0 : n.n), 0))}</span></div>`;
      const parts = nodes.map(n => [n.sec, draw(n, 0, "")])
        .concat(gone.map(([n, to]) => [n, `<div class="secmoved">${code(n)}${fat(secTitle(n), "span", "st")}<span class="to">${t.period.moved([...to].sort((a, b) => a - b).map(yr).join(fa ? "، " : ", "))}</span></div>`]));
      h += parts.sort((a, b) => a[0] - b[0]).map(x => x[1]).join("");
    }
    elList.innerHTML = h;
    applyTops();
  }
  /* the open headings stick below the count bar while their rows scroll,
     each below its parents: its top is the sum of their heights. Set at
     once after drawing the list; after a heading opens or closes (many at
     once for a whole branch) on a timer, once for them all; a timer, not
     an animation frame, so it also runs in a hidden tab */
  function applyTops() {
    const bar = elList.querySelector(".count");
    const walk = (d, top) => {
      const s = d.firstElementChild;
      s.style.top = top + "px";
      if (d.open) for (const k of d.querySelectorAll(":scope > details")) walk(k, top + s.offsetHeight);
    };
    for (const d of elList.querySelectorAll(":scope > details")) walk(d, bar ? bar.offsetHeight : 0);
  }
  let stickTimer = 0;
  function stickTops() { clearTimeout(stickTimer); stickTimer = setTimeout(applyTops, 0); }
  new ResizeObserver(stickTops).observe(elList);
  /* the list sticks to the top of the window like the item card: while it
     is still below its sticky place, the wheel scrolls the page, so the list
     never hides its last rows below the window */
  elList.addEventListener("wheel", e => {
    if (e.deltaY <= 0 || e.ctrlKey || getComputedStyle(elList).position !== "sticky") return;
    const top = parseFloat(getComputedStyle(elList).top) || 0, gap = elList.getBoundingClientRect().top - top;
    const room = document.documentElement.scrollHeight - innerHeight - scrollY;
    if (gap > 1 && room > 1) { e.preventDefault(); scrollBy(0, Math.min(gap, e.deltaY * (e.deltaMode === 1 ? 16 : 1))); }
  }, { passive: false });
  /* opening and closing a heading is remembered, while browsing and while searching */
  elList.addEventListener("toggle", e => {
    const d = e.target;
    if (d.matches && d.matches("details[data-key]")) { setFold(d.dataset.key, d.open, +d.dataset.d); stickTops(); }
  }, true);
  /* a level button; the fold button of a heading or an Alt- or Shift-click
     on it opens or closes everything under it */
  elList.addEventListener("click", e => {
    const lb = e.target.closest("[data-level]");
    if (lb) {
      fold.level = LEVELS[+lb.dataset.level]; fold.open.clear(); fold.closed.clear();
      renderList(); return;
    }
    const sm = e.target.closest("summary"), fb = e.target.closest("[data-fold]");
    /* the title opens the heading's page, and the heading if it is closed
       (a second click on the heading shown opens or closes it); the arrow,
       and Enter or Space, only open or close it */
    if (sm && !fb && !e.altKey && !e.shiftKey && sm.dataset.g && e.detail) {
      const r = sm.getBoundingClientRect(), arrow = r.right - parseFloat(getComputedStyle(sm).paddingRight) - 16;
      if (e.clientX >= arrow) return;
      e.preventDefault();
      const d = sm.parentElement;
      if (selGroup === sm.dataset.g) { d.open = !d.open; return; }
      d.open = true;
      selectGroup(sm.dataset.g);
      return;
    }
    if (!sm || !(fb || e.altKey || e.shiftKey)) return;
    e.preventDefault();
    const d = sm.parentElement;
    const open = fb ? !d.open || !!d.querySelector("details:not([open])") : !d.open;
    for (const x of [d, ...d.querySelectorAll("details[data-key]")]) { setFold(x.dataset.key, open, +x.dataset.d); x.open = open; }
    getSelection()?.removeAllRanges();
  });

  function emptyDetail() {
    const ex = ["برنج", "11114", "تلویزیون", "دندان"].map(q => `<a data-q="${q}">${q}</a>`);
    elDetail.innerHTML = `<div class="empty"><div class="big">${t.pick}</div>
      ${t.summary(num(M.SER.length), num(M.YEARS.length), num(M.DATA.relations.length))}<br>
      ${t.tryThese} ${ex.slice(0, 3).join(fa ? "، " : ", ")} ${t.or} ${ex[3]}</div>`;
  }

  function tip(y, e) {
    if (!e || e.st === null) return `${yr(y)}: ${t.cm.na}`;
    const codes = e.set.map(x => x.code);
    if (e.st === "ref") return `${yr(y)}: ${codes[0]} · ${t.cm.ref}`;
    if (e.st === 3) return `${yr(y)}: ${e.partial ? t.cm.partial(codes.join(" + ")) : t.cm.inside(codes.join(fa ? "، " : ", "))} · ${t.cm.st[3]}`;
    if (e.st === 2) return `${yr(y)}: ${t.cm.sum(codes.join(" + "))} · ${t.cm.st[2]}`;
    if (e.st === 1) return `${yr(y)}: ${codes[0]} · ${t.cm.st[1]} (${e.via.filter(is11).map(r => `${t.det[r.detail]} ${yr(r.year)}`).join(fa ? "، " : ", ")})`;
    return `${yr(y)}: ${codes[0]} · ${t.cm.st[0]}`;
  }

  /* the buttons after a card's title: back to it in the list; the same,
     with every other branch closed (two chevrons folding in on a line) */
  const locateBtns = () => `<button type="button" class="locate" data-locate title="${esc(t.cm.locate)}" aria-label="${esc(t.cm.locate)}">` +
      `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" stroke-width="2"/>` +
      `<circle cx="12" cy="12" r="2.5" fill="currentColor"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>` +
      `<button type="button" class="locate" data-locate="only" title="${esc(t.cm.only)}" aria-label="${esc(t.cm.only)}">` +
      `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">` +
      `<path d="M8 4l4 4 4-4M8 20l4-4 4 4M4 12h16"/></svg></button>`;
  const renderSel = () => (selGroup ? renderGroup() : selected ? renderDetail(selected) : emptyDetail());
  const nodeRef = n => (ref && n.years.includes(ref) ? ref : n.last);
  const nodeLabel = (n, y) => (n.kind === "s" ? M.sectionTitle(n.sec, y) : M.groupLabel(n.giAt(y), y));
  const gLink = (id, label) => `<a data-group="${esc(id)}">${label}</a>`;

  function gtip(y, e) {
    if (!e || e.st === null) return `${yr(y)}: ${t.cm.na}`;
    const k = e.st === "ref" ? 0 : e.st, parts = [`${yr(y)}: ${t.g.items(num(e.mem.length))}`];
    if (e.plus.length) parts.push(`+${num(e.plus.length)}`);
    if (e.moved.length + e.gone.length) parts.push(`−${num(e.moved.length + e.gone.length)}`);
    if (e.miss.length) parts.push(`${t.g.miss}: ${num(e.miss.length)}`);
    return parts.join(" · ") + ` · ${e.st === "ref" ? t.cm.ref : t.g.st[k]}`;
  }

  function renderGroup() {
    const n = M.NODES.get(selGroup);
    if (!n) { emptyDetail(); return; }
    const R = nodeRef(n), cmp = gcompare(M, n, R), memR = cmp.get(R).mem;
    const gi = n.kind === "g" ? n.giAt(R) : null, sec = n.kind === "s" ? n.sec : M.G[gi][3];
    // the headings above it, read from an item under it
    const path = gi !== null && memR.length ? memR[0].groupsAt(R) : [];
    const above = gi !== null ? path.slice(0, path.indexOf(gi)) : [];
    let h = `<div class="crumbs fa">` + (n.kind === "g" ? [gLink(`s${sec}`, esc(M.sectionTitle(sec, R))), ...above.map(i => M.nodeOfG[i] ? gLink(M.nodeOfG[i].id, esc(M.groupLabel(i, R))) : esc(M.groupLabel(i, R)))]
      .map(x => `<span>${x}</span>`).join("") : "") + `</div>`;
    h += `<div class="title fa">${esc(nodeLabel(n, R))}${locateBtns()}</div>`;
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
      ` <span class="pill">${t.g.items(num(memR.length))}</span>` + (n.kind === "g" ? ` <span class="pill" title="${t.chainId}">${esc(n.id)}</span>` : "") + `</div>`;
    if (ref && !n.years.includes(ref)) h += `<div class="note">${t.cm.notInRef(yr(ref))}</div>`;

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
    elDetail.innerHTML = h;
    elDetail.scrollTop = 0;
  }

  function renderDetail(sid) {
    const s = M.serOf.get(sid);
    if (!s) { emptyDetail(); return; }
    const R = refOf(s), cmp = compare(M, s, R), c = s.at(R);
    const inSer = new Set(s.chains.map(x => x.id));

    // the headings above it, each a link to its page
    const gs = c.groupsAt(R), sn = c.secAt(R);
    const above = gs.length ? gs.map(gi => M.nodeOfG[gi] ? gLink(M.nodeOfG[gi].id, esc(M.groupLabel(gi, R))) : esc(M.groupLabel(gi, R)))
      : c.path.map(p => esc(p[1]));
    let h = `<div class="crumbs fa">${[M.NODES.has(`s${sn}`) ? gLink(`s${sn}`, esc(M.sectionTitle(sn, R))) : esc(M.sectionTitle(sn, R)), ...above].filter(Boolean).map(x => `<span>${x}</span>`).join("")}</div>`;
    h += `<div class="title fa">${esc(c.text)}${locateBtns()}</div>`;
    // codes by period: 011837 1383–1385 → 011174 1386–1403
    const periods = [];
    for (const x of s.chains) {
      const p = periods[periods.length - 1];
      if (p && p.code === x.code) p.b = x.last; else periods.push({ code: x.code, a: x.first, b: x.last });
    }
    h += `<div class="ids">${periods.map(p => `${code(p.code)} <span class="yrs">${span(p.a, p.b)}</span>`).join(` <span class="arrow">${ARROW}</span> `)}` +
      ` <span class="pill">${t.section(yr(c.secAt(R)))}</span> <span class="pill" title="${t.chainId}">${esc(s.id)}</span></div>`;
    if (ref && !s.years.includes(ref)) h += `<div class="note">${t.cm.notInRef(yr(ref))}</div>`;

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
        h += `<div class="step${x === c ? " cur" : ""}${x.id === focus ? " focus" : ""}"><div class="hd">${code(x.code)} <span class="pill">${ylabel(x)}</span>` +
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
    elDetail.innerHTML = h;
    elDetail.scrollTop = 0;
  }

  /* the page's state lives in the URL hash (item, year, search, filters),
     so a link, a reload or the language menu opens the same view */
  // an item's row in the list: under where it is compared, not a past section's copy
  const rowOf = id => root.querySelector(`.row[data-id="${CSS.escape(id)}"]:not(.past)`) || root.querySelector(`.row[data-id="${CSS.escape(id)}"]`);
  function hashFor(id) {
    const p = [];
    if (id) p.push("item=" + encodeURIComponent(id));
    else if (selGroup) p.push("group=" + encodeURIComponent(selGroup));
    if (ref === null) p.push("ref=all");
    else if (ref !== M.LAST) p.push("ref=" + ref);
    if (elQ.value.trim()) p.push("q=" + encodeURIComponent(elQ.value.trim()));
    if (elSec.value) p.push("sec=" + elSec.value);
    if (elLinked.checked) p.push("partial=1");
    return "#" + p.join("&");
  }
  const current = () => (selected ? focus || selected : null);
  /* the language menu (the site's header) opens the other language at the same state */
  function syncLang() {
    document.querySelectorAll("a[hreflang]").forEach(a => { a.href = a.href.split("#")[0] + location.hash; });
  }
  function setHash(h) { history.replaceState(null, "", h); syncLang(); }
  /* open the groups above a row and scroll the list to it */
  function reveal(row, force) {
    for (let d = row.parentElement.closest("details"); d; d = d.parentElement.closest("details")) {
      setFold(d.dataset.key, true, +d.dataset.d);
      d.open = true;
    }
    const lr = elList.getBoundingClientRect(), rr = row.getBoundingClientRect();
    if (force || rr.top < lr.top + 40 || rr.bottom > lr.bottom) elList.scrollTop += rr.top - lr.top - lr.height / 3;
  }
  /* the button after the card's title: back to the item in the list, even
     after browsing elsewhere; filters that hide it are cleared */
  function locate(only = false) {
    if (!selected && !selGroup) return;
    const years = selGroup ? M.NODES.get(selGroup).years : M.serOf.get(selected).years;
    const find = () => selGroup ? elList.querySelector(`summary[data-g="${CSS.escape(selGroup)}"]`) : rowOf(selected);
    if (!find()) {
      elQ.value = ""; elSec.value = ""; elLinked.checked = false;
      if (ref && !years.includes(ref)) { ref = null; elRef.value = "all"; renderSel(); }
      renderList(); setHash(hashFor(current()));
    }
    if (only && find()) { fold.level = 0; fold.open.clear(); fold.closed.clear(); renderList(); }
    const row = find();
    if (!row) return;
    if (window.innerWidth <= 860) elList.scrollIntoView({ behavior: "smooth", block: "start" });
    reveal(row, true);
    row.classList.remove("flash"); void row.offsetWidth; row.classList.add("flash");
  }
  function selectGroup(id, push = true) {
    if (!M.NODES.has(id)) return;
    selGroup = id; selected = null; focus = null;
    root.querySelectorAll(".row.sel, summary.sel").forEach(e => e.classList.remove("sel"));
    root.querySelectorAll(`summary[data-g="${CSS.escape(id)}"]`).forEach(e => e.classList.add("sel"));
    const sm = elList.querySelector(`summary[data-g="${CSS.escape(id)}"]`);
    if (sm) reveal(sm, false);
    renderGroup();
    if (push) setHash(hashFor(null));
    if (window.innerWidth <= 860) elDetail.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function select(sid, focusId = null, push = true) {
    selected = sid; focus = focusId; selGroup = null;
    root.querySelectorAll(".row.sel, summary.sel").forEach(e => e.classList.remove("sel"));
    const row = rowOf(sid);
    if (row) { row.classList.add("sel"); reveal(row, false); }
    renderDetail(sid);
    if (push) setHash(hashFor(focus || sid));
    if (window.innerWidth <= 860) elDetail.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const prevOf = y => M.YEARS[M.YEARS.indexOf(y) - 1];
  let lastKind = null, lastKindAt = 0, soloBefore = null;
  // the selection: a cell (section and year), a row (section), a column (year) or nothing
  const ch = { sec: null, y: null, kinds: new Set(DEFAULT_KINDS) };
  const inSel = e => (ch.sec === null || e.sec === ch.sec) && (ch.y === null || e.y === ch.y);
  function changesHash() {
    const p = ["changes"];
    if (ch.y !== null) p.push("year=" + ch.y);
    if (ch.sec !== null) p.push("section=" + ch.sec);
    const ks = KINDS.filter(k => ch.kinds.has(k));
    if (ks.join() !== DEFAULT_KINDS.join()) p.push("kinds=" + (ks.join(",") || "none"));
    return "#" + p.join("&");
  }
  function setChanges() { setHash(changesHash()); renderChanges(); }

  function renderChanges() {
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
    h += renderChangeList(inS.filter(e => ch.kinds.has(e.kind)));
    elYears.innerHTML = h;
  }

  function renderChangeList(list) {
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

  function show(view) {
    root.querySelectorAll(".hx-view").forEach(e => e.classList.toggle("active", e.dataset.view === view));
    root.querySelectorAll(".hx-tabs a").forEach(a => a.classList.toggle("active", a.dataset.tab === view));
  }
  function route() {
    syncLang();
    const raw = location.hash.slice(1), h = decodeURIComponent(raw), p = new URLSearchParams(raw);
    if (p.has("changes") || p.has("year")) {
      const y = +p.get("year"), sc = +p.get("section"), ks = p.get("kinds");
      ch.y = M.YEARS.includes(y) ? y : null;
      ch.sec = M.DATA.sections[sc] ? sc : null;
      ch.kinds = new Set(ks === null ? DEFAULT_KINDS : ks.split(",").filter(k => KINDS.includes(k)));
      show("years"); renderChanges(); return;
    }
    if (h === "about") { show("about"); return; }
    show("items");
    // search and filters from the hash
    const q = p.get("q") || "", sec = M.DATA.sections[p.get("sec")] ? p.get("sec") : "", chg = p.get("partial") === "1";
    if (q !== elQ.value.trim() || sec !== elSec.value || chg !== elLinked.checked) {
      elQ.value = q; elSec.value = sec; elLinked.checked = chg; renderList();
    }
    const id = p.get("item"), s = id && M.serOf.get(id), gn = !s && M.NODES.get(p.get("group") || "");
    let r = p.get("ref") === "all" ? null : M.YEARS.includes(+p.get("ref")) ? +p.get("ref") : M.LAST;
    // a link to an item (or heading) not asked in the default year opens it among all items
    if ((s || gn) && !p.has("ref") && !(s || gn).years.includes(r)) r = null;
    if (r !== ref) { ref = r; elRef.value = ref === null ? "all" : String(ref); renderList(); renderSel(); }
    if (s) {
      if (selected !== s.id || focus !== (id === s.id ? null : id)) {
        // an item outside the list is searched for, unless the hash sets the filters
        if (!q && !sec && !chg && !rowOf(s.id)) { elQ.value = s.at(refOf(s)).code; renderList(); }
        select(s.id, id === s.id ? null : id, false);
      }
    } else if (gn) {
      if (selGroup !== gn.id) selectGroup(gn.id, false);
    } else if (!selected && !selGroup) emptyDetail();
  }

  let timer;
  elQ.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { renderList(); setHash(hashFor(current())); }, 80); });
  elQ.addEventListener("keydown", e => {
    if (e.key === "Enter") { clearTimeout(timer); renderList(); const r = elList.querySelector(".row"); if (r) select(r.dataset.id); }
  });
  [elSec, elLinked].forEach(e => e.addEventListener("change", () => { renderList(); setHash(hashFor(current())); }));
  elRef.addEventListener("change", () => {
    ref = elRef.value === "all" ? null : +elRef.value;
    renderList();
    renderSel();
    setHash(hashFor(current()));
  });
  let cellTimer = null, cellYear = null;
  function setRefYear(y) {
    const s = selGroup ? M.NODES.get(selGroup) : M.serOf.get(selected);
    if (!s || !s.years.includes(y) || ref === y) return;
    ref = y; elRef.value = String(y);
    renderList(); renderSel();
    rowOf(selected)?.classList.add("sel");
    setHash(hashFor(current()));
  }
  root.addEventListener("click", e => {
    // a timeline year: one click opens the printed form, a double click makes
    // it the reference year (the click waits a moment to tell them apart)
    const cell = e.target.closest(".tl .c[data-y]");
    if (cell && !(e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button)) {
      e.preventDefault();
      const y = +cell.dataset.y;
      if (cellTimer && cellYear === y) { clearTimeout(cellTimer); cellTimer = null; setRefYear(y); return; }
      clearTimeout(cellTimer); cellYear = y;
      cellTimer = setTimeout(() => {
        cellTimer = null;
        if (cell.dataset.pdf) openPdf(cell.dataset.pdf.split(" ").map(id => M.CH.get(id)).filter(Boolean), y, cell, cell.dataset.st);
      }, 280);
      return;
    }
    const pdfLink = e.target.closest("a[data-pdf]");
    if (pdfLink && !(e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button)) {
      e.preventDefault(); openPdf(pdfLink.dataset.pdf.split(" ").map(id => M.CH.get(id)).filter(Boolean), +pdfLink.dataset.year, pdfLink, pdfLink.dataset.st); return;
    }
    const lc = e.target.closest("[data-locate]");
    if (lc) { locate(lc.dataset.locate === "only"); return; }
    const row = e.target.closest(".row"); if (row) { select(row.dataset.id); return; }
    const gl = e.target.closest("a[data-group]");
    if (gl) {
      e.preventDefault();
      // from the changes by year: over to the heading's page in the items view
      if (gl.closest('[data-view="years"]')) { location.hash = "group=" + encodeURIComponent(gl.dataset.group); return; }
      selectGroup(gl.dataset.group); locate(); return;
    }
    const go = e.target.closest("[data-go]");
    if (go) { e.preventDefault(); location.hash = hashFor(go.dataset.go); return; }
    const cp = e.target.closest("button[data-copy]");
    if (cp) {
      navigator.clipboard?.writeText(cp.dataset.copy).then(() => { cp.textContent = t.cm.copied; setTimeout(() => { cp.textContent = t.cm.copy; }, 1500); });
      return;
    }
    const q = e.target.closest("[data-q]");
    if (q) { e.preventDefault(); elQ.value = q.dataset.q; renderList(); setHash(hashFor(current())); elQ.focus(); return; }
    // changes by year: a cell, a section, a year, a total, the corner; the kinds
    const kb = e.target.closest("[data-hk]");
    if (kb) {
      // a click turns a kind on or off; a double click shows that kind alone
      // (again on a kind shown alone: back to the default). Two clicks are
      // read here, as the chips are redrawn after the first one.
      const k = kb.dataset.hk, now = Date.now(), twice = k && k === lastKind && now - lastKindAt < 400;
      lastKind = twice ? null : k; lastKindAt = now;
      if (k === "") ch.kinds = new Set(DEFAULT_KINDS);
      else if (twice) ch.kinds = soloBefore === k ? new Set(DEFAULT_KINDS) : new Set([k]);
      else {
        soloBefore = ch.kinds.size === 1 && ch.kinds.has(k) ? k : null;
        if (ch.kinds.has(k)) ch.kinds.delete(k); else ch.kinds.add(k);
      }
      setChanges(); return;
    }
    if (e.target.closest("[data-hclear]")) { ch.sec = ch.y = null; setChanges(); return; }
    const hc = e.target.closest("[data-hs],[data-hy]");
    if (hc && hc.closest('[data-view="years"]')) {
      const s = hc.dataset.hs ? +hc.dataset.hs : null, y = hc.dataset.hy ? +hc.dataset.hy : null;
      if (ch.sec === s && ch.y === y) { ch.sec = ch.y = null; } else { ch.sec = s; ch.y = y; }
      setChanges(); return;
    }
  });
  /* in-page viewer: one page of a questionnaire PDF, with an optional
     highlight box [top, bottom, left, right] in PDF points from the
     top-left corner (left and right may be missing: then full width) */
  const viewer = document.createElement("div");
  viewer.className = "hx-viewer"; viewer.hidden = true;
  viewer.setAttribute("role", "dialog"); viewer.setAttribute("aria-modal", "true");
  viewer.innerHTML = `<div class="hx-vbox">
      <div class="hx-vbar">
        <b class="hx-vtitle"></b><span class="hx-vspacer"></span>
        <button type="button" data-act="prev" title="${t.pv.prev}" aria-label="${t.pv.prev}">${fa ? "›" : "‹"}<span class="hx-vbadge" hidden></span></button>
        <button type="button" data-act="next" title="${t.pv.next}" aria-label="${t.pv.next}">${fa ? "‹" : "›"}<span class="hx-vbadge" hidden></span></button>
        <button type="button" data-act="out" title="${t.pv.zoomOut}" aria-label="${t.pv.zoomOut}">−</button>
        <button type="button" data-act="in" title="${t.pv.zoomIn}" aria-label="${t.pv.zoomIn}">+</button>
        <a class="hx-vtab" target="_blank" rel="noopener" title="${t.pv.tab}" aria-label="${t.pv.tab}">↗</a>
        <button type="button" data-act="close" title="${t.pv.close}" aria-label="${t.pv.close}">✕</button>
      </div>
      <div class="hx-vbody"><div class="hx-vpage"><canvas></canvas><div class="hx-vmarks"></div></div><div class="hx-vmsg"></div></div>
    </div>`;
  root.appendChild(viewer);
  const vEl = s => viewer.querySelector(s);
  const canvas = vEl("canvas"), marks = vEl(".hx-vmarks"), vmsg = vEl(".hx-vmsg"), vbody = vEl(".hx-vbody");
  const vs = { url: "", year: 0, page: 1, n: 0, zoom: 1, marks: [], st: "", back: null, token: 0, task: null };
  /* how many highlighted rows lie before and after this page, on the page buttons */
  function badges() {
    for (const [act, n, tip] of [["prev", vs.marks.filter(m => m.page < vs.page).length, t.pv.before],
                                 ["next", vs.marks.filter(m => m.page > vs.page).length, t.pv.after]]) {
      const b = vEl(`[data-act="${act}"]`), badge = b.querySelector(".hx-vbadge"), name = act === "prev" ? t.pv.prev : t.pv.next;
      badge.hidden = !n; badge.textContent = n ? num(n) : "";
      badge.className = `hx-vbadge${vs.st !== "" ? ` m${vs.st}` : ""}`;
      b.title = n ? `${name} · ${tip(num(n))}` : name;
    }
  }

  async function showPage() {
    const token = ++vs.token;
    vEl(".hx-vtitle").textContent = t.pv.title(yr(vs.year), num(vs.page), vs.n ? num(vs.n) : "");
    vEl(".hx-vtab").href = `${vs.url}#page=${vs.page}`;
    vEl('[data-act="prev"]').disabled = vs.page <= 1;
    vEl('[data-act="next"]').disabled = !!vs.n && vs.page >= vs.n;
    vmsg.textContent = t.pv.loading; marks.innerHTML = ""; badges();
    try {
      const doc = await pdfDoc(vs.url);
      if (token !== vs.token) return;
      vs.n = doc.numPages;
      vEl(".hx-vtitle").textContent = t.pv.title(yr(vs.year), num(vs.page), num(vs.n));
      vEl('[data-act="next"]').disabled = vs.page >= vs.n;
      const page = await doc.getPage(vs.page);
      if (token !== vs.token) return;
      const fit = Math.max(200, vbody.clientWidth - 44) / page.getViewport({ scale: 1 }).width;
      const vp = page.getViewport({ scale: fit * vs.zoom });
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.floor(vp.width * dpr); canvas.height = Math.floor(vp.height * dpr);
      canvas.style.width = `${Math.floor(vp.width)}px`; canvas.style.height = `${Math.floor(vp.height)}px`;
      if (vs.task) vs.task.cancel();
      vs.task = page.render({ canvasContext: canvas.getContext("2d"), viewport: vp, transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null });
      await vs.task.promise;
      if (token !== vs.token) return;
      vmsg.textContent = "";
      const here = vs.marks.filter(m => m.page === vs.page && m.box);
      if (here.length) {
        const k = vp.scale, cls = vs.st !== "" ? ` m${vs.st}` : "", what = vs.st !== "" ? ` · ${t.cm.st[vs.st]}` : "";
        marks.innerHTML = here.map(({ code: cd, box: [top, bottom, left, right] }) => {
          const sides = left != null && right != null;
          return `<div class="hx-vmark${cls}" title="${esc(cd + what)}" style="top:${top * k}px;height:${(bottom - top) * k}px;` +
            `left:${sides ? left * k : 0}px;width:${sides ? `${(right - left) * k}px` : "100%"}"></div>`;
        }).join("");
        vbody.scrollTop = Math.max(0, Math.min(...here.map(m => m.box[0])) * k - vbody.clientHeight / 3);
      }
    } catch (err) {
      if (err && err.name === "RenderingCancelledException") return;
      if (token === vs.token) vmsg.textContent = t.pv.failed;
    }
  }
  /* open year y of the questionnaire at the first page holding one of the
     given chains, highlighting all of them, on every page, in the colour of
     the year's comparability st (0-3; "" none) */
  function openPdf(chains, y, from, st = "") {
    const all = chains.filter(c => c.page.get(y)).map(c => ({ page: c.page.get(y), box: c.box.get(y), code: c.code }));
    if (!all.length) return;
    const page = Math.min(...all.map(m => m.page));
    Object.assign(vs, { url: `${pdfBase}questionnaire_${y}.pdf`, year: y, page, n: 0, zoom: 1, marks: all,
      st: /^[0-3]$/.test(String(st)) ? +st : "", back: from || null });
    viewer.hidden = false; document.documentElement.style.overflow = "hidden";
    vbody.scrollTop = 0; vEl('[data-act="close"]').focus();
    showPage();
  }
  function closePdf() {
    if (viewer.hidden) return;
    viewer.hidden = true; vs.token++; if (vs.task) vs.task.cancel();
    document.documentElement.style.overflow = "";
    if (vs.back) vs.back.focus();
  }
  viewer.addEventListener("click", e => {
    if (e.target === viewer) { closePdf(); return; }
    const act = e.target.closest("button[data-act]")?.dataset.act;
    if (act === "close") closePdf();
    else if (act === "prev" && vs.page > 1) { vs.page--; vbody.scrollTop = 0; showPage(); }
    else if (act === "next" && vs.page < vs.n) { vs.page++; vbody.scrollTop = 0; showPage(); }
    else if (act === "in") { vs.zoom = Math.min(4, vs.zoom * 1.25); showPage(); }
    else if (act === "out") { vs.zoom = Math.max(0.5, vs.zoom / 1.25); showPage(); }
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && !viewer.hidden) closePdf(); });
  let vresize;
  window.addEventListener("resize", () => { if (!viewer.hidden) { clearTimeout(vresize); vresize = setTimeout(showPage, 150); } });

  window.addEventListener("hashchange", route);
  renderList();
  route();
  return { focus: () => { location.hash = ""; show("items"); elQ.focus(); elQ.select(); } };
}

/* ---------- boot ---------- */
async function boot() {
  const roots = [...document.querySelectorAll(".hx")];
  if (!roots.length) return;
  let data = window.HX_DATA;
  if (!data) {
    const src = roots[0].dataset.src;
    try {
      data = await (await fetch(src)).json();
    } catch (err) {
      roots.forEach(r => { r.innerHTML = `<p>Could not load ${esc(src)}: ${esc(err)}</p>`; });
      return;
    }
  }
  const M = model(data);
  window.HX = roots.map(r => mount(r, M));
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
else boot();
