/* HIES explorer: search and browse the questionnaire items across years.
 *
 * The entry module: defines the <hies-explorer> element (app/element.js,
 * which lists its attributes). hiesir_codebook.explorer bundles it, with
 * what it imports, into one script for the offline page and the docs site.
 * The parts, each importing only from the ones before it:
 *   core/   the data model, comparison, search, changes (no DOM)
 *   i18n/   the interface text and number formats
 *   ui/     the views, as HTML from functions over a shared context
 *   app/    the URL scheme, the wiring (mount), the custom element
 */
import { defineExplorer } from "./app/element.js";

defineExplorer();
