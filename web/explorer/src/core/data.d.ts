/* The data the explorer reads: explorer/data.json on the docs site, or
 * window.HX_DATA in the offline page. Written by
 * hiesir_codebook.explorer.collect() from output/; this file is its
 * contract, for editors and for any other site or service that reads it.
 *
 * Years are Iranian (Solar Hijri) survey years, such as 1383. A "chain" is
 * one item under one code over a run of years; links join chains across
 * years (the same item reworded or recoded, a merge, a split ...).
 */

export type Year = number;
/** "011111": a six-digit expenditure code, kept as text (leading zero). */
export type Code = string;
/** "011111-1383": an expenditure code and the first year it is asked under it. */
export type ChainId = string;

export interface HxData {
  /** the survey years, in order */
  years: Year[];
  /** section number (as a JSON key) -> its title, as printed in the latest year */
  sections: Record<string, string>;
  /** the sections whose title changed: number -> [[first year, title], ...] */
  sectionYears: Record<string, [Year, string][]>;
  /** the printed group headers across years; DATA.groups[i] is group i */
  groups: Group[];
  /** links between groups, except the rejected ones */
  groupLinks: GroupLink[];
  /** groupIds[i]: the id of group i ("0111-1383": code and first year, as in output/4_groups/) */
  groupIds: string[];
  chains: Chain[];
  /** links between chains (output/3_items/links.csv and relations.csv), except the rejected ones */
  relations: Relation[];
  /** the hand corrections to the printed questionnaires (curated/2_corrected/corrections.csv) */
  corrections: Correction[];
}

/**
 * [code, label, level, section] and, when its wording changed over the years,
 * [[first year, label], ...]. code may join several ("01111, 01112");
 * level is 2, 3 or 4 (the depth of the header); label is the latest wording.
 */
export type Group =
  | [code: string, label: string, level: number, section: number]
  | [code: string, label: string, level: number, section: number, wordings: [Year, string][]];

/** [from group, to group, relation, year, number of items it moved]: group indexes into groups */
export type GroupLink = [from: number, to: number, rel: "continued" | "moved" | "merged" | "split" | "regrouped", year: Year, items: number];

export interface Chain {
  id: ChainId;
  /** its section in its first year (Chain.gp gives later ones) */
  s: number;
  code: Code;
  first: Year;
  last: Year;
  /** years between first and last when it is not asked */
  miss: Year[];
  /** its wording, Persian */
  text: string;
  /** the group headers printed above it in its last year, outermost first: [code, label] */
  path: [string, string][];
  /** in each year it is asked (in order): the PDF page it is printed on, or null (added by a correction) */
  pg: (number | null)[];
  /** and its box on that page in PDF points from the top-left: [top, bottom, left, right], or [top, bottom] with no table around it */
  bx: ([number, number] | [number, number, number, number] | null)[];
  /** its groups each time they change: [first year, [group indexes, outermost first]] */
  gp: [Year, number[]][];
}

export interface Relation {
  id: string;
  from: ChainId[];
  to: ChainId[];
  /** same and recoded join one chain to one; the others many to many */
  rel: "same" | "recoded" | "merged" | "split" | "regrouped";
  /** for "same": how the wording changed ("" when it did not) */
  detail: "" | "minor" | "label_reworded" | "label_broadened" | "label_narrowed";
  /** the first year of the "to" side */
  year: Year;
  /** decided by no rule and not yet reviewed */
  check: boolean;
  /** the review: "" none */
  verified: "" | "confirmed" | "changed" | "added";
  /** the evidence */
  note: string;
}

/** a row of curated/2_corrected/corrections.csv, all fields as text */
export interface Correction {
  year: string;
  action: "add_section" | "delete" | "recode" | "recode_header" | "retext" | "retext_header" | string;
  expenditure_code: string;
  description: string;
  value: string;
  reason: string;
}
