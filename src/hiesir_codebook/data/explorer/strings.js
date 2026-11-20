/* HIES explorer: the interface text, in English and Farsi.
 *
 * Kept apart from the code (explorer.js) so the wording can be read and
 * edited, or a language added, without touching the logic. Each language
 * has the same keys; a value is a string, or a function of the numbers and
 * names it shows (already formatted for that language). Load this file
 * before explorer.js: the standalone page inlines both, in that order, and
 * the documentation site loads both (overrides/explorer.html).
 */
window.HX_STRINGS = {
  en: {
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
  },
  fa: {
    tabs: { items: "اقلام", years: "تغییرات هر سال", about: "راهنما" },
    placeholder: "جست‌وجوی کد (011114، 11114) یا متن (برنج، تلویزیون …)",
    allSections: "همه بخش‌ها", notFull: "نه کاملاً قابل مقایسه", notFullTip: "فقط اقلامی که سالی دارند که با سالِ انتخاب‌شده در فیلد «سال» کاملاً قابل مقایسه نیست (سبز روشن، زرد یا قرمز)", current: "هنوز پرسیده می‌شود ({y})",
    hint: "نیم‌فاصله، فاصله و شکل عربی یا فارسی حروف نادیده گرفته می‌شود · کد ۵ رقمی داده خام مانند <span class=\"code\">11114</span> با <span class=\"code\">011114</span> جور می‌شود",
    count: (n, s) => `${n} قلم${s ? " یافت شد" : ""}`,
    noMatch: "قلمی یافت نشد. واژه‌های کمتر یا بخشی از واژه را امتحان کنید.",
    tree: {
      label: "باز کردن درخت تا",
      levels: ["بخش‌ها", "گروه‌ها", "زیرگروه‌ها", "همه"],
      tips: ["بستن همه: فقط بخش‌ها", "باز کردن بخش‌ها: گروه‌هایشان", "باز کردن گروه‌ها: زیرگروه‌هایشان", "باز کردن همه، تا اقلام"],
      fold: "باز یا بسته کردن همه زیرشاخه‌های این سرگروه (یا Alt+کلیک روی سرگروه)",
      head: "کلیک روی عنوان: صفحه آن؛ کلیک روی پیکان: باز و بسته کردن",
    },
    g: {
      st: ["همان اقلام", "تغییر دامنه: برخی اقلام پرسیده نشده", "قابل بازسازی با افزودن یا کاستن کدها", "غیرقابل بازسازی"],
      seenFrom: y => `در مقایسه با سرگروه در سال ${y}`,
      kind: { g: l => `گروه، سطح ${l}`, s: "بخش" },
      items: n => `${n} قلم`,
      hint: "برای دیدن اقلام این سرگروه در پرسشنامه چاپی روی یک سال کلیک کنید؛ با دو بار کلیک، سال‌های دیگر با آن سال مقایسه می‌شوند.",
      useTitle: "اقلام، سال به سال",
      more: n => `${n} مورد دیگر`,
      via: "عبارت گسترده‌تر یا محدودتر شده",
      plus: "افزودن: زیر سرگروه دیگری پرسیده شده",
      movedIn: "کاستن: این سال زیر این سرگروه، در سال مرجع زیر سرگروه دیگر",
      gone: "کاستن: در سال مرجع پرسیده نشده",
      miss: "این سال پرسیده نشده",
      inside: "قلمی که میان این سرگروه و سرگروه دیگری تفکیک شده",
      useNote: y => `اقلام هر سال زیر این سرگروه را، با افزوده‌ها و کاسته‌های فهرست‌شده، جمع بزنید تا سرگروه مانند سال ${y} ساخته شود. برای مبلغ هزینه دقیق است؛ تعداد خانوارها را نمی‌توان جمع زد.`,
      sub: "زیرگروه‌ها", members: (y, n) => `اقلام زیر آن در ${y} (${n})`,
      links: "پیوند با سرگروه‌های دیگر", nItems: n => `${n} قلم`,
      pyHead: (id, y) => `# HIESIR Codebook, heading ${id}: as printed in ${y}`,
    },
    pick: "یک قلم را برای دیدن تاریخچه‌اش انتخاب کنید",
    summary: (n, y, r) => `${n} قلم در ${y} پرسشنامه، با ${r} پیوند میان آن‌ها.`,
    tryThese: "امتحان کنید:", or: "یا",
    section: s => `بخش ${s}`, chainId: "شناسه زنجیره",
    timeline: "خط زمانی", cameFrom: "از کجا آمده", wentInto: "به کجا رفته",
    otherUnder: c => `اقلام دیگر با کد ${c}`, corrections: "اصلاحات پرسشنامه چاپی", evidence: "شاهد",
    openPdf: (y, p) => `${y}: صفحه ${p}، باز کردن فرم چاپی`,
    pdfHint: "برای دیدن قلم در پرسشنامه چاپی، روی یک سال کلیک کنید؛ با دو بار کلیک، سال‌های دیگر با آن سال مقایسه می‌شوند.",
    refHint: "با دو بار کلیک روی یک سال، سال‌های دیگر با آن سال مقایسه می‌شوند.",
    cm: {
      st: ["کاملاً قابل مقایسه", "همان قلم، با تغییر دامنه", "قابل بازسازی با جمع کدها", "غیرقابل بازسازی"],
      ref: "سال مرجع", na: "پرسیده نشده",
      seenFrom: y => `در مقایسه با قلم در سال ${y}`,
      sum: c => `جمع ${c}`, inside: c => `درون ${c}، همراه با اقلام دیگر`,
      partial: c => `بخشی از ${c} در این سال پرسیده نشده`,
      useTitle: "کدهای مورد استفاده در هر سال",
      useNote: y => `برای ساختن قلمِ سال ${y}، کدهای هر سال را با هم جمع کنید. این برای مبلغ هزینه دقیق است؛ تعداد خانوارها را نمی‌توان جمع زد، چون یک خانوار ممکن است چند کد را گزارش کند.`,
      copy: "کپی به‌صورت Python", copied: "کپی شد",
      history: "تاریخچه عبارت", earlier: "عبارت پیشین",
      yearLabel: "سال", yearAll: "همه اقلام",
      yearTip: "اقلامی را که در این سال پرسیده شده‌اند نشان بده و سال‌های دیگر را با آن مقایسه کن؛ همه اقلام: همه اقلام، هر کدام در مقایسه با آخرین سالِ خود",
      notInRef: y => `در ${y} پرسیده نشده؛ مقایسه نسبت به آخرین سالِ آن است.`,
      openForm: "باز کردن فرم چاپی",
      np: "چاپ نشده: با اصلاح افزوده شده",
      npLine: ys => `در پرسشنامه چاپی نیست: ${ys}. این کدها از یک اصلاح آمده‌اند، پس صفحه‌ای برای نمایش نیست`,
      locate: "نمایش در فهرست",
      only: "نمایش در فهرست و بستن شاخه‌های دیگر",
    },
    notPrinted: "در فرم چاپی آن سال نیست (با اصلاح افزوده شده)",
    pv: { title: (y, p, n) => `پرسشنامه ${y} · صفحه ${p}${n ? ` از ${n}` : ""}`, prev: "صفحه قبل", next: "صفحه بعد",
         zoomOut: "کوچک‌نمایی", zoomIn: "بزرگ‌نمایی", tab: "باز کردن در زبانه تازه", close: "بستن", loading: "در حال بارگذاری پرسشنامه…",
         failed: "بارگذاری PDF ممکن نشد.",
         before: n => `${n} مورد دیگر در صفحه‌های پیشین`, after: n => `${n} مورد دیگر در صفحه‌های بعدی` },
    period: { m: "ماه گذشته", y: "۱۲ ماه گذشته", head: { m: "ماه گذشته", y: "۱۲ ماه گذشته" },
              secs: r => `بخش‌های ${r}`, moved: l => `اقلامش در بخش ${l} فهرست شده‌اند`,
              movedFrom: (l, y) => `اقلامش تا ${y} در این بخش پرسیده شده‌اند؛ پس از آن در بخش ${l} فهرست شده‌اند` },
    rel: { same: "همان قلم", recoded: "تغییر کد", merged: "ادغام", split: "تفکیک", regrouped: "بازگروه‌بندی" },
    det: { minor: "تغییر جزئی", label_reworded: "تغییر عبارت", label_broadened: "گسترده‌تر شده", label_narrowed: "محدودتر شده" },
    v: { confirmed: "تأییدشده", changed: "اصلاح در بازبینی", added: "افزوده در بازبینی", definite: "قطعی", unverified: "راستی‌آزمایی‌نشده",
         confirmedTip: "دستی بررسی شده", changedTip: "دستی اصلاح شده", addedTip: "دستی افزوده شده", definiteTip: "فقط عبارت فرق دارد" },
    ch: {
      cap: "شمار اقلام تغییرکرده در هر بخش و سال: ادغام یا تفکیک با طرف بزرگ‌ترش شمرده می‌شود (۹۹ ادغام ۱۳۸۶، ۲۶۱ قلم را در بر گرفت). روی یک خانه، یک بخش یا یک سال کلیک کنید؛ کلیک دوباره انتخاب را برمی‌دارد.",
      filter: "نوع تغییر", reset: "پیش‌فرض", clear: "برداشتن انتخاب", total: "جمع",
      kinds: { added: "جدید", dropped: "حذف‌شده", recoded: "تغییر کد", merged: "ادغام", split: "تفکیک", regrouped: "بازگروه‌بندی", scope: "تغییر عبارت یا دامنه", groups: "سرگروه‌ها", corr: "اصلاح PDF" },
      solo: "برای دیدن فقط همین نوع، دو بار کلیک کنید",
      unit: { items: "شمار اقلام درگیر (ادغام یا تفکیک با طرف بزرگ‌ترش)", groups: "پیوندهای میان سرگروه‌ها", corr: "اصلاحات پرسشنامه‌های چاپی" },
      base: y => `${y}: نخستین پرسشنامه، پس تغییری ندارد؛ فقط اصلاحاتش`,
      pickYear: (a, b) => `${a} ← ${b}: همه بخش‌ها`,
      legend: "قلم در هر خانه",
      pick: "برای دیدن تغییرات، یک خانه، یک بخش یا یک سال را انتخاب کنید.",
      none: "تغییری از نوع‌های انتخاب‌شده نیست.",
      allSections: "همه بخش‌ها", allYears: "همه سال‌ها",
      count: (n, e) => `${n} قلم، ${e} تغییر`,
      droppedAny: "حذف‌شده: دیگر پرسیده نشده",
      grel: { continued: "ادامه", split: "تفکیک", merged: "ادغام", regrouped: "بازگروه‌بندی", moved: "جابه‌جایی" },
      moved: n => `${n} قلم`, groupsTitle: "سرگروه‌ها: پیوند میان عنوان‌هایی که بالای اقلام چاپ شده‌اند",
    },
    groups: { recoded: "تغییر کد: همان قلم با کد جدید", merged: "ادغام", split: "تفکیک", regrouped: "بازگروه‌بندی", scope: "تغییر عبارت یا دامنه با همان کد", added: "اقلام جدید", dropped: y => `حذف‌شده: آخرین بار در ${y} پرسیده شده`, corr: "اصلاحات پرسشنامه چاپی" },
    about: (root, docs) => `
      <h4>این صفحه چه نشان می‌دهد</h4>
      <p>همه اقلام هزینه‌ای پرسشنامه‌های طرح هزینه و درآمد خانوار ۱۳۸۳ تا ۱۴۰۳ (۱۴۰۱ پرسشنامه ندارد)، پس از اصلاحات، و پیوند هر قلم در طول سال‌ها.${docs ? ` روش کامل در <a href="${docs}">روش کار</a> آمده است.` : ""}</p>
      <h4>اصطلاحات</h4>
      <dl>
        <dt>قلم (زنجیره)</dt><dd>یک کد هزینه با یک عبارت، تا زمانی که هر دو ثابت بمانند. شناسه آن کد و نخستین سال است، مثلاً <span class="code">011114-1387</span>. فاصله، نیم‌فاصله، نشانه‌گذاری و شکل رقم تغییر حساب نمی‌شوند.</dd>
        <dt>سری قابل مقایسه</dt><dd>اقلامی که یک‌به‌یک به هم پیوند دارند (عبارت تازه، یا همان قلم با کد جدید). مقادیر در طول سری قابل مقایسه‌اند؛ گام <span class="pill warn">محدودتر شده</span> یا <span class="pill warn">گسترده‌تر شده</span> یعنی دامنه تغییر کرده، پس اول شاهد را ببینید.</dd>
        <dt>ادغام، تفکیک، بازگروه‌بندی</dt><dd>چند قلم یکی شده‌اند، یک قلم چند قلم شده، یا گروهی از نو سازمان یافته است. سری همان‌جا پایان می‌یابد: برای مقایسه، بخش‌ها را جمع بزنید.</dd>
        <dt>گروه‌ها</dt><dd>فهرست از سرگروه‌هایی پیروی می‌کند که بالای اقلام چاپ شده‌اند (سطح ۲ تا ۴)، همان‌گونه که در سالِ انتخاب‌شده در فیلد «سال» چاپ شده‌اند. برخی سرگروه‌ها دو بار چاپ شده‌اند: <span class="code">M</span> در بخش‌های مربوط به ماه گذشته و <span class="code">A</span> در بخش ۱۳، مربوط به ۱۲ ماه گذشته. قلمی که میان آن‌ها جابه‌جا شده، در جایی فهرست می‌شود که آن سال چاپ شده است.</dd>
        <dt>راستی‌آزمایی</dt><dd><span class="pill ok">قطعی</span> فقط عبارت فرق دارد؛ <span class="pill ok">تأییدشده</span>، <span class="pill info">اصلاح در بازبینی</span> و <span class="pill info">افزوده در بازبینی</span> را یک نفر در <span class="code">curated/3_items/links.csv</span> و <span class="code">curated/3_items/relations.csv</span>، بیشتر با بررسی تعداد خانوارهای گزارش‌دهنده هر کد، تعیین کرده است.</dd>
      </dl>
      <h4>رنگ‌های خط زمانی</h4>
      <p>هر سال بر اساس این رنگ می‌گیرد که چگونه می‌تواند <b>قلمِ سال مرجع</b> را نشان دهد: سالی که در فیلد «سال» انتخاب شده، یا آخرین سالِ قلم (با کادر).</p>
      <div class="legend"><span><i class="sw s0"></i>کاملاً قابل مقایسه: همان قلم با همان دامنه</span><span><i class="sw s1"></i>همان قلم، دامنه گسترده‌تر یا محدودتر</span><span><i class="sw s2"></i>قابل بازسازی با جمع کدها (پس از ادغام یا تفکیک)</span><span><i class="sw s3"></i>بدون برآورد قابل بازسازی نیست</span><span><i class="sw"></i>پرسیده نشده</span></div>
      <h4>اتصال به داده‌های خام</h4>
      <p>کدها صفر ابتدایی‌شان را نگه می‌دارند (<span class="code">011111</span>)؛ ستون <span class="code">Commodity_Code</span> داده‌های خام آن‌ها را عدد ذخیره می‌کند (<span class="code">11111</span>)، پس اتصال را با <span class="code">int(expenditure_code)</span> انجام دهید.</p>
      <h4>دریافت</h4>
      <ul>
        <li><a href="${root}3_items/chains.csv">3_items/chains.csv</a>: هر قلم (زنجیره) یک سطر</li>
        <li><a href="${root}3_items/links.csv">3_items/links.csv</a>: پیوندهای یک‌به‌یکی که یک قلم را ادامه می‌دهند (همان قلم، تغییر کد)، همراه با شاهد</li>
        <li><a href="${root}3_items/relations.csv">3_items/relations.csv</a>: ادغام‌ها، تفکیک‌ها و بازگروه‌بندی‌ها، همراه با شاهد</li>
        <li><a href="${root}2_corrected/questionnaire_1403.csv">2_corrected/questionnaire_1403.csv</a>: یک پرسشنامه اصلاح‌شده (سال را در نشانی عوض کنید)</li>
      </ul>`,
  },
};
