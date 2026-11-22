/* One explorer in one element: builds the context the ui/ parts share,
 * draws the skeleton, and wires the search bar, the list, the cards, the
 * changes by year, the PDF viewer and the URL hash together.
 *
 * mount(root, M): root is the element (its data-lang, data-root, data-docs,
 * data-pdf), M the model (core/model.js). Returns { focusSearch }.
 */
import { DEFAULT_KINDS } from "../core/changes.js";
import { makeFormat } from "../i18n/format.js";
import { STRINGS } from "../i18n/index.js";
import { createChangesView } from "../ui/changes-view.js";
import { createGroupCard } from "../ui/group-card.js";
import { createItemCard } from "../ui/item-card.js";
import { createLabels } from "../ui/labels.js";
import { emptyHtml, layoutHtml } from "../ui/layout.js";
import { createPdfViewer } from "../ui/pdf-viewer.js";
import { createTimeline } from "../ui/timeline.js";
import { createTree } from "../ui/tree.js";
import { changesHash, itemsHash, parseHash } from "./state.js";

export function mount(root, M) {
  const lang = root.dataset.lang === "fa" ? "fa" : "en";
  const pdfBase = root.dataset.pdf || "";
  /* what is shown: an item (selected, its series; focus, the chain asked
     for) or a heading (selGroup), compared with year ref (null: all items) */
  const S = { selected: null, focus: null, ref: M.LAST, selGroup: null };
  const ctx = {
    M, lang, root, state: S, pdfBase,
    t: STRINGS[lang], fa: lang === "fa",
    fmt: makeFormat(lang, M.YEARS),
    filesRoot: root.dataset.root || "../",
    docs: root.dataset.docs || "",
    pdfUrl: (c, y) => pdfBase && c.page.get(y) ? `${pdfBase}questionnaire_${y}.pdf#page=${c.page.get(y)}` : "",
    // the year a series (or a heading) is compared with: ref, or its last year
    refOf: s => (S.ref && s.years.includes(S.ref) ? S.ref : s.last),
    nodeRef: n => (S.ref && n.years.includes(S.ref) ? S.ref : n.last),
    actions: {},
  };
  const { t } = ctx;
  root.setAttribute("dir", ctx.fa ? "rtl" : "ltr");
  root.setAttribute("lang", lang);
  ctx.labels = createLabels(ctx);
  ctx.timeline = createTimeline(ctx);

  root.innerHTML = layoutHtml(ctx);
  const $ = s => root.querySelector(s);
  const elQ = $(".hx-q"), elSec = $(".hx-sec"), elLinked = $(".hx-linked"), elRef = $(".hx-ref");
  const elList = $(".hx-list"), elDetail = $(".hx-detail"), elYears = $('[data-view="years"]');

  const tree = createTree(ctx, elList, () => ({ q: elQ.value, sec: elSec.value, partial: elLinked.checked }));
  const itemCard = createItemCard(ctx), groupCard = createGroupCard(ctx);
  const changesView = createChangesView(ctx), viewer = createPdfViewer(ctx);
  const renderList = () => tree.render();

  /* the card */
  const emptyDetail = () => { elDetail.innerHTML = emptyHtml(ctx); };
  function showCard(h) {
    if (h === null) { emptyDetail(); return; }
    elDetail.innerHTML = h;
    elDetail.scrollTop = 0;
  }
  const renderGroup = () => showCard(groupCard.render(S.selGroup));
  const renderDetail = sid => showCard(itemCard.render(sid));
  const renderSel = () => (S.selGroup ? renderGroup() : S.selected ? renderDetail(S.selected) : emptyDetail());

  /* the hash */
  const hashFor = id => itemsHash(M, { item: id, group: S.selGroup, ref: S.ref, q: elQ.value.trim(), sec: elSec.value, partial: elLinked.checked });
  const current = () => (S.selected ? S.focus || S.selected : null);
  /* the language menu (the site's header) opens the other language at the same state */
  function syncLang() {
    document.querySelectorAll("a[hreflang]").forEach(a => { a.href = a.href.split("#")[0] + location.hash; });
  }
  function setHash(h) { history.replaceState(null, "", h); syncLang(); }

  /* the button after the card's title: back to the item in the list, even
     after browsing elsewhere; filters that hide it are cleared */
  function locate(only = false) {
    if (!S.selected && !S.selGroup) return;
    const years = S.selGroup ? M.NODES.get(S.selGroup).years : M.serOf.get(S.selected).years;
    const find = () => S.selGroup ? tree.headOf(S.selGroup) : tree.rowOf(S.selected);
    if (!find()) {
      elQ.value = ""; elSec.value = ""; elLinked.checked = false;
      if (S.ref && !years.includes(S.ref)) { S.ref = null; elRef.value = "all"; renderSel(); }
      renderList(); setHash(hashFor(current()));
    }
    if (only && find()) tree.closeAll();
    const row = find();
    if (!row) return;
    if (window.innerWidth <= 860) elList.scrollIntoView({ behavior: "smooth", block: "start" });
    tree.reveal(row, true);
    row.classList.remove("flash"); void row.offsetWidth; row.classList.add("flash");
  }
  function selectGroup(id, push = true) {
    if (!M.NODES.has(id)) return;
    S.selGroup = id; S.selected = null; S.focus = null;
    root.querySelectorAll(".row.sel, summary.sel").forEach(e => e.classList.remove("sel"));
    root.querySelectorAll(`summary[data-g="${CSS.escape(id)}"]`).forEach(e => e.classList.add("sel"));
    const sm = tree.headOf(id);
    if (sm) tree.reveal(sm, false);
    renderGroup();
    if (push) setHash(hashFor(null));
    if (window.innerWidth <= 860) elDetail.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function select(sid, focusId = null, push = true) {
    S.selected = sid; S.focus = focusId; S.selGroup = null;
    root.querySelectorAll(".row.sel, summary.sel").forEach(e => e.classList.remove("sel"));
    const row = tree.rowOf(sid);
    if (row) { row.classList.add("sel"); tree.reveal(row, false); }
    renderDetail(sid);
    if (push) setHash(hashFor(S.focus || sid));
    if (window.innerWidth <= 860) elDetail.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  ctx.actions.selectGroup = selectGroup;

  /* changes by year: the selection, a cell (section and year), a row
     (section), a column (year) or nothing, and the kinds shown */
  const ch = { sec: null, y: null, kinds: new Set(DEFAULT_KINDS) };
  let lastKind = null, lastKindAt = 0, soloBefore = null;
  const renderChanges = () => { elYears.innerHTML = changesView.render(ch); };
  function setChanges() { setHash(changesHash(ch)); renderChanges(); }

  function show(view) {
    root.querySelectorAll(".hx-view").forEach(e => e.classList.toggle("active", e.dataset.view === view));
    root.querySelectorAll(".hx-tabs a").forEach(a => a.classList.toggle("active", a.dataset.tab === view));
  }
  function route() {
    syncLang();
    const v = parseHash(M, location.hash);
    if (v.view === "years") {
      ch.y = v.y; ch.sec = v.sec; ch.kinds = v.kinds;
      show("years"); renderChanges(); return;
    }
    if (v.view === "about") { show("about"); return; }
    show("items");
    // search and filters from the hash
    if (v.q !== elQ.value.trim() || v.sec !== elSec.value || v.partial !== elLinked.checked) {
      elQ.value = v.q; elSec.value = v.sec; elLinked.checked = v.partial; renderList();
    }
    const { id, series: s, group: gn } = v;
    if (v.ref !== S.ref) { S.ref = v.ref; elRef.value = S.ref === null ? "all" : String(S.ref); renderList(); renderSel(); }
    if (s) {
      if (S.selected !== s.id || S.focus !== (id === s.id ? null : id)) {
        // an item outside the list is searched for, unless the hash sets the filters
        if (!v.q && !v.sec && !v.partial && !tree.rowOf(s.id)) { elQ.value = s.at(ctx.refOf(s)).code; renderList(); }
        select(s.id, id === s.id ? null : id, false);
      }
    } else if (gn) {
      if (S.selGroup !== gn.id) selectGroup(gn.id, false);
    } else if (!S.selected && !S.selGroup) emptyDetail();
  }

  /* the search bar */
  let timer;
  elQ.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { renderList(); setHash(hashFor(current())); }, 80); });
  elQ.addEventListener("keydown", e => {
    if (e.key === "Enter") { clearTimeout(timer); renderList(); const r = elList.querySelector(".row"); if (r) select(r.dataset.id); }
  });
  [elSec, elLinked].forEach(e => e.addEventListener("change", () => { renderList(); setHash(hashFor(current())); }));
  elRef.addEventListener("change", () => {
    S.ref = elRef.value === "all" ? null : +elRef.value;
    renderList();
    renderSel();
    setHash(hashFor(current()));
  });
  let cellTimer = null, cellYear = null;
  function setRefYear(y) {
    const s = S.selGroup ? M.NODES.get(S.selGroup) : M.serOf.get(S.selected);
    if (!s || !s.years.includes(y) || S.ref === y) return;
    S.ref = y; elRef.value = String(y);
    renderList(); renderSel();
    tree.rowOf(S.selected)?.classList.add("sel");
    setHash(hashFor(current()));
  }
  const chainsOf = ids => ids.split(" ").map(id => M.CH.get(id)).filter(Boolean);
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
        if (cell.dataset.pdf) viewer.open(chainsOf(cell.dataset.pdf), y, cell, cell.dataset.st);
      }, 280);
      return;
    }
    const pdfLink = e.target.closest("a[data-pdf]");
    if (pdfLink && !(e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button)) {
      e.preventDefault(); viewer.open(chainsOf(pdfLink.dataset.pdf), +pdfLink.dataset.year, pdfLink, pdfLink.dataset.st); return;
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

  window.addEventListener("hashchange", route);
  renderList();
  route();
  return { focusSearch: () => { location.hash = ""; show("items"); elQ.focus(); elQ.select(); } };
}
