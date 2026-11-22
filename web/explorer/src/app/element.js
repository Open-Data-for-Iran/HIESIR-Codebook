/* <hies-explorer>: the explorer as a custom element, so any page or
 * framework can embed it with one tag:
 *
 *   <hies-explorer data-lang="fa" data-src="data.json" data-pdf="pdf/"></hies-explorer>
 *
 * Attributes (read once, when it is first connected):
 *   data-lang  "en" or "fa" (Farsi switches the whole component to right-to-left)
 *   data-src   URL of data.json; not needed when the page sets window.HX_DATA
 *   data-root  URL prefix of the published CSVs (3_items/, 2_corrected/), for the How to read tab
 *   data-docs  URL of the methods page (optional)
 *   data-pdf   URL prefix of the questionnaire PDFs (optional); items then link
 *              to the page they are printed on
 * No shadow DOM: it takes the page's styles (styles/explorer.css, scoped
 * under .hx, which it adds to itself), so a site can theme it.
 */
import { model } from "../core/model.js";
import { esc } from "../ui/html.js";
import { mount } from "./mount.js";

/* the model of each data source, built once and shared by every element */
const models = new Map();
function loadModel(src) {
  const key = window.HX_DATA ? "HX_DATA" : src;
  if (!models.has(key)) {
    const p = (async () => model(window.HX_DATA || (await (await fetch(src)).json())))();
    models.set(key, p);
    p.catch(() => models.delete(key));
  }
  return models.get(key);
}

export class HiesExplorer extends HTMLElement {
  async connectedCallback() {
    if (this._started) return;  // moved in the page: keep what it shows
    this._started = true;
    this.classList.add("hx");
    const src = this.dataset.src;
    try {
      const M = await loadModel(src);
      this._api = mount(this, M);
    } catch (err) {
      this.innerHTML = `<p>Could not load ${esc(src)}: ${esc(err)}</p>`;
    }
  }
  /* back to the items, with the cursor in the search box */
  focusSearch() { this._api?.focusSearch(); }
}

export function defineExplorer(name = "hies-explorer") {
  if (!customElements.get(name)) customElements.define(name, HiesExplorer);
}
