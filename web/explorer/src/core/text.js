/* Text helpers for search: Persian and Arabic digits, letter forms. No DOM. */

export const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹", AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";

/* Persian and Arabic digits as 0-9 */
export function latinDigits(s) {
  return s.replace(/[۰-۹]/g, d => FA_DIGITS.indexOf(d)).replace(/[٠-٩]/g, d => AR_DIGITS.indexOf(d));
}

/* a search key: digits as 0-9, Arabic letter forms as Persian, without
   diacritics, tatweel, ZWNJ, spaces or punctuation, lower case */
export function norm(s) {
  return latinDigits(s)
    .replace(/[يى]/g, "ی").replace(/ك/g, "ک").replace(/[ةۀ]/g, "ه").replace(/[أإٱ]/g, "ا").replace(/ؤ/g, "و")
    .replace(/[ً-ٰٟـ]/g, "")
    .replace(/[‌‍\s.,،؛;:!؟?()«»"'\/\\\-–_]+/g, "").toLowerCase();
}
