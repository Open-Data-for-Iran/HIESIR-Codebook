/* The explorer's interface text in English. fa.js has the same keys; a value
 * is a string, or a function of the numbers and names it shows (already
 * formatted for the language). */
export const en = {
  tabs: { items: "Items", years: "Changes by year", about: "How to read" },
  placeholder: "Search a code (011114, 11114) or Persian text (برنج، تلویزیون …)",
  allSections: "All sections", notFull: "Not fully comparable", notFullTip: "Only the items with a year that is not strictly comparable with the year picked in the Year field (light green, yellow or red)", current: "Still asked in {y}",
  hint: "ZWNJ, spacing and Arabic/Persian letter forms are ignored · a 5-digit code like the raw data's <span class=\"code\">11114</span> matches <span class=\"code\">011114</span>",
  count: (n, s) => `${n} item${n === "1" ? "" : "s"}${s ? " match" : ""}`,
  noMatch: "No item matches. Try fewer words or part of a word.",
  tree: {
    label: "Open the tree to",
    levels: ["Sections", "Groups", "Subgroups", "All"],
    tips: ["Close everything: the sections only", "Open the sections: their groups", "Open the groups too: their subgroups", "Open everything, down to the items"],
    fold: "Open or close everything under this heading (or Alt-click the heading)",
    head: "click the title to open its page, the arrow to open or close it",
  },
  g: {
    st: ["the same items", "scope changed: some items not asked", "recoverable by adding or removing codes", "not recoverable"],
    seenFrom: y => `Compared with the heading as printed in ${y}`,
    kind: { g: l => `group, level ${l}`, s: "section" },
    items: n => `${n} items`,
    hint: "Click a year to see the heading's items on the printed questionnaire; double-click it to compare every year with it.",
    useTitle: "Items, year by year",
    more: n => `${n} more`,
    via: "label broadened or narrowed",
    plus: "add: asked under another heading",
    movedIn: "remove: under this heading this year, under another in the reference year",
    gone: "remove: not asked in the reference year",
    miss: "not asked this year",
    inside: "an item split between this heading and another",
    useNote: y => `Add up a year's items under the heading, with the additions and removals listed, to rebuild the heading as printed in ${y}. This is exact for expenditure amounts; household counts can't be added up.`,
    sub: "Subgroups", members: (y, n) => `Items under it in ${y} (${n})`,
    links: "Links with other headings", nItems: n => `${n} item${n === "1" ? "" : "s"}`,
    pyHead: (id, y) => `# HIESIR Codebook, heading ${id}: as printed in ${y}`,
  },
  pick: "Pick an item to see its history",
  summary: (n, y, r) => `${n} items across ${y} questionnaires, ${r} links between them.`,
  tryThese: "Try", or: "or",
  section: s => `section ${s}`, chainId: "chain id",
  timeline: "Timeline", cameFrom: "Came from", wentInto: "Went into",
  otherUnder: c => `Other items under code ${c}`, corrections: "Corrections to the printed questionnaire", evidence: "Evidence",
  openPdf: (y, p) => `${y}: page ${p}, open the printed form`,
  pdfHint: "Click a year to see the item on the printed questionnaire; double-click it to compare every year with it.",
  refHint: "Double-click a year to compare every year with it.",
  cm: {
    st: ["strictly comparable", "same item, scope changed", "recoverable by adding codes", "not recoverable"],
    ref: "reference year", na: "not asked",
    seenFrom: y => `Compared with the item as asked in ${y}`,
    sum: c => `sum of ${c}`, inside: c => `inside ${c}, together with other items`,
    partial: c => `part of ${c} was not asked this year`,
    useTitle: "Codes to use, year by year",
    useNote: y => `Add up the codes listed for a year to rebuild the item as asked in ${y}. This is exact for expenditure amounts; household counts can't be added up, since one household may report several codes.`,
    copy: "Copy as Python", copied: "Copied",
    history: "Wording history", earlier: "earlier wording",
    yearLabel: "Year", yearAll: "All items",
    yearTip: "Show the items asked in this year, and compare every other year with it; All items: every item, each compared with its latest year",
    notInRef: y => `Not asked in ${y}; compared with its latest year instead.`,
    openForm: "open the printed form",
    np: "not printed: added by a correction",
    npLine: ys => `not on the printed questionnaire: ${ys}. These codes come from a correction, so there is no page to open`,
    locate: "Show in the list",
    only: "Show in the list and close every other branch",
  },
  notPrinted: "not in that year's printed form (added by a correction)",
  pv: { title: (y, p, n) => `Questionnaire ${y} · page ${p}${n ? ` of ${n}` : ""}`, prev: "Previous page", next: "Next page",
       zoomOut: "Zoom out", zoomIn: "Zoom in", tab: "Open in a new tab", close: "Close", loading: "Loading the questionnaire…",
       failed: "Could not load the PDF.",
       before: n => `${n} more on earlier pages`, after: n => `${n} more on later pages` },
  period: { m: "last month", y: "last 12 months", head: { m: "Last month", y: "Last 12 months" },
            secs: r => `sections ${r}`, moved: l => `its items are listed under section ${l}`,
            movedFrom: (l, y) => `its items as asked here until ${y}; after that they are listed under section ${l}` },
  rel: { same: "same item", recoded: "recoded", merged: "merged", split: "split", regrouped: "regrouped" },
  det: { minor: "minor wording", label_reworded: "reworded", label_broadened: "broadened", label_narrowed: "narrowed" },
  v: { confirmed: "confirmed", changed: "changed by review", added: "added by review", definite: "definite", unverified: "unverified",
       confirmedTip: "checked by hand", changedTip: "corrected by hand", addedTip: "added by hand", definiteTip: "only wording differs" },
  ch: {
    cap: "Items changed per section and year: a merge or split counts its larger side (the 99 merges of 1386 took in 261 items). Click a cell, a section or a year; click it again to clear.",
    filter: "Kinds of change", reset: "default", clear: "Clear the selection", total: "Total",
    kinds: { added: "new", dropped: "dropped", recoded: "recoded", merged: "merged", split: "split", regrouped: "regrouped", scope: "wording or scope", groups: "group headings", corr: "PDF corrections" },
    solo: "double-click to show only this kind",
    unit: { items: "items involved (a merge or split counts its larger side)", groups: "links between group headings", corr: "corrections to the printed questionnaires" },
    base: y => `${y}: the first questionnaire, so no change; only its corrections`,
    pickYear: (a, b) => `${a} → ${b}: all sections`,
    legend: "items per cell",
    pick: "Pick a cell, a section or a year to list its changes.",
    none: "No change of the kinds picked.",
    allSections: "all sections", allYears: "all years",
    count: (n, e) => `${n} items, ${e} changes`,
    droppedAny: "Dropped: not asked again",
    grel: { continued: "continued", split: "split", merged: "merged", regrouped: "regrouped", moved: "moved" },
    moved: n => `${n} items`, groupsTitle: "Group headings: links between the headers printed above the items",
  },
  groups: { recoded: "Recoded: same item, new code", merged: "Merged", split: "Split", regrouped: "Regrouped", scope: "Wording or scope changed, same code", added: "New items", dropped: y => `Dropped: last asked in ${y}`, corr: "Corrections to the printed questionnaire" },
  about: (root, docs) => `
    <h4>What this shows</h4>
    <p>Every expenditure item of the HIES questionnaires 1383–1403 (1401 has no questionnaire), after the corrections, and how each item is linked through the years.${docs ? ` The full method is in <a href="${docs}">Methods</a>.` : ""}</p>
    <h4>Terms</h4>
    <dl>
      <dt>Item (chain)</dt><dd>One expenditure code with one label, followed while both stay the same. Its id is the code and first year, e.g. <span class="code">011114-1387</span>. Spacing, ZWNJ, punctuation and digit style do not count as a change.</dd>
      <dt>Comparable series</dt><dd>Items linked one-to-one (label reworded, or the same item under a new code). Values can be compared across the series; a <span class="pill warn">narrowed</span> or <span class="pill warn">broadened</span> step means the scope changed, so check the evidence first.</dd>
      <dt>Merged, split, regrouped</dt><dd>Several items became one, one became several, or a group was reorganised. The series ends there: sum the parts to compare.</dd>
      <dt>Groups</dt><dd>The list follows the group headers printed above the items (levels 2 to 4), as printed in the year picked in the Year field. Some headers are printed twice: <span class="code">M</span> in the sections about the last month, <span class="code">A</span> in section 13, about the last 12 months. An item that moved between them is listed where it was printed that year.</dd>
      <dt>Verification</dt><dd><span class="pill ok">definite</span> only the wording differs; <span class="pill ok">confirmed</span>, <span class="pill info">changed by review</span> and <span class="pill info">added by review</span> were decided by hand in <span class="code">curated/3_items/links.csv</span> and <span class="code">curated/3_items/relations.csv</span>, mostly by checking how many households reported each code.</dd>
    </dl>
    <h4>Timeline colours</h4>
    <p>Every year is coloured by how it can express the item <b>as asked in the reference year</b>: the year picked in the Year field, else the item's latest year (outlined).</p>
    <div class="legend"><span><i class="sw s0"></i>strictly comparable: same item, same scope</span><span><i class="sw s1"></i>same item, scope broadened or narrowed</span><span><i class="sw s2"></i>recoverable by adding codes (after a merge or split)</span><span><i class="sw s3"></i>not recoverable without estimating</span><span><i class="sw"></i>not asked</span></div>
    <h4>Joining with the raw data</h4>
    <p>Codes keep their leading zero (<span class="code">011111</span>); the raw data's <span class="code">Commodity_Code</span> stores them as numbers (<span class="code">11111</span>), so join on <span class="code">int(expenditure_code)</span>.</p>
    <h4>Download</h4>
    <ul>
      <li><a href="${root}3_items/chains.csv">3_items/chains.csv</a>: one row per item (chain)</li>
      <li><a href="${root}3_items/links.csv">3_items/links.csv</a>: 1 → 1 links that continue an item (same, recoded), with the evidence</li>
      <li><a href="${root}3_items/relations.csv">3_items/relations.csv</a>: merges, splits and regroupings between items, with the evidence</li>
      <li><a href="${root}2_corrected/questionnaire_1403.csv">2_corrected/questionnaire_1403.csv</a>: one questionnaire, corrected (change the year in the link)</li>
    </ul>`,
};
