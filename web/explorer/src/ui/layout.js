/* The component's skeleton (tabs, search bar, list and card, the other
 * views) and the card before anything is picked. */
import { esc } from "./html.js";

export function layoutHtml(ctx) {
  const { M, t, filesRoot, docs } = ctx;
  const { yr } = ctx.fmt;
  const { secTitle, secPeriod } = ctx.labels;
  const sectionOpts = Object.keys(M.DATA.sections).map(n => `<option value="${n}">${yr(n)} · ${esc(secTitle(n).slice(0, 48))}${secPeriod(n) ? ` (${secPeriod(n)})` : ""}</option>`).join("");
  return `
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
}

/* the card before an item is picked: what the data holds, a few searches to try */
export function emptyHtml(ctx) {
  const { M, t, fa } = ctx;
  const { num } = ctx.fmt;
  const ex = ["برنج", "11114", "تلویزیون", "دندان"].map(q => `<a data-q="${q}">${q}</a>`);
  return `<div class="empty"><div class="big">${t.pick}</div>
      ${t.summary(num(M.SER.length), num(M.YEARS.length), num(M.DATA.changes.length))}<br>
      ${t.tryThese} ${ex.slice(0, 3).join(fa ? "، " : ", ")} ${t.or} ${ex[3]}</div>`;
}
