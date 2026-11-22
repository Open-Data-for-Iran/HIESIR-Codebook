/* The list: sections, then the printed group headers (levels 2-4) as a
 * tree, each item under its groups in the year it is compared with. It
 * owns what is open, the sticky headings, and a heading's dot with its
 * timeline on hover (a popover).
 *
 * createTree(ctx, el, filters): filters() gives the search bar's values,
 * { q, sec, partial }; clicking a heading's title calls
 * ctx.actions.selectGroup(id).
 */
import { compare, gcompare } from "../core/compare.js";
import { search } from "../core/search.js";
import { norm } from "../core/text.js";
import { code, esc, fat } from "./html.js";

// the Popover API (top layer, no z-index fights); hidden in older browsers
const POPOVER = typeof HTMLElement !== "undefined" && Object.prototype.hasOwnProperty.call(HTMLElement.prototype, "popover");

export function createTree(ctx, elList, filters) {
  const { M, t, fa, state: S } = ctx;
  const { num, yr, span, ranges } = ctx.fmt;
  const { secTitle, secHead, secKind } = ctx.labels;
  const { strip, stCls, spans, byState } = ctx.timeline;
  // some year can express the item only with a scope change, by adding codes, or not at all
  const notFull = s => [...compare(M, s, ctx.refOf(s)).values()].some(e => e.st === 1 || e.st === 2 || e.st === 3);

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
  const nodeCmp = id => { const n = M.NODES.get(id); if (!n) return null; const R = ctx.nodeRef(n); return { n, R, cmp: gcompare(M, n, R) }; };
  function gdot(id) {
    const x = id && nodeCmp(id);
    if (!x) return "";
    let w = 0;
    for (const e of x.cmp.values()) if (typeof e.st === "number") w = Math.max(w, e.st);
    return `<span class="gdot s${w}" data-gdot="${esc(id)}" title=""></span>`;
  }
  const pop = document.createElement("div");
  pop.className = "gpop"; pop.setAttribute("role", "tooltip");
  if (POPOVER) pop.popover = "manual"; else pop.hidden = true;
  ctx.root.appendChild(pop);
  const isShown = () => (POPOVER ? pop.matches(":popover-open") : !pop.hidden);
  function hidePop() {
    if (!isShown()) return;
    if (POPOVER) pop.hidePopover(); else pop.hidden = true;
  }
  function showPop(dt) {
    const x = nodeCmp(dt.dataset.gdot);
    if (!x) return;
    pop.innerHTML = `<div class="gp-h">${t.g.seenFrom(`<span class="refy">${yr(x.R)}</span>`)}</div>` +
      `<div class="gp-tl" style="grid-template-columns:repeat(${M.YEARS.length},1fr)">` +
      M.YEARS.map(y => `<i class="${stCls(x.cmp.get(y))}"></i>`).join("") +
      M.YEARS.map(y => `<span${y === x.R ? ` class="ref"` : ""}>${yr(y).slice(2)}</span>`).join("") + `</div>` +
      `<ul>${spans(byState(x.cmp), t.g.st)}</ul>`;
    if (!isShown()) { if (POPOVER) pop.showPopover(); else pop.hidden = false; }
    const r = dt.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    const left = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2));
    const top = r.bottom + 8 + h > innerHeight ? r.top - 8 - h : r.bottom + 8;
    pop.style.left = left + "px"; pop.style.top = top + "px";
  }
  elList.addEventListener("mouseover", e => { const dt = e.target.closest("[data-gdot]"); if (dt) showPop(dt); });
  elList.addEventListener("mouseout", e => { if (e.target.closest("[data-gdot]")) hidePop(); });
  elList.addEventListener("scroll", hidePop, { passive: true });

  function render() {
    const f = filters(), ref = S.ref;
    const res = search(M, f.q), sec = f.sec;
    const rows = (res || M.SER.map(s => [s, 0, null])).map(([s, rank, hit]) => [s, rank, hit, s.at(ctx.refOf(s))])
      .filter(([s, , , c]) => c && (!ref || s.years.includes(ref)) && (!sec || c.secAt(ctx.refOf(s)) == sec) && (!f.partial || notFull(s)));
    const top = new Map();
    const node = (kids, key, extra) => kids.get(key) || kids.set(key, { key, kids: new Map(), items: [], n: 0, min: "~", ...extra }).get(key);
    for (const row of rows) {
      const c = row[3];
      const sn = c.secAt(ctx.refOf(row[0]));
      let n = node(top, `s${sn}`, { sec: sn });
      const trail = [n];
      for (const gi of c.groupsAt(ctx.refOf(row[0]))) { n = node(n.kids, `${n.key}/${gi}`, { g: M.G[gi], gi }); trail.push(n); }
      n.items.push(row);
      for (const x of trail) { x.n++; if (c.code < x.min) x.min = c.code; }
    }
    const auto = !!res || rows.length < 80;
    if (auto && fold !== foldAuto) foldAuto = newFold();
    fold = auto ? foldAuto : foldBrowse;
    fold.base = auto ? Infinity : sec || top.size === 1 ? 1 : 0;
    const isOpen = (n, depth) => fold.open.has(n.key) || (!fold.closed.has(n.key) && depth < lvl(fold));
    const item = ([s, , hit, c, past]) => `<div class="row${past ? " past" : ""}${S.selected === s.id && !past ? " sel" : ""}" data-id="${esc(s.id)}">${code(c.code)}${fat(c.text, "div")}` +
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
        `<summary${nid ? ` data-g="${esc(nid)}"` : ""}${nid && nid === S.selGroup ? ` class="sel"` : ""} title="${esc(`${n.g ? gLabel(n) : M.sectionTitle(n.sec, ref)} · ${t.tree.head}`)}">${head}${fb}${gdot(nid)}<span class="n">${num(n.n)}</span></summary>${body}</details>`;
    }
    const cur = lvl(fold);
    const levels = rows.length ? `<span class="levels" role="group" aria-label="${esc(t.tree.label)}">` + LEVELS.map((L, i) =>
      `<button type="button" data-level="${i}" class="${L === cur ? "on" : ""}" aria-pressed="${L === cur}" title="${esc(t.tree.tips[i])}">${t.tree.levels[i]}</button>`).join("") + `</span>` : "";
    let h = `<div class="count"><span>${t.count(num(rows.length), !!res)}</span>${levels}</div>`;
    if (!rows.length) h += `<div class="empty">${t.noMatch}</div>`;
    // two blocks, one per period asked about; a section with no item here
    // whose items are listed under another section says where they went
    const filtered = res || sec || f.partial;
    const moved = new Map();
    if (!filtered) {
      for (const s of M.SER) {
        const y = ctx.refOf(s), c = s.at(y);
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
      render(); return;
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
      if (S.selGroup === sm.dataset.g) { d.open = !d.open; return; }
      d.open = true;
      ctx.actions.selectGroup(sm.dataset.g);
      return;
    }
    if (!sm || !(fb || e.altKey || e.shiftKey)) return;
    e.preventDefault();
    const d = sm.parentElement;
    const open = fb ? !d.open || !!d.querySelector("details:not([open])") : !d.open;
    for (const x of [d, ...d.querySelectorAll("details[data-key]")]) { setFold(x.dataset.key, open, +x.dataset.d); x.open = open; }
    getSelection()?.removeAllRanges();
  });

  // an item's row: under where it is compared, not a past section's copy
  const rowOf = id => elList.querySelector(`.row[data-id="${CSS.escape(id)}"]:not(.past)`) || elList.querySelector(`.row[data-id="${CSS.escape(id)}"]`);
  // a heading's title in the list
  const headOf = id => elList.querySelector(`summary[data-g="${CSS.escape(id)}"]`);
  /* open the groups above a row and scroll the list to it */
  function reveal(row, force) {
    for (let d = row.parentElement.closest("details"); d; d = d.parentElement.closest("details")) {
      setFold(d.dataset.key, true, +d.dataset.d);
      d.open = true;
    }
    const lr = elList.getBoundingClientRect(), rr = row.getBoundingClientRect();
    if (force || rr.top < lr.top + 40 || rr.bottom > lr.bottom) elList.scrollTop += rr.top - lr.top - lr.height / 3;
  }
  // only the sections open, as the first level button does
  function closeAll() { fold.level = 0; fold.open.clear(); fold.closed.clear(); render(); }

  return { render, rowOf, headOf, reveal, closeAll };
}
