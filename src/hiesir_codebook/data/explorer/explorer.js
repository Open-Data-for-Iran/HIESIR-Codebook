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
 * MkDocs page (docs/explorer.md), so the two never drift apart.
 */
(function () {
  "use strict";

  /* ---------- strings ---------- */
  const T = {
    en: {
      tabs: { items: "Items", years: "Changes by year", about: "How to read" },
      placeholder: "Search a code (011114, 11114) or Persian text (برنج، تلویزیون …)",
      allSections: "All sections", notFull: "Not fully comparable", notFullTip: "Only the items with a year that is not strictly comparable with the year picked in the Year field (light green, yellow or red)", current: "Still asked in {y}",
      hint: "ZWNJ, spacing and Arabic/Persian letter forms are ignored · a 5-digit code like the raw data's <span class=\"code\">11114</span> matches <span class=\"code\">011114</span>",
      count: (n, s) => `${n} item${n === "1" ? "" : "s"}${s ? " match" : ""}`,
      noMatch: "No item matches. Try fewer words or part of a word.",
      linked: "linked", linkedTip: "linked to other items",
      pick: "Pick an item to see its history",
      summary: (n, y, r) => `${n} items across ${y} questionnaires, ${r} links between them.`,
      tryThese: "Try", or: "or",
      section: s => `section ${s}`, asked: s => `asked ${s}`, notIn: l => `not in ${l}`, chainId: "chain id",
      comparable: s => `Comparable ${s}`, comparableSeries: s => `Comparable series ${s}`, withScope: " — with scope changes",
      sameEveryYear: "Same code and label in every year it was asked.",
      followed: l => `Followed through ${l}.`, codeChanges: l => `code changes ${l}`, labels: n => `${n} labels`,
      scope: (l, one) => ` Scope ${l}: check the evidence below before comparing across ${one ? "that year" : "those years"}.`,
      scopeIn: (d, y) => `${d} in ${y}`,
      before: (y, r) => ` Before ${y} it was ${r} from other items.`,
      after: (y, r) => ` After ${y} it was ${r} into other items.`,
      notAfter: y => ` Not asked after ${y}.`,
      timeline: "Timeline", series: "Series", cameFrom: "Came from", wentInto: "Went into",
      otherUnder: c => `Other items under code ${c}`, corrections: "Corrections to the printed questionnaire", evidence: "Evidence",
      lgThis: "this item", lgOther: "same series, other code or label (click)", lgGap: "not asked", lgMark: "change year",
      openPdf: (y, p) => `${y}: page ${p}, open the printed form`,
      pdfHint: "Click a year to see the item on the printed questionnaire.",
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
      },
      notPrinted: "not in that year's printed form (added by a correction)",
      pv: { title: (y, p, n) => `Questionnaire ${y} · page ${p}${n ? ` of ${n}` : ""}`, prev: "Previous page", next: "Next page",
           zoomOut: "Zoom out", zoomIn: "Zoom in", tab: "Open in a new tab", close: "Close", loading: "Loading the questionnaire…",
           failed: "Could not load the PDF.", here: "The item is on this page",
           before: n => `${n} more on earlier pages`, after: n => `${n} more on later pages` },
      tipNot: "not asked",
      period: { m: "last month", y: "last 12 months", head: { m: "Last month", y: "Last 12 months" },
                secs: r => `sections ${r}`, moved: l => `its items are listed under section ${l}` },
      rel: { same: "same item", recoded: "recoded", merged: "merged", split: "split", regrouped: "regrouped" },
      relVerb: { same: "continued", recoded: "recoded", merged: "merged", split: "split", regrouped: "regrouped" },
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
      linked: "پیونددار", linkedTip: "به اقلام دیگر پیوند دارد",
      pick: "یک قلم را برای دیدن تاریخچه‌اش انتخاب کنید",
      summary: (n, y, r) => `${n} قلم در ${y} پرسشنامه، با ${r} پیوند میان آن‌ها.`,
      tryThese: "امتحان کنید:", or: "یا",
      section: s => `بخش ${s}`, asked: s => `پرسیده‌شده ${s}`, notIn: l => `به‌جز ${l}`, chainId: "شناسه زنجیره",
      comparable: s => `قابل مقایسه ${s}`, comparableSeries: s => `سری قابل مقایسه ${s}`, withScope: " — با تغییر دامنه",
      sameEveryYear: "در همه سال‌هایی که پرسیده شده، کد و عبارتش یکسان است.",
      followed: l => `دنبال‌شده با ${l}.`, codeChanges: l => `تغییر کد در ${l}`, labels: n => `${n} عبارت`,
      scope: (l, one) => ` دامنه ${l}: پیش از مقایسه ${one ? "در آن سال" : "در آن سال‌ها"} شاهد زیر را ببینید.`,
      scopeIn: (d, y) => `در ${y} ${d}`,
      before: (y, r) => ` پیش از ${y} از اقلام دیگر ${r} شده است.`,
      after: (y, r) => ` پس از ${y} در اقلام دیگر ${r} شده است.`,
      notAfter: y => ` پس از ${y} پرسیده نشده است.`,
      timeline: "خط زمانی", series: "سری", cameFrom: "از کجا آمده", wentInto: "به کجا رفته",
      otherUnder: c => `اقلام دیگر با کد ${c}`, corrections: "اصلاحات پرسشنامه چاپی", evidence: "شاهد",
      lgThis: "همین قلم", lgOther: "همان سری با کد یا عبارت دیگر (کلیک کنید)", lgGap: "پرسیده نشده", lgMark: "سال تغییر",
      openPdf: (y, p) => `${y}: صفحه ${p}، باز کردن فرم چاپی`,
      pdfHint: "برای دیدن قلم در پرسشنامه چاپی، روی یک سال کلیک کنید.",
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
      },
      notPrinted: "در فرم چاپی آن سال نیست (با اصلاح افزوده شده)",
      pv: { title: (y, p, n) => `پرسشنامه ${y} · صفحه ${p}${n ? ` از ${n}` : ""}`, prev: "صفحه قبل", next: "صفحه بعد",
           zoomOut: "کوچک‌نمایی", zoomIn: "بزرگ‌نمایی", tab: "باز کردن در زبانه تازه", close: "بستن", loading: "در حال بارگذاری پرسشنامه…",
           failed: "بارگذاری PDF ممکن نشد.", here: "قلم در این صفحه است",
           before: n => `${n} مورد دیگر در صفحه‌های پیشین`, after: n => `${n} مورد دیگر در صفحه‌های بعدی` },
      tipNot: "پرسیده نشده",
      period: { m: "ماه گذشته", y: "۱۲ ماه گذشته", head: { m: "ماه گذشته", y: "۱۲ ماه گذشته" },
                secs: r => `بخش‌های ${r}`, moved: l => `اقلامش در بخش ${l} فهرست شده‌اند` },
      rel: { same: "همان قلم", recoded: "تغییر کد", merged: "ادغام", split: "تفکیک", regrouped: "بازگروه‌بندی" },
      relVerb: { same: "ادامه", recoded: "تغییر کد", merged: "ادغام", split: "تفکیک", regrouped: "بازگروه‌بندی" },
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

  /* ---------- text normalisation for search ---------- */
  const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹", AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";
  function norm(s) {
    return s.replace(/[۰-۹]/g, d => FA_DIGITS.indexOf(d)).replace(/[٠-٩]/g, d => AR_DIGITS.indexOf(d))
      .replace(/[يى]/g, "ی").replace(/ك/g, "ک").replace(/[ةۀ]/g, "ه").replace(/[أإٱ]/g, "ا").replace(/ؤ/g, "و")
      .replace(/[ً-ٰٟـ]/g, "")
      .replace(/[‌‍\s.,،؛;:!؟?()«»"'\/\\\-–_]+/g, "").toLowerCase();
  }
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

  /* ---------- data model (shared by every mounted component) ---------- */
  function model(DATA) {
    const YEARS = DATA.years, LAST = YEARS[YEARS.length - 1];
    const CH = new Map(DATA.chains.map(c => [c.id, c])), G = DATA.groups || [];
    for (const c of DATA.chains) {
      const miss = new Set(c.miss);
      c.years = YEARS.filter(y => y >= c.first && y <= c.last && !miss.has(y));
      c.page = new Map(c.years.map((y, i) => [y, c.pg ? c.pg[i] : null]));
      c.box = new Map(c.years.map((y, i) => [y, c.bx ? c.bx[i] : null]));
      // its groups (indexes into DATA.groups, outermost first) in year y
      c.groupsAt = y => { let g = []; for (const [y0, p] of c.gp || []) if (y0 <= y) g = p; return g; };
      // its section in year y: some items moved (124113 and the insurance items
      // went from section 12 to 13); c.s is the section of its first year
      c.secAt = y => { const g = c.groupsAt(y); return (g.length && G[g[0]] && G[g[0]][3]) || c.s; };
      c.ins = []; c.outs = [];
      c.key = norm(c.text + " " + c.path.map(p => p[1]).join(" "));
      c.key0 = norm(c.text);
    }
    for (const r of DATA.relations) {
      for (const id of r.to) CH.get(id)?.ins.push(r);
      for (const id of r.from) CH.get(id)?.outs.push(r);
    }
    const byCode = new Map();
    for (const c of DATA.chains) (byCode.get(c.code) || byCode.set(c.code, []).get(c.code)).push(c);
    // series: chains joined by one-to-one links (the same item reworded, or recoded)
    const serOf = new Map(), SER = [];
    for (const c of DATA.chains) {
      if (serOf.has(c.id)) continue;
      const comp = [], todo = [c], seen = new Set([c.id]);
      while (todo.length) {
        const x = todo.pop(); comp.push(x);
        for (const r of [...x.ins, ...x.outs]) {
          if (!is11(r)) continue;
          for (const id of [r.from[0], r.to[0]]) {
            const y = CH.get(id);
            if (y && !seen.has(y.id)) { seen.add(y.id); todo.push(y); }
          }
        }
      }
      comp.sort((a, b) => a.first - b.first || a.last - b.last);
      const s = { id: comp[0].id, chains: comp, years: [...new Set(comp.flatMap(x => x.years))].sort((a, b) => a - b) };
      s.last = s.years[s.years.length - 1];
      s.key = comp.map(x => x.key).join(" ");
      s.at = y => s.chains.find(x => x.years.includes(y));
      comp.forEach(x => serOf.set(x.id, s));
      SER.push(s);
    }
    const RELS = DATA.relations.slice().sort((a, b) => a.year - b.year);
    // the wording printed in year y (y null: the latest)
    const runAt = (runs, y, latest) => { if (!runs || y == null) return latest; let l = runs[0][1]; for (const [y0, v] of runs) if (y0 <= y) l = v; return l; };
    const groupLabel = (gi, y) => runAt(G[gi] && G[gi][4], y, G[gi] ? G[gi][1] : "");
    const sectionTitle = (n, y) => runAt((DATA.sectionYears || {})[n], y, DATA.sections[n] || "");
    return { DATA, YEARS, LAST, CH, byCode, SER, serOf, RELS, G, groupLabel, sectionTitle, cmp: new Map() };
  }
  const is11 = r => (r.rel === "same" || r.rel === "recoded") && r.from.length === 1 && r.to.length === 1;
  const linked = c => c.ins.length || c.outs.length;

  /* How each year can express the target: the series' item as asked in year R.
     Every relation says its two sides cover the same ground. Walking away from
     R, a relation whose whole near side is in the target set swaps it for the
     far side (exact: add those codes up); one that takes only part of it buries
     the target inside items that also hold other things (not recoverable).
     st: "ref" | 0 strictly comparable | 1 scope changed | 2 recoverable by adding
     codes | 3 not recoverable | null not asked; set: the chains to add up (for 3:
     the chains it is buried in). */
  const LEVEL = r => is11(r) ? (r.detail === "label_broadened" || r.detail === "label_narrowed" ? 1 : 0) : 2;
  function compare(M, s, R) {
    const key = `${s.id}|${R}`;
    if (M.cmp.has(key)) return M.cmp.get(key);
    const out = new Map(), target = s.at(R);
    M.cmp.set(key, out);
    if (!target) return out;
    out.set(R, { st: "ref", set: [target], via: [] });
    const walk = (years, rels, near, far, applies) => {
      const S = new Set([target.id]), via = [];
      let lvl = 0, broken = null, i = 0;
      for (const y of years) {
        while (i < rels.length && applies(rels[i], y)) {
          const r = rels[i++], hit = r[near].filter(id => S.has(id));
          if (!hit.length) continue;
          r[near].forEach(id => S.delete(id));
          r[far].forEach(id => S.add(id));
          if (broken) continue;
          if (hit.length === r[near].length) { lvl = Math.max(lvl, LEVEL(r)); if (LEVEL(r)) via.push(r); }
          else broken = r;
        }
        const set = [...S].map(id => M.CH.get(id)).filter(Boolean);
        const asked = set.filter(x => x.years.includes(y)).sort((a, b) => a.code.localeCompare(b.code));
        set.sort((a, b) => a.code.localeCompare(b.code));
        if (!asked.length) { out.set(y, { st: null, set: [], via: [] }); continue; }
        const partial = !broken && asked.length < set.length;
        out.set(y, { st: broken || partial ? 3 : lvl, set: partial ? set : asked, via: [...via], broken, partial });
      }
    };
    walk(M.YEARS.filter(y => y > R), M.RELS.filter(r => r.year > R), "from", "to", (r, y) => r.year <= y);
    walk(M.YEARS.filter(y => y < R).reverse(), M.RELS.filter(r => r.year <= R).reverse(), "to", "from", (r, y) => r.year > y);
    return out;
  }

  /* series matching a query: [series, rank, the chain that matched] */
  function search(M, q) {
    const raw = q.trim();
    if (!raw) return null;
    const ascii = raw.replace(/[۰-۹]/g, d => FA_DIGITS.indexOf(d)).replace(/[٠-٩]/g, d => AR_DIGITS.indexOf(d));
    const m = ascii.match(/^(\d+)(?:-(\d{4}))?$/);
    const out = [];
    if (m) {
      const d = m[1], cands = new Set([d]);
      if (d.length === 5 || d.length === 3) cands.add("0" + d);
      for (const s of M.SER) {
        const hit = [...s.chains].reverse().find(c => [...cands].some(x => c.code.startsWith(x)) && (!m[2] || c.id.endsWith(m[2])));
        if (hit) out.push([s, cands.has(hit.code) ? 0 : 1, hit]);
      }
      return out;
    }
    const toks = raw.split(/\s+/).map(norm).filter(Boolean);
    for (const s of M.SER) {
      if (!toks.every(t => s.key.includes(t))) continue;
      const hit = [...s.chains].reverse().find(c => toks.every(t => c.key0.includes(t)))
        || [...s.chains].reverse().find(c => toks.every(t => c.key.includes(t))) || s.chains[s.chains.length - 1];
      out.push([s, (toks.every(t => hit.key0.includes(t)) ? 0 : 2) + (hit.key0.startsWith(toks[0]) ? 0 : 1), hit]);
    }
    return out;
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

    /* the list: sections, then the printed group headers (levels 2-4) as a
       tree, each item under its groups in the year it is compared with */
    const openKeys = new Set();
    let allOpen = false;
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
      allOpen = !!res || rows.length < 80;
      const isOpen = n => allOpen || openKeys.has(n.key) || (n.sec && (sec || top.size === 1));
      const item = ([s, , hit, c]) => `<div class="row${selected === s.id ? " sel" : ""}" data-id="${esc(s.id)}">${code(c.code)}${fat(c.text, "div")}` +
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
        const head = n.sec ? secHead(n.sec, ref) : `${code(n.g[0])}${fat(gLabel(n))}`;
        const parts = [...n.kids.values()].map(k => [k.min, k]).concat(n.items.map(r => [r[3].code, r]));
        parts.sort((a, b) => a[0].localeCompare(b[0]) || (Array.isArray(a[1]) ? 1 : -1));
        const body = parts.map(([, x]) => Array.isArray(x) ? item(x) : draw(x, depth + 1, n.sec ? secTitle(n.sec, ref) : gLabel(n))).join("");
        return `<details class="${n.sec ? "sec" : "grp"}" data-key="${esc(n.key)}" style="--d:${depth}"${isOpen(n) ? " open" : ""}>` +
          `<summary title="${esc(n.g ? gLabel(n) : M.sectionTitle(n.sec, ref))}">${head}<span class="n">${num(n.n)}</span></summary>${body}</details>`;
      }
      let h = `<div class="count">${t.count(num(rows.length), !!res)}</div>`;
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
      }
      for (const kind of ["m", "y"]) {
        const nodes = [...top.values()].filter(n => secKind(n.sec) === kind).sort((a, b) => a.sec - b.sec);
        const gone = [...moved].filter(([n]) => secKind(n) === kind);
        if (!nodes.length && !gone.length) continue;
        const nums = nodes.map(n => n.sec);
        h += `<div class="perhead"><b>${t.period.head[kind]}</b>` +
          (nums.length ? `<span>${t.period.secs(span(nums[0], nums[nums.length - 1]))}</span>` : "") +
          `<span class="n">${num(nodes.reduce((a, n) => a + n.n, 0))}</span></div>`;
        const parts = nodes.map(n => [n.sec, draw(n, 0, "")])
          .concat(gone.map(([n, to]) => [n, `<div class="secmoved">${code(n)}${fat(secTitle(n), "span", "st")}<span class="to">${t.period.moved([...to].sort((a, b) => a - b).map(yr).join(fa ? "، " : ", "))}</span></div>`]));
        h += parts.sort((a, b) => a[0] - b[0]).map(x => x[1]).join("");
      }
      elList.innerHTML = h;
    }
    /* the list sticks to the top of the window like the item card: while it
       is still below its sticky place, the wheel scrolls the page, so the list
       never hides its last rows below the window */
    elList.addEventListener("wheel", e => {
      if (e.deltaY <= 0 || e.ctrlKey || getComputedStyle(elList).position !== "sticky") return;
      const top = parseFloat(getComputedStyle(elList).top) || 0, gap = elList.getBoundingClientRect().top - top;
      const room = document.documentElement.scrollHeight - innerHeight - scrollY;
      if (gap > 1 && room > 1) { e.preventDefault(); scrollBy(0, Math.min(gap, e.deltaY * (e.deltaMode === 1 ? 16 : 1))); }
    }, { passive: false });
    /* opening and closing a group is remembered while browsing (not while a
       search or a short list opens everything) */
    elList.addEventListener("toggle", e => {
      const d = e.target;
      if (allOpen || !d.matches || !d.matches("details[data-key]")) return;
      if (d.open) openKeys.add(d.dataset.key); else openKeys.delete(d.dataset.key);
    }, true);

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

    function renderDetail(sid) {
      const s = M.serOf.get(sid);
      if (!s) { emptyDetail(); return; }
      const R = refOf(s), cmp = compare(M, s, R), c = s.at(R);
      const inSer = new Set(s.chains.map(x => x.id));

      const above = c.groupsAt(R).map(gi => M.groupLabel(gi, R));
      let h = `<div class="crumbs fa">${[M.sectionTitle(c.secAt(R), R), ...(above.length ? above : c.path.map(p => p[1]))].filter(Boolean).map(x => `<span>${esc(x)}</span>`).join("")}</div>`;
      h += `<div class="title fa">${esc(c.text)}<button type="button" class="locate" data-locate title="${esc(t.cm.locate)}" aria-label="${esc(t.cm.locate)}">` +
        `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="7" fill="none" stroke="currentColor" stroke-width="2"/>` +
        `<circle cx="12" cy="12" r="2.5" fill="currentColor"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button></div>`;
      // codes by period: 011837 1383–1385 → 011174 1386–1403
      const periods = [];
      for (const x of s.chains) {
        const p = periods[periods.length - 1];
        if (p && p.code === x.code) p.b = x.last; else periods.push({ code: x.code, a: x.first, b: x.last });
      }
      h += `<div class="ids">${periods.map(p => `${code(p.code)} <span class="yrs">${span(p.a, p.b)}</span>`).join(` <span class="arrow">${ARROW}</span> `)}` +
        ` <span class="pill">${t.section(yr(c.secAt(R)))}</span> <span class="pill" title="${t.chainId}">${esc(s.id)}</span></div>`;
      if (ref && !s.years.includes(ref)) h += `<div class="note">${t.cm.notInRef(yr(ref))}</div>`;

      // verdict: the years of each colour
      const by = [[], [], [], []];
      for (const y of M.YEARS) { const e = cmp.get(y); if (e && e.st !== null) by[e.st === "ref" ? 0 : e.st].push(y); }
      const vcls = by[3].length ? "bad" : by[1].length || by[2].length ? "warn" : "ok";
      // years asked but on no printed page: the codes come from a correction
      // (1383 section 2, copied from 1384 as that page of the PDF is blank)
      const np = M.YEARS.filter(y => { const e = cmp.get(y); return e && e.st !== null && e.set.every(x => !x.page.get(y)); });
      const why = [...new Set(np.flatMap(y => cmp.get(y).set.map(x => M.DATA.corrections.find(k =>
        +k.year === y && k.action === "add_section" && +k.description === x.secAt(y))).filter(Boolean)))];
      h += `<div class="verdict ${vcls}"><b>${t.cm.seenFrom(yr(R))}</b><ul class="spans">` +
        by.map((ys, k) => ys.length ? `<li><i class="sw s${k}"></i>${t.cm.st[k]}: ${ranges(ys)}</li>` : "").join("") +
        (np.length ? `<li class="np"><i class="sw np"></i>${t.cm.npLine(ranges(np))}${why.length ? ":" : "."}` +
          why.map(k => `<div class="why" dir="ltr">${esc(k.reason)}</div>`).join("") + `</li>` : "") + `</ul></div>`;

      // timeline
      h += `<h3>${t.timeline}</h3>`;
      if (pdfBase && s.chains.some(x => x.years.some(y => x.page.get(y)))) h += `<div class="pdfhint">${t.pdfHint}</div>`;
      h += `<div class="timeline"><div class="tl" style="grid-template-columns:repeat(${M.YEARS.length},1fr)">`;
      h += M.YEARS.map(y => `<div class="y">${yr(y).slice(2)}</div>`).join("");
      h += M.YEARS.map(y => {
        const e = cmp.get(y), cls = stCls(e), text = tip(y, e);
        const printed = e && e.set.filter(x => pdfUrl(x, y));
        if (pdfBase && printed && printed.length) {
          return `<a class="c ${cls}" href="${pdfUrl(printed[0], y)}" target="_blank" rel="noopener" data-pdf="${esc(printed.map(x => x.id).join(" "))}" data-year="${y}" data-st="${e.st === "ref" ? 0 : e.st}" title="${esc(text)} · ${t.cm.openForm}"></a>`;
        }
        return `<div class="c ${cls}${np.includes(y) ? " np" : ""}" title="${esc(text)}${np.includes(y) ? ` · ${t.notPrinted}` : ""}"></div>`;
      }).join("");
      const present = new Set([...cmp.values()].map(e => (e.st === "ref" ? 0 : e.st)));
      h += `</div></div><div class="legend">` +
        [0, 1, 2, 3].filter(k => present.has(k)).map(k => `<span><i class="sw s${k}"></i>${t.cm.st[k]}</span>`).join("") +
        (present.has(null) ? `<span><i class="sw"></i>${t.cm.na}</span>` : "") +
        (np.length ? `<span><i class="sw np"></i>${t.cm.np}</span>` : "") +
        `<span><i class="sw s0 ref"></i>${t.cm.ref}</span></div>`;

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
      const py = [`# HIESIR Codebook, series ${s.id}: the item as asked in ${R}`,
        "# codes to add up in each year (the raw data's Commodity_Code)", "codes = {"];
      for (const y of M.YEARS) {
        const e = cmp.get(y);
        if (e && e.st !== null && e.st !== 3) py.push(`    ${y}: [${e.set.map(x => Number(x.code)).join(", ")}],`);
      }
      py.push("}");
      h += `<h3>${t.cm.useTitle}</h3><div class="uses">` + use.map(u => `<div class="use"><span class="yrs">${ranges(u.ys)}</span>` +
        `<span class="codes">${u.k === 3 ? `<span class="muted">${esc(u.e.partial ? t.cm.partial(u.codes) : t.cm.inside(u.e.set.map(x => x.code).join(fa ? "، " : ", ")))}</span>` : u.codes.split(" + ").map(code).join(" + ")}</span>` +
        `<span class="st"><i class="sw s${u.k}"></i>${t.cm.st[u.k]}</span></div>`).join("") + `</div>` +
        `<div class="note">${t.cm.useNote(yr(R))}</div><button type="button" class="copy" data-copy="${esc(py.join("\n"))}">${t.cm.copy}</button>`;

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
    function hashFor(id) {
      const p = [];
      if (id) p.push("item=" + encodeURIComponent(id));
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
        if (!allOpen) openKeys.add(d.dataset.key);
        d.open = true;
      }
      const lr = elList.getBoundingClientRect(), rr = row.getBoundingClientRect();
      if (force || rr.top < lr.top + 40 || rr.bottom > lr.bottom) elList.scrollTop += rr.top - lr.top - lr.height / 3;
    }
    /* the button after the card's title: back to the item in the list, even
       after browsing elsewhere; filters that hide it are cleared */
    function locate() {
      if (!selected) return;
      const s = M.serOf.get(selected), find = () => elList.querySelector(`.row[data-id="${CSS.escape(selected)}"]`);
      if (!find()) {
        elQ.value = ""; elSec.value = ""; elLinked.checked = false;
        if (ref && !s.years.includes(ref)) { ref = null; elRef.value = "all"; renderDetail(selected); }
        renderList(); setHash(hashFor(current()));
      }
      const row = find();
      if (!row) return;
      if (window.innerWidth <= 860) elList.scrollIntoView({ behavior: "smooth", block: "start" });
      reveal(row, true);
      row.classList.remove("flash"); void row.offsetWidth; row.classList.add("flash");
    }
    function select(sid, focusId = null, push = true) {
      selected = sid; focus = focusId;
      root.querySelectorAll(".row.sel").forEach(e => e.classList.remove("sel"));
      const row = root.querySelector(`.row[data-id="${CSS.escape(sid)}"]`);
      if (row) { row.classList.add("sel"); reveal(row, false); }
      renderDetail(sid);
      if (push) setHash(hashFor(focus || sid));
      if (window.innerWidth <= 860) elDetail.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    const isScope = r => r.rel === "same" && r.detail && r.detail !== "minor";
    const prevOf = y => M.YEARS[M.YEARS.indexOf(y) - 1];

    /* ---------- changes by year ----------
       Every change is one event: its kind, year, section (where its items
       sit that year) and the number of items it involves: 1 for a new,
       dropped, recoded or reworded item, the larger side of a merge, split
       or regrouping (99 merges that took in 261 items count 261), one per
       link between group headings and one per correction. */
    const KINDS = ["added", "dropped", "recoded", "merged", "split", "regrouped", "scope", "groups", "corr"];
    const DEFAULT_KINDS = KINDS.filter(k => k !== "groups" && k !== "corr");
    let EV = null, lastKind = null, lastKindAt = 0, soloBefore = null;
    function corrChain(k) {
      const y = +k.year;
      for (const cd of [k.value, k.expenditure_code]) {
        const cs = M.byCode.get(cd) || [];
        const c = cs.find(x => x.years.includes(y)) || cs[0];
        if (c) return c;
      }
      return null;
    }
    function corrSec(k) {
      if (k.action === "add_section") return +k.description;
      const c = corrChain(k);
      if (c) return c.secAt(+k.year);
      const g = M.G.find(g => g[0] === k.expenditure_code || g[0] === k.value);
      return g ? g[3] : null;
    }
    function events() {
      if (EV) return EV;
      EV = [];
      for (const r of M.DATA.relations) {
        const kind = r.rel === "same" ? (isScope(r) ? "scope" : null) : r.rel;
        if (!kind) continue;
        const tgt = M.CH.get(r.to[0]), src = M.CH.get(r.from[0]);
        EV.push({ kind, y: r.year, sec: tgt ? tgt.secAt(r.year) : src ? src.secAt(prevOf(r.year)) : null, n: Math.max(r.from.length, r.to.length), r });
      }
      for (const c of M.DATA.chains) {
        const y = c.years[0], last = c.years[c.years.length - 1];
        if (y !== M.YEARS[0] && !c.ins.some(r => r.year === y)) EV.push({ kind: "added", y, sec: c.secAt(y), n: 1, c });
        const next = M.YEARS[M.YEARS.indexOf(last) + 1];
        if (next && !c.outs.some(r => r.year === next)) EV.push({ kind: "dropped", y: next, sec: c.secAt(last), n: 1, c });
      }
      for (const g of M.DATA.groupLinks || []) EV.push({ kind: "groups", y: g[3], sec: M.G[g[1]][3], n: 1, g });
      for (const k of M.DATA.corrections) EV.push({ kind: "corr", y: +k.year, sec: corrSec(k), n: 1, k });
      return EV;
    }
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
      const ev = events(), secs = Object.keys(M.DATA.sections).map(Number), ys = M.YEARS;
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
      const gside = (gi, y) => `<div class="side"><div class="gh">${code(M.G[gi][0])}${fat(M.groupLabel(gi, y))}</div></div>`;
      const row = e => {
        if (e.r) return `<div class="yi">${side(e.r.from)}<span class="arrow">${ARROW}</span>${side(e.r.to)}<div class="reason">${tag(e)}${relPills(e.r)}</div></div>`;
        if (e.c) return `<div class="yi single">${chainLink(e.c)}<div>${fat(e.c.text)}</div><div class="reason">${tag(e)}<span class="pill">${ylabel(e.c)}</span></div></div>`;
        if (e.g) return `<div class="yi">${gside(e.g[0], prevOf(e.y))}<span class="arrow">${ARROW}</span>${gside(e.g[1], e.y)}<div class="reason">${tag(e)}<span class="pill info">${t.ch.grel[e.g[2]] || e.g[2]}</span> ${t.ch.moved(num(e.g[4]))}</div></div>`;
        const k = e.k, c = corrChain(k), y = +k.year, pg = c && c.page.get(y);
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
      const id = p.get("item"), s = id && M.serOf.get(id);
      let r = p.get("ref") === "all" ? null : M.YEARS.includes(+p.get("ref")) ? +p.get("ref") : M.LAST;
      // a link to an item not asked in the default year opens it among all items
      if (s && !p.has("ref") && !s.years.includes(r)) r = null;
      if (r !== ref) { ref = r; elRef.value = ref === null ? "all" : String(ref); renderList(); if (selected) renderDetail(selected); }
      if (s) {
        if (selected !== s.id || focus !== (id === s.id ? null : id)) {
          // an item outside the list is searched for, unless the hash sets the filters
          if (!q && !sec && !chg && !root.querySelector(`.row[data-id="${CSS.escape(s.id)}"]`)) { elQ.value = s.at(refOf(s)).code; renderList(); }
          select(s.id, id === s.id ? null : id, false);
        }
      } else if (!selected) emptyDetail();
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
      if (selected) renderDetail(selected);
      setHash(hashFor(current()));
    });
    root.addEventListener("click", e => {
      const pdfLink = e.target.closest("a[data-pdf]");
      if (pdfLink && !(e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button)) {
        e.preventDefault(); openPdf(pdfLink.dataset.pdf.split(" ").map(id => M.CH.get(id)).filter(Boolean), +pdfLink.dataset.year, pdfLink, pdfLink.dataset.st); return;
      }
      if (e.target.closest("[data-locate]")) { locate(); return; }
      const row = e.target.closest(".row"); if (row) { select(row.dataset.id); return; }
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
})();
