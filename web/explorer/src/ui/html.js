/* HTML pieces every view uses. Each returns a string. */

export const esc = s => String(s ?? "").replace(/[&<>"]/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
// Persian text, right to left inside any page
export const fat = (s, tag = "span", cls = "") => `<${tag} class="fa ${cls}">${esc(s)}</${tag}>`;
export const code = s => `<span class="code">${esc(s)}</span>`;
// a link to an item (a chain id) and to a heading's page (a node id)
export const chainLink = c => `<a data-go="${esc(c.id)}">${code(c.code)}</a>`;
export const gLink = (id, label) => `<a data-group="${esc(id)}">${label}</a>`;

/* the buttons after a card's title: back to it in the list; the same,
   with every other branch closed (two chevrons folding in on a line) */
export const locateBtns = t => `<button type="button" class="locate" data-locate title="${esc(t.cm.locate)}" aria-label="${esc(t.cm.locate)}">` +
    `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" stroke-width="2"/>` +
    `<circle cx="12" cy="12" r="2.5" fill="currentColor"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button>` +
    `<button type="button" class="locate" data-locate="only" title="${esc(t.cm.only)}" aria-label="${esc(t.cm.only)}">` +
    `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">` +
    `<path d="M8 4l4 4 4-4M8 20l4-4 4 4M4 12h16"/></svg></button>`;
