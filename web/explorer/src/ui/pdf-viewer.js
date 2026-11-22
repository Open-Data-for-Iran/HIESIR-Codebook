/* The in-page viewer: one page of a questionnaire PDF in a modal <dialog>
 * (the browser handles focus, Escape and the backdrop), with the rows of
 * the items highlighted. PDF.js is loaded from its CDN on the first use.
 *
 * createPdfViewer(ctx).open(chains, year, from, st): the questionnaire of
 * that year at the first page holding one of the chains; from gets the
 * focus back on closing; st (0-3) colours the highlights.
 */
import { esc } from "./html.js";

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

let nViewers = 0;

export function createPdfViewer(ctx) {
  const { t, fa, pdfBase } = ctx;
  const { num, yr } = ctx.fmt;
  /* one page, with highlight boxes [top, bottom, left, right] in PDF points
     from the top-left corner (left and right may be missing: then full width) */
  const viewer = document.createElement("dialog");
  const titleId = `hx-vtitle-${++nViewers}`;
  viewer.className = "hx-viewer";
  viewer.setAttribute("aria-labelledby", titleId);
  viewer.innerHTML = `<div class="hx-vbox">
      <div class="hx-vbar">
        <b class="hx-vtitle" id="${titleId}"></b><span class="hx-vspacer"></span>
        <button type="button" data-act="prev" title="${t.pv.prev}" aria-label="${t.pv.prev}">${fa ? "›" : "‹"}<span class="hx-vbadge" hidden></span></button>
        <button type="button" data-act="next" title="${t.pv.next}" aria-label="${t.pv.next}">${fa ? "‹" : "›"}<span class="hx-vbadge" hidden></span></button>
        <button type="button" data-act="out" title="${t.pv.zoomOut}" aria-label="${t.pv.zoomOut}">−</button>
        <button type="button" data-act="in" title="${t.pv.zoomIn}" aria-label="${t.pv.zoomIn}">+</button>
        <a class="hx-vtab" target="_blank" rel="noopener" title="${t.pv.tab}" aria-label="${t.pv.tab}">↗</a>
        <button type="button" data-act="close" title="${t.pv.close}" aria-label="${t.pv.close}">✕</button>
      </div>
      <div class="hx-vbody"><div class="hx-vpage"><canvas></canvas><div class="hx-vmarks"></div></div><div class="hx-vmsg"></div></div>
    </div>`;
  ctx.root.appendChild(viewer);
  const vEl = s => viewer.querySelector(s);
  const canvas = vEl("canvas"), marks = vEl(".hx-vmarks"), vmsg = vEl(".hx-vmsg"), vbody = vEl(".hx-vbody");
  const vs = { url: "", year: 0, page: 1, n: 0, zoom: 1, marks: [], st: "", back: null, token: 0, task: null, closed: true };
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
  function open(chains, y, from, st = "") {
    const all = chains.filter(c => c.page.get(y)).map(c => ({ page: c.page.get(y), box: c.box.get(y), code: c.code }));
    if (!all.length) return;
    const page = Math.min(...all.map(m => m.page));
    Object.assign(vs, { url: `${pdfBase}questionnaire_${y}.pdf`, year: y, page, n: 0, zoom: 1, marks: all,
      st: /^[0-3]$/.test(String(st)) ? +st : "", back: from || null, closed: false });
    if (!viewer.open) viewer.showModal();
    document.documentElement.style.overflow = "hidden";
    vbody.scrollTop = 0; vEl('[data-act="close"]').focus();
    showPage();
  }
  /* closed by the button, the backdrop or Escape. The tidying up runs at
     once, not on the dialog's "close" event, which is queued (and in some
     embedded browsers late); "cancel" (Escape) and "close" catch the rest */
  function closed() {
    if (vs.closed) return;
    vs.closed = true; vs.token++; if (vs.task) vs.task.cancel();
    document.documentElement.style.overflow = "";
    if (vs.back) vs.back.focus();
  }
  const close = () => { if (viewer.open) viewer.close(); closed(); };
  viewer.addEventListener("cancel", closed);
  viewer.addEventListener("close", closed);
  viewer.addEventListener("click", e => {
    if (e.target === viewer) { close(); return; }
    const act = e.target.closest("button[data-act]")?.dataset.act;
    if (act === "close") close();
    else if (act === "prev" && vs.page > 1) { vs.page--; vbody.scrollTop = 0; showPage(); }
    else if (act === "next" && vs.page < vs.n) { vs.page++; vbody.scrollTop = 0; showPage(); }
    else if (act === "in") { vs.zoom = Math.min(4, vs.zoom * 1.25); showPage(); }
    else if (act === "out") { vs.zoom = Math.max(0.5, vs.zoom / 1.25); showPage(); }
  });
  let vresize;
  window.addEventListener("resize", () => { if (viewer.open) { clearTimeout(vresize); vresize = setTimeout(showPage, 150); } });

  return { open, close };
}
