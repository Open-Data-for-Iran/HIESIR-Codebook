/* Labels: section titles and periods, heading names, the pills of a link.
 *
 * Every ui/ module is a factory, createX(ctx), over the context that
 * app/mount.js builds: { M (core/model.js), t (i18n strings), lang, fa,
 * fmt (i18n/format.js), state, refOf, nodeRef, pdfBase, pdfUrl, ... }.
 */
import { code, fat } from "./html.js";

export function createLabels(ctx) {
  const { M, t } = ctx;
  const PERIOD = /\s*(?:خانوار\s*)?(?:در\s+(12|۱۲)?\s*ماه گذشته)?\s*$/;
  // a section's title without "the household's expenses" and its period
  const secTitle = (s, y = null) => M.sectionTitle(s, y).replace(/^هزینه‌(های|ی) /, "").replace(PERIOD, "");
  const secPeriod = s => { const m = (M.DATA.sections[s] || "").match(/در\s+(12|۱۲)?\s*ماه گذشته\s*$/); return m ? (m[1] ? t.period.y : t.period.m) : ""; };
  const secHead = (s, y = null) => `${code(s)}${fat(secTitle(s, y), "span", "st")}`;
  // the period a section asks about: "m" last month, "y" last 12 months
  // (a section whose latest title names none goes with its neighbours)
  const secKind = s => /در\s+(12|۱۲)\s*ماه گذشته\s*$/.test(M.DATA.sections[s] || "") ? "y" : "m";
  // a heading node's name as printed in year y
  const nodeLabel = (n, y) => (n.kind === "s" ? M.sectionTitle(n.sec, y) : M.groupLabel(n.giAt(y), y));

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
  return { secTitle, secPeriod, secHead, secKind, nodeLabel, relPills, verifPill };
}
