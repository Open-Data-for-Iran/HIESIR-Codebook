/* Numbers and years in the page's language: Persian digits and separators
 * in Farsi. No DOM. */
import { FA_DIGITS } from "../core/text.js";

/* years: the survey years, in order (for ranges) */
export function makeFormat(lang, years) {
  const fa = lang === "fa";
  const num = n => Number(n).toLocaleString(fa ? "fa-IR" : "en-US");
  const yr = y => fa ? String(y).replace(/\d/g, d => FA_DIGITS[d]) : String(y);
  const yrs = ys => ys.map(yr).join(fa ? "، " : ", ");
  const span = (a, b) => a === b ? yr(a) : `${yr(a)}–${yr(b)}`;
  // the years a chain is asked under its code
  const ylabel = c => span(c.first, c.last);
  const ARROW = fa ? "←" : "→";
  /* consecutive survey years as ranges: 1383–1389، 1391 */
  function ranges(list) {
    const idx = list.map(y => years.indexOf(y)).sort((a, b) => a - b), parts = [];
    for (let i = 0; i < idx.length; i++) {
      let j = i;
      while (j + 1 < idx.length && idx[j + 1] === idx[j] + 1) j++;
      parts.push(span(years[idx[i]], years[idx[j]]));
      i = j;
    }
    return parts.join(fa ? "، " : ", ");
  }
  return { num, yr, yrs, span, ylabel, ranges, ARROW };
}
