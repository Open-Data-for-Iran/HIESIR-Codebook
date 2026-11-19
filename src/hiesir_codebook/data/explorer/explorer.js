/* HIES explorer: search and browse the questionnaire items across years.
 *
 * Mounts into every element with class "hx". Attributes on that element:
 *   data-lang  "en" or "fa" (Farsi switches the whole component to right-to-left)
 *   data-root  URL prefix of the published files (3_matched/, 2_corrected/)
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
      allSections: "All sections", changedOnly: "Linked only", current: "Still asked in {y}",
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
      printed: "Printed form", page: p => `p. ${p}`, openPdf: (y, p) => `${y}: page ${p}, open the printed form`,
      pv: { title: (y, p, n) => `Questionnaire ${y} · page ${p}${n ? ` of ${n}` : ""}`, prev: "Previous page", next: "Next page",
           zoomOut: "Zoom out", zoomIn: "Zoom in", tab: "Open in a new tab", close: "Close", loading: "Loading the questionnaire…",
           failed: "Could not load the PDF.", here: "The item is on this page" },
      tipNot: "not asked",
      rel: { same: "same item", recoded: "recoded", merged: "merged", split: "split", regrouped: "regrouped" },
      relVerb: { same: "continued", recoded: "recoded", merged: "merged", split: "split", regrouped: "regrouped" },
      det: { minor: "minor wording", label_reworded: "reworded", label_broadened: "broadened", label_narrowed: "narrowed" },
      v: { confirmed: "confirmed", changed: "changed by review", added: "added by review", definite: "definite", unverified: "unverified",
           confirmedTip: "checked by hand", changedTip: "corrected by hand", addedTip: "added by hand", definiteTip: "only wording differs" },
      heatCap: "Changes per section and year: new, dropped, recoded, merged and split items and wording changes. Click a cell.",
      stats: { added: "new items", dropped: "dropped items", recoded: "recoded", merged: "merges", split: "splits", regrouped: "regroupings", scope: "wording / scope changes", corr: "PDF corrections" },
      groups: { recoded: "Recoded: same item, new code", merged: "Merged", split: "Split", regrouped: "Regrouped", scope: "Wording or scope changed, same code", added: "New items", dropped: y => `Dropped: last asked in ${y}`, corr: "Corrections to the printed questionnaire" },
      about: (root, docs) => `
        <h4>What this shows</h4>
        <p>Every expenditure item of the HIES questionnaires 1383–1403 (1401 has no questionnaire), after the corrections, and how each item is linked through the years.${docs ? ` The full method is in <a href="${docs}">Methods</a>.` : ""}</p>
        <h4>Terms</h4>
        <dl>
          <dt>Item (chain)</dt><dd>One expenditure code with one label, followed while both stay the same. Its id is the code and first year, e.g. <span class="code">011114-1387</span>. Spacing, ZWNJ, punctuation and digit style do not count as a change.</dd>
          <dt>Comparable series</dt><dd>Items linked one-to-one (label reworded, or the same item under a new code). Values can be compared across the series; a <span class="pill warn">narrowed</span> or <span class="pill warn">broadened</span> step means the scope changed, so check the evidence first.</dd>
          <dt>Merged, split, regrouped</dt><dd>Several items became one, one became several, or a group was reorganised. The series ends there: sum the parts to compare.</dd>
          <dt>Verification</dt><dd><span class="pill ok">definite</span> only the wording differs; <span class="pill ok">confirmed</span>, <span class="pill info">changed by review</span> and <span class="pill info">added by review</span> were decided by hand in <span class="code">curated/links.csv</span> and <span class="code">curated/relations.csv</span>, mostly by checking how many households reported each code.</dd>
        </dl>
        <h4>Timeline colours</h4>
        <div class="legend"><span><i style="background:var(--on)"></i>asked as this item</span><span><i style="background:var(--other)"></i>same series, other code or label</span><span><i style="background:var(--gap)"></i>not asked</span></div>
        <h4>Joining with the raw data</h4>
        <p>Codes keep their leading zero (<span class="code">011111</span>); the raw data's <span class="code">Commodity_Code</span> stores them as numbers (<span class="code">11111</span>), so join on <span class="code">int(expenditure_code)</span>.</p>
        <h4>Download</h4>
        <ul>
          <li><a href="${root}3_matched/chains.csv">3_matched/chains.csv</a>: one row per item (chain)</li>
          <li><a href="${root}3_matched/links.csv">3_matched/links.csv</a>: 1 → 1 links that continue an item (same, recoded), with the evidence</li>
          <li><a href="${root}3_matched/relations.csv">3_matched/relations.csv</a>: merges, splits and regroupings between items, with the evidence</li>
          <li><a href="${root}2_corrected/questionnaire_1403.csv">2_corrected/questionnaire_1403.csv</a>: one questionnaire, corrected (change the year in the link)</li>
        </ul>`,
    },
    fa: {
      tabs: { items: "اقلام", years: "تغییرات هر سال", about: "راهنما" },
      placeholder: "جست‌وجوی کد (011114، 11114) یا متن (برنج، تلویزیون …)",
      allSections: "همه بخش‌ها", changedOnly: "فقط اقلام پیونددار", current: "هنوز پرسیده می‌شود ({y})",
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
      printed: "فرم چاپی", page: p => `ص ${p}`, openPdf: (y, p) => `${y}: صفحه ${p}، باز کردن فرم چاپی`,
      pv: { title: (y, p, n) => `پرسشنامه ${y} · صفحه ${p}${n ? ` از ${n}` : ""}`, prev: "صفحه قبل", next: "صفحه بعد",
           zoomOut: "کوچک‌نمایی", zoomIn: "بزرگ‌نمایی", tab: "باز کردن در زبانه تازه", close: "بستن", loading: "در حال بارگذاری پرسشنامه…",
           failed: "بارگذاری PDF ممکن نشد.", here: "قلم در این صفحه است" },
      tipNot: "پرسیده نشده",
      rel: { same: "همان قلم", recoded: "تغییر کد", merged: "ادغام", split: "تفکیک", regrouped: "بازگروه‌بندی" },
      relVerb: { same: "ادامه", recoded: "تغییر کد", merged: "ادغام", split: "تفکیک", regrouped: "بازگروه‌بندی" },
      det: { minor: "تغییر جزئی", label_reworded: "تغییر عبارت", label_broadened: "گسترده‌تر شده", label_narrowed: "محدودتر شده" },
      v: { confirmed: "تأییدشده", changed: "اصلاح در بازبینی", added: "افزوده در بازبینی", definite: "قطعی", unverified: "راستی‌آزمایی‌نشده",
           confirmedTip: "دستی بررسی شده", changedTip: "دستی اصلاح شده", addedTip: "دستی افزوده شده", definiteTip: "فقط عبارت فرق دارد" },
      heatCap: "تغییرات هر بخش در هر سال: اقلام جدید، حذف‌شده، تغییر کد، ادغام، تفکیک و تغییر عبارت. روی یک خانه کلیک کنید.",
      stats: { added: "قلم جدید", dropped: "قلم حذف‌شده", recoded: "تغییر کد", merged: "ادغام", split: "تفکیک", regrouped: "بازگروه‌بندی", scope: "تغییر عبارت یا دامنه", corr: "اصلاح PDF" },
      groups: { recoded: "تغییر کد: همان قلم با کد جدید", merged: "ادغام", split: "تفکیک", regrouped: "بازگروه‌بندی", scope: "تغییر عبارت یا دامنه با همان کد", added: "اقلام جدید", dropped: y => `حذف‌شده: آخرین بار در ${y} پرسیده شده`, corr: "اصلاحات پرسشنامه چاپی" },
      about: (root, docs) => `
        <h4>این صفحه چه نشان می‌دهد</h4>
        <p>همه اقلام هزینه‌ای پرسشنامه‌های طرح هزینه و درآمد خانوار ۱۳۸۳ تا ۱۴۰۳ (۱۴۰۱ پرسشنامه ندارد)، پس از اصلاحات، و پیوند هر قلم در طول سال‌ها.${docs ? ` روش کامل در <a href="${docs}">روش کار</a> آمده است.` : ""}</p>
        <h4>اصطلاحات</h4>
        <dl>
          <dt>قلم (زنجیره)</dt><dd>یک کد هزینه با یک عبارت، تا زمانی که هر دو ثابت بمانند. شناسه آن کد و نخستین سال است، مثلاً <span class="code">011114-1387</span>. فاصله، نیم‌فاصله، نشانه‌گذاری و شکل رقم تغییر حساب نمی‌شوند.</dd>
          <dt>سری قابل مقایسه</dt><dd>اقلامی که یک‌به‌یک به هم پیوند دارند (عبارت تازه، یا همان قلم با کد جدید). مقادیر در طول سری قابل مقایسه‌اند؛ گام <span class="pill warn">محدودتر شده</span> یا <span class="pill warn">گسترده‌تر شده</span> یعنی دامنه تغییر کرده، پس اول شاهد را ببینید.</dd>
          <dt>ادغام، تفکیک، بازگروه‌بندی</dt><dd>چند قلم یکی شده‌اند، یک قلم چند قلم شده، یا گروهی از نو سازمان یافته است. سری همان‌جا پایان می‌یابد: برای مقایسه، بخش‌ها را جمع بزنید.</dd>
          <dt>راستی‌آزمایی</dt><dd><span class="pill ok">قطعی</span> فقط عبارت فرق دارد؛ <span class="pill ok">تأییدشده</span>، <span class="pill info">اصلاح در بازبینی</span> و <span class="pill info">افزوده در بازبینی</span> را یک نفر در <span class="code">curated/links.csv</span> و <span class="code">curated/relations.csv</span>، بیشتر با بررسی تعداد خانوارهای گزارش‌دهنده هر کد، تعیین کرده است.</dd>
        </dl>
        <h4>رنگ‌های خط زمانی</h4>
        <div class="legend"><span><i style="background:var(--on)"></i>پرسیده‌شده به‌عنوان همین قلم</span><span><i style="background:var(--other)"></i>همان سری با کد یا عبارت دیگر</span><span><i style="background:var(--gap)"></i>پرسیده نشده</span></div>
        <h4>اتصال به داده‌های خام</h4>
        <p>کدها صفر ابتدایی‌شان را نگه می‌دارند (<span class="code">011111</span>)؛ ستون <span class="code">Commodity_Code</span> داده‌های خام آن‌ها را عدد ذخیره می‌کند (<span class="code">11111</span>)، پس اتصال را با <span class="code">int(expenditure_code)</span> انجام دهید.</p>
        <h4>دریافت</h4>
        <ul>
          <li><a href="${root}3_matched/chains.csv">3_matched/chains.csv</a>: هر قلم (زنجیره) یک سطر</li>
          <li><a href="${root}3_matched/links.csv">3_matched/links.csv</a>: پیوندهای یک‌به‌یکی که یک قلم را ادامه می‌دهند (همان قلم، تغییر کد)، همراه با شاهد</li>
          <li><a href="${root}3_matched/relations.csv">3_matched/relations.csv</a>: ادغام‌ها، تفکیک‌ها و بازگروه‌بندی‌ها، همراه با شاهد</li>
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
    const CH = new Map(DATA.chains.map(c => [c.id, c]));
    for (const c of DATA.chains) {
      const miss = new Set(c.miss);
      c.years = YEARS.filter(y => y >= c.first && y <= c.last && !miss.has(y));
      c.page = new Map(c.years.map((y, i) => [y, c.pg ? c.pg[i] : null]));
      c.box = new Map(c.years.map((y, i) => [y, c.bx ? c.bx[i] : null]));
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
    return { DATA, YEARS, LAST, CH, byCode };
  }
  const is11 = r => (r.rel === "same" || r.rel === "recoded") && r.from.length === 1 && r.to.length === 1;
  const linked = c => c.ins.length || c.outs.length;

  /* series: walk one-to-one links back and forward; links[i] joins steps[i-1] -> steps[i] */
  function series(M, c) {
    const back = [], fwd = [], seen = new Set([c.id]);
    let cur = c;
    for (;;) {
      const r = cur.ins.find(is11); if (!r) break;
      const p = M.CH.get(r.from[0]); if (!p || seen.has(p.id)) break;
      seen.add(p.id); back.unshift({ chain: p, link: r }); cur = p;
    }
    cur = c;
    for (;;) {
      const r = cur.outs.find(is11); if (!r) break;
      const n = M.CH.get(r.to[0]); if (!n || seen.has(n.id)) break;
      seen.add(n.id); fwd.push({ chain: n, link: r }); cur = n;
    }
    return {
      steps: [...back.map(s => s.chain), c, ...fwd.map(s => s.chain)],
      links: [null, ...back.map(s => s.link), ...fwd.map(s => s.link)],
    };
  }

  function search(M, q) {
    const raw = q.trim();
    if (!raw) return null;
    const ascii = raw.replace(/[۰-۹]/g, d => FA_DIGITS.indexOf(d)).replace(/[٠-٩]/g, d => AR_DIGITS.indexOf(d));
    const m = ascii.match(/^(\d+)(?:-(\d{4}))?$/);
    if (m) {
      const d = m[1], cands = new Set([d]);
      if (d.length === 5 || d.length === 3) cands.add("0" + d);
      return M.DATA.chains.filter(c => [...cands].some(x => c.code.startsWith(x)) && (!m[2] || c.id.endsWith(m[2])))
        .map(c => [c, cands.has(c.code) ? 0 : 1]);
    }
    const toks = raw.split(/\s+/).map(norm).filter(Boolean);
    const out = [];
    for (const c of M.DATA.chains) {
      if (!toks.every(t => c.key.includes(t))) continue;
      out.push([c, (toks.every(t => c.key0.includes(t)) ? 0 : 2) + (c.key0.startsWith(toks[0]) ? 0 : 1)]);
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
    const secTitle = s => (M.DATA.sections[s] || "").replace(/^هزینه‌(های|ی) /, "");
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
    function strip(c) {
      const on = new Set(c.years);
      return `<span class="strip">` + M.YEARS.map(y => `<i class="${on.has(y) ? "on" : ""}"></i>`).join("") + `</span>`;
    }

    /* skeleton */
    const sectionOpts = Object.keys(M.DATA.sections).map(n => `<option value="${n}">${yr(n)} · ${esc(secTitle(n).slice(0, 48))}</option>`).join("");
    root.innerHTML = `
      <nav class="hx-tabs">
        <a data-tab="items" href="#">${t.tabs.items}</a>
        <a data-tab="years" href="#year">${t.tabs.years}</a>
        <a data-tab="about" href="#about">${t.tabs.about}</a>
      </nav>
      <section class="hx-view" data-view="items">
        <div class="hx-search">
          <input class="hx-q" type="search" autocomplete="off" spellcheck="false" placeholder="${esc(t.placeholder)}" aria-label="${esc(t.placeholder)}">
          <select class="hx-sec"><option value="">${t.allSections}</option>${sectionOpts}</select>
          <label class="chip"><input type="checkbox" class="hx-linked"> ${t.changedOnly}</label>
          <label class="chip"><input type="checkbox" class="hx-current"> ${t.current.replace("{y}", yr(M.LAST))}</label>
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
    const elQ = $(".hx-q"), elSec = $(".hx-sec"), elLinked = $(".hx-linked"), elCurrent = $(".hx-current");
    const elList = $(".hx-list"), elDetail = $(".hx-detail"), elYears = $('[data-view="years"]');
    let selected = null;

    function renderList() {
      const res = search(M, elQ.value);
      const sec = elSec.value;
      let rows = (res || M.DATA.chains.map(c => [c, 0]))
        .filter(([c]) => (!sec || c.s == sec) && (!elLinked.checked || linked(c)) && (!elCurrent.checked || c.last === M.LAST));
      rows.sort((a, b) => (res ? a[1] - b[1] : 0) || a[0].s - b[0].s || a[0].code.localeCompare(b[0].code) || a[0].first - b[0].first);
      const groups = new Map();
      for (const [c] of rows) (groups.get(c.s) || groups.set(c.s, []).get(c.s)).push(c);
      const open = res || sec || groups.size === 1 || rows.length < 80;
      let h = `<div class="count">${t.count(num(rows.length), !!res)}</div>`;
      if (!rows.length) h += `<div class="empty">${t.noMatch}</div>`;
      for (const [s, cs] of groups) {
        h += `<details class="sec" ${open ? "open" : ""}><summary><span>${yr(s)}</span>${fat(secTitle(s))}<span class="n">${num(cs.length)}</span></summary>`;
        for (const c of cs) {
          h += `<div class="row${selected === c.id ? " sel" : ""}" data-id="${esc(c.id)}">${code(c.code)}${fat(c.text, "div")}` +
            `<div class="meta">${strip(c)}<span class="yrs">${ylabel(c)}</span>${linked(c) ? `<span class="pill info" title="${t.linkedTip}">${t.linked}</span>` : ""}</div></div>`;
        }
        h += `</details>`;
      }
      elList.innerHTML = h;
    }

    function emptyDetail() {
      const ex = ["برنج", "11114", "تلویزیون", "دندان"].map(q => `<a data-q="${q}">${q}</a>`);
      elDetail.innerHTML = `<div class="empty"><div class="big">${t.pick}</div>
        ${t.summary(num(M.DATA.chains.length), num(M.YEARS.length), num(M.DATA.relations.length))}<br>
        ${t.tryThese} ${ex.slice(0, 3).join(fa ? "، " : ", ")} ${t.or} ${ex[3]}</div>`;
    }

    function renderDetail(id) {
      const c = M.CH.get(id);
      if (!c) { emptyDetail(); return; }
      const ser = series(M, c);
      const first = ser.steps[0], last = ser.steps[ser.steps.length - 1];
      const scope = ser.links.filter(l => l && (l.detail === "label_broadened" || l.detail === "label_narrowed"));
      const recodes = ser.links.filter(l => l && l.rel === "recoded");
      const sYears = [...new Set(ser.steps.flatMap(s => s.years))].sort();
      const before = c.ins.filter(r => !is11(r)), after = c.outs.filter(r => !is11(r));
      const firstBreak = first.ins.find(r => !is11(r)), lastBreak = last.outs.find(r => !is11(r));

      let h = `<div class="crumbs fa">${[M.DATA.sections[c.s], ...c.path.map(p => p[1])].filter(Boolean).map(s => `<span>${esc(s)}</span>`).join("")}</div>`;
      h += `<div class="title fa">${esc(c.text)}</div>`;
      h += `<div class="ids">${code(c.code)} <span class="pill">${t.section(yr(c.s))}</span> <span class="pill">${t.asked(ylabel(c))}${c.miss.length ? `، ${t.notIn(yrs(c.miss))}`.replace("،", fa ? "،" : ",") : ""}</span> <span class="pill" title="${t.chainId}">${esc(c.id)}</span></div>`;

      if (pdfBase) {
        const ends = [...new Set([c.years[0], c.years[c.years.length - 1]])].filter(y => pdfUrl(c, y));
        if (ends.length) h += `<div class="printed">${t.printed}: ` + ends.map(y => `<a href="${pdfUrl(c, y)}" target="_blank" rel="noopener" data-pdf="${esc(c.id)}" data-year="${y}">${yr(y)}، ${t.page(num(c.page.get(y)))} ↗</a>`.replace("، ", fa ? "، " : ", ")).join(" · ") + `</div>`;
      }
      const sp = span(sYears[0], sYears[sYears.length - 1]);
      const notes = [];
      if (recodes.length) notes.push(t.codeChanges(yrs(recodes.map(l => l.year))));
      if (ser.steps.length > recodes.length + 1) notes.push(t.labels(num(ser.steps.length)));
      const warn = scope.length > 0;
      let v = `<div class="verdict ${warn ? "warn" : "ok"}"><b>${ser.steps.length === 1 ? t.comparable(sp) : t.comparableSeries(sp)}${warn ? t.withScope : ""}</b>`;
      v += ser.steps.length === 1 ? t.sameEveryYear : t.followed(notes.join(fa ? "، " : ", "));
      if (warn) v += t.scope(scope.map(l => t.scopeIn(t.det[l.detail], yr(l.year))).join(fa ? "، " : ", "), scope.length === 1);
      if (firstBreak) v += t.before(yr(first.first), t.relVerb[firstBreak.rel]);
      if (lastBreak) v += t.after(yr(last.last), t.relVerb[lastBreak.rel]);
      else if (last.last !== M.LAST) v += t.notAfter(yr(last.last));
      h += v + `</div>`;

      const on = new Set(c.years), other = new Map();
      for (const s of ser.steps) if (s !== c) for (const y of s.years) other.set(y, s);
      const marks = new Set(ser.links.filter(Boolean).map(l => l.year));
      h += `<h3>${t.timeline}</h3><div class="timeline"><div class="tl" style="grid-template-columns:repeat(${M.YEARS.length},1fr)">`;
      h += M.YEARS.map(y => `<div class="y">${yr(y).slice(2)}</div>`).join("");
      h += M.YEARS.map(y => {
        const o = other.get(y);
        const cls = on.has(y) ? "on" : o ? "other" : "";
        const tip = on.has(y) ? `${yr(y)}: ${c.code}` : o ? `${yr(y)}: ${o.code} ${o.text}` : `${yr(y)}: ${t.tipNot}`;
        const href = on.has(y) && pdfUrl(c, y);
        if (href) return `<a class="c ${cls}${marks.has(y) ? " mark" : ""}" href="${href}" target="_blank" rel="noopener" data-pdf="${esc(c.id)}" data-year="${y}" title="${esc(t.openPdf(yr(y), num(c.page.get(y))))}"></a>`;
        return `<div class="c ${cls}${marks.has(y) ? " mark" : ""}" title="${esc(tip)}"${o ? ` data-go="${esc(o.id)}"` : ""}></div>`;
      }).join("");
      h += `</div></div><div class="legend"><span><i style="background:var(--on)"></i>${t.lgThis}</span><span><i style="background:var(--other)"></i>${t.lgOther}</span><span><i style="background:var(--gap)"></i>${t.lgGap}</span><span><i style="box-shadow:inset 0 0 0 2px var(--warn)"></i>${t.lgMark}</span></div>`;

      if (ser.steps.length > 1) {
        h += `<h3>${t.series}</h3><div class="steps">`;
        ser.steps.forEach((s, i) => {
          const l = ser.links[i];
          if (l) h += `<div class="link">${yr(l.year)} ${relPills(l)}</div>`;
          h += `<div class="step${s === c ? " cur" : ""}"><div class="hd">${s === c ? code(s.code) : chainLink(s)} <span class="pill">${ylabel(s)}</span></div>${fat(s.text)}` +
            (l && l.note ? `<details class="note"><summary>${t.evidence}</summary>${esc(l.note)}</details>` : "") + `</div>`;
        });
        h += `</div>`;
      }

      const relBlock = r => {
        const side = ids => `<ul>${ids.map(i => { const x = M.CH.get(i); return x ? `<li class="${x === c ? "me" : ""}">${x === c ? code(x.code) : chainLink(x)}${fat(x.text)}</li>` : ""; }).join("")}</ul>`;
        return `<div class="rel"><div class="hd"><b>${yr(r.year)}</b> ${relPills(r)}</div><div class="sides">${side(r.from)}<span class="arrow">${ARROW}</span>${side(r.to)}</div>` +
          (r.note ? `<details class="note"><summary>${t.evidence}</summary>${esc(r.note)}</details>` : "") + `</div>`;
      };
      if (before.length) h += `<h3>${t.cameFrom}</h3>` + before.map(relBlock).join("");
      if (after.length) h += `<h3>${t.wentInto}</h3>` + after.map(relBlock).join("");

      const inSer = new Set(ser.steps.map(s => s.id));
      const others = (M.byCode.get(c.code) || []).filter(x => !inSer.has(x.id));
      if (others.length) {
        h += `<h3>${t.otherUnder(code(c.code))}</h3>`;
        h += others.map(x => `<div class="link">${chainLink(x)} <span class="pill">${ylabel(x)}</span> ${fat(x.text)}</div>`).join("");
      }

      const corr = M.DATA.corrections.filter(k => k.expenditure_code === c.code || k.value === c.code);
      if (corr.length) {
        h += `<h3>${t.corrections}</h3>`;
        h += corr.map(k => `<div class="rel"><div class="hd"><b>${yr(k.year)}</b> <span class="pill warn">${esc(k.action)}</span> ${code(k.expenditure_code)}${k.value ? ` ${ARROW} ${/^\d+$/.test(k.value) ? code(k.value) : fat(k.value)}` : ""}</div>${fat(k.description, "div")}<div class="note" dir="ltr">${esc(k.reason)}</div></div>`).join("");
      }
      elDetail.innerHTML = h;
      elDetail.scrollTop = 0;
    }

    function select(id, push = true) {
      selected = id;
      root.querySelectorAll(".row.sel").forEach(e => e.classList.remove("sel"));
      root.querySelector(`.row[data-id="${CSS.escape(id)}"]`)?.classList.add("sel");
      renderDetail(id);
      if (push) history.replaceState(null, "", "#item=" + encodeURIComponent(id));
      if (window.innerWidth <= 860) elDetail.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function yearStats(y) {
      const rels = M.DATA.relations.filter(r => r.year === y);
      const prev = M.YEARS[M.YEARS.indexOf(y) - 1];
      const inn = new Set(rels.flatMap(r => r.to)), out = new Set(rels.flatMap(r => r.from));
      return {
        rels,
        added: M.DATA.chains.filter(c => c.first === y && !inn.has(c.id) && y !== M.YEARS[0]),
        dropped: prev ? M.DATA.chains.filter(c => c.last === prev && !out.has(c.id)) : [],
        corr: M.DATA.corrections.filter(k => +k.year === y),
      };
    }
    const isScope = r => r.rel === "same" && r.detail && r.detail !== "minor";

    function renderYears(y) {
      const secs = Object.keys(M.DATA.sections).map(Number), ys = M.YEARS.slice(1);
      const cnt = {}; let max = 1;
      for (const yy of ys) {
        const st = yearStats(yy);
        for (const s of secs) {
          const n = st.rels.filter(r => r.rel !== "same" || isScope(r)).filter(r => M.CH.get(r.to[0])?.s === s || M.CH.get(r.from[0])?.s === s).length
            + st.added.filter(c => c.s === s).length + st.dropped.filter(c => c.s === s).length;
          cnt[`${s}-${yy}`] = n; max = Math.max(max, n);
        }
      }
      let h = `<div class="yearbar">` + ys.map(yy => `<a href="#year=${yy}" class="${yy === y ? "active" : ""}">${yr(yy)}</a>`).join("") + `</div>`;
      h += `<div class="panel heat"><div class="cap">${t.heatCap}</div><table><tr><th></th>${ys.map(yy => `<th>${yr(yy).slice(2)}</th>`).join("")}</tr>`;
      for (const s of secs) {
        h += `<tr><th class="s fa" title="${esc(M.DATA.sections[s])}">${yr(s)} · ${esc(secTitle(s).slice(0, 32))}</th>`;
        for (const yy of ys) {
          const n = cnt[`${s}-${yy}`], a = n ? 0.12 + 0.88 * Math.sqrt(n / max) : 0;
          const style = n ? `background:color-mix(in srgb, var(--accent) ${Math.round(a * 100)}%, var(--panel));color:${a > .55 ? "var(--on-accent)" : "var(--ink)"}` : "";
          h += `<td class="${n ? "" : "z"}${yy === y ? " sel" : ""}" data-year="${yy}" title="${yr(yy)} · ${t.section(yr(s))}: ${num(n)}" style="${style}">${n ? num(n) : ""}</td>`;
        }
        h += `</tr>`;
      }
      h += `</table></div>`;

      const st = yearStats(y);
      const by = k => st.rels.filter(r => r.rel === k);
      const scope = st.rels.filter(isScope);
      h += `<div class="cards">` + [
        [st.added.length, t.stats.added], [st.dropped.length, t.stats.dropped], [by("recoded").length, t.stats.recoded],
        [by("merged").length, t.stats.merged], [by("split").length, t.stats.split], [by("regrouped").length, t.stats.regrouped],
        [scope.length, t.stats.scope], [st.corr.length, t.stats.corr],
      ].map(([n, k]) => `<div class="panel stat"><div class="v">${num(n)}</div><div class="k">${k}</div></div>`).join("") + `</div>`;

      const item = c => `<div class="side">${chainLink(c)}${fat(c.text)}</div>`;
      const relRows = rs => rs.map(r => `<div class="yi"><div class="side">${r.from.map(i => M.CH.get(i)).filter(Boolean).map(item).join("")}</div><span class="arrow">${ARROW}</span><div class="side">${r.to.map(i => M.CH.get(i)).filter(Boolean).map(item).join("")}</div><div class="reason">${relPills(r)}</div></div>`).join("");
      const single = cs => cs.map(c => `<div class="yi single">${chainLink(c)}${fat(c.text, "div")}</div>`).join("");
      const group = (title, body, n) => n ? `<div class="panel group"><h3>${title} (${num(n)})</h3>${body}</div>` : "";
      h += group(t.groups.recoded, relRows(by("recoded")), by("recoded").length);
      h += group(t.groups.merged, relRows(by("merged")), by("merged").length);
      h += group(t.groups.split, relRows(by("split")), by("split").length);
      h += group(t.groups.regrouped, relRows(by("regrouped")), by("regrouped").length);
      h += group(t.groups.scope, relRows(scope), scope.length);
      h += group(t.groups.added, single(st.added), st.added.length);
      h += group(t.groups.dropped(yr(M.YEARS[M.YEARS.indexOf(y) - 1])), single(st.dropped), st.dropped.length);
      h += group(t.groups.corr, st.corr.map(k => `<div class="yi single">${code(k.expenditure_code || "—")}<div><span class="pill warn">${esc(k.action)}</span> ${fat(k.description)}${k.value ? ` ${ARROW} ${/^\d+$/.test(k.value) ? code(k.value) : fat(k.value)}` : ""}</div><div class="reason" dir="ltr">${esc(k.reason)}</div></div>`).join(""), st.corr.length);
      elYears.innerHTML = h;
    }

    function show(view) {
      root.querySelectorAll(".hx-view").forEach(e => e.classList.toggle("active", e.dataset.view === view));
      root.querySelectorAll(".hx-tabs a").forEach(a => a.classList.toggle("active", a.dataset.tab === view));
    }
    function route() {
      const h = decodeURIComponent(location.hash.slice(1));
      if (h.startsWith("year")) {
        const y = +h.split("=")[1];
        show("years"); renderYears(M.YEARS.includes(y) && y !== M.YEARS[0] ? y : 1386); return;
      }
      if (h === "about") { show("about"); return; }
      show("items");
      if (h.startsWith("item=")) {
        const id = h.slice(5);
        if (M.CH.has(id) && selected !== id) {
          if (!root.querySelector(`.row[data-id="${CSS.escape(id)}"]`)) { elQ.value = M.CH.get(id).code; renderList(); }
          select(id, false);
        }
      } else if (!selected) emptyDetail();
    }

    let timer;
    elQ.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(renderList, 80); });
    elQ.addEventListener("keydown", e => {
      if (e.key === "Enter") { clearTimeout(timer); renderList(); const r = elList.querySelector(".row"); if (r) select(r.dataset.id); }
    });
    [elSec, elLinked, elCurrent].forEach(e => e.addEventListener("change", renderList));
    root.addEventListener("click", e => {
      const pdfLink = e.target.closest("a[data-pdf]");
      if (pdfLink && !(e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button)) {
        e.preventDefault(); openPdf(M.CH.get(pdfLink.dataset.pdf), +pdfLink.dataset.year, pdfLink); return;
      }
      const row = e.target.closest(".row"); if (row) { select(row.dataset.id); return; }
      const go = e.target.closest("[data-go]");
      if (go) { e.preventDefault(); location.hash = "item=" + encodeURIComponent(go.dataset.go); return; }
      const q = e.target.closest("[data-q]");
      if (q) { e.preventDefault(); elQ.value = q.dataset.q; renderList(); elQ.focus(); return; }
      const td = e.target.closest("td[data-year]"); if (td) location.hash = "year=" + td.dataset.year;
    });
    /* in-page viewer: one page of a questionnaire PDF, with an optional
       highlight box [top, bottom] in PDF points from the top of the page */
    const viewer = document.createElement("div");
    viewer.className = "hx-viewer"; viewer.hidden = true;
    viewer.setAttribute("role", "dialog"); viewer.setAttribute("aria-modal", "true");
    viewer.innerHTML = `<div class="hx-vbox">
        <div class="hx-vbar">
          <b class="hx-vtitle"></b><span class="hx-vspacer"></span>
          <button type="button" data-act="prev" title="${t.pv.prev}" aria-label="${t.pv.prev}">${fa ? "›" : "‹"}</button>
          <button type="button" data-act="next" title="${t.pv.next}" aria-label="${t.pv.next}">${fa ? "‹" : "›"}</button>
          <button type="button" data-act="out" title="${t.pv.zoomOut}" aria-label="${t.pv.zoomOut}">−</button>
          <button type="button" data-act="in" title="${t.pv.zoomIn}" aria-label="${t.pv.zoomIn}">+</button>
          <a class="hx-vtab" target="_blank" rel="noopener" title="${t.pv.tab}" aria-label="${t.pv.tab}">↗</a>
          <button type="button" data-act="close" title="${t.pv.close}" aria-label="${t.pv.close}">✕</button>
        </div>
        <div class="hx-vbody"><div class="hx-vpage"><canvas></canvas><div class="hx-vmark" title="${t.pv.here}" hidden></div></div><div class="hx-vmsg"></div></div>
      </div>`;
    root.appendChild(viewer);
    const vEl = s => viewer.querySelector(s);
    const canvas = vEl("canvas"), mark = vEl(".hx-vmark"), vmsg = vEl(".hx-vmsg"), vbody = vEl(".hx-vbody");
    const vs = { url: "", year: 0, page: 1, n: 0, zoom: 1, box: null, boxPage: 0, back: null, token: 0, task: null };

    async function showPage() {
      const token = ++vs.token;
      vEl(".hx-vtitle").textContent = t.pv.title(yr(vs.year), num(vs.page), vs.n ? num(vs.n) : "");
      vEl(".hx-vtab").href = `${vs.url}#page=${vs.page}`;
      vEl('[data-act="prev"]').disabled = vs.page <= 1;
      vEl('[data-act="next"]').disabled = !!vs.n && vs.page >= vs.n;
      vmsg.textContent = t.pv.loading; mark.hidden = true;
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
        if (vs.box && vs.page === vs.boxPage) {
          const k = vp.scale, pad = 3;
          mark.style.top = `${vs.box[0] * k - pad}px`; mark.style.height = `${(vs.box[1] - vs.box[0]) * k + 2 * pad}px`;
          mark.hidden = false;
          vbody.scrollTop = Math.max(0, vs.box[0] * k - vbody.clientHeight / 3);
        }
      } catch (err) {
        if (err && err.name === "RenderingCancelledException") return;
        if (token === vs.token) vmsg.textContent = t.pv.failed;
      }
    }
    function openPdf(c, y, from) {
      if (!c || !c.page.get(y)) return;
      Object.assign(vs, { url: `${pdfBase}questionnaire_${y}.pdf`, year: y, page: c.page.get(y), n: 0, zoom: 1,
                          box: c.box ? c.box.get(y) || null : null, boxPage: c.page.get(y), back: from || null });
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
