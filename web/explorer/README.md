# The explorer

The page that searches and browses the matched questionnaire items across
years, as a reusable web component: `<hies-explorer>`. It is website code,
kept apart from the Python package, in plain ES modules and CSS with no
dependencies, so another site can take all of it or only the parts it needs.

The documentation site draws it: `docs/explorer.md` → `overrides/explorer.html`,
which loads the files that `scripts/mkdocs_hooks.py` publishes under
`assets/explorer/` and fetches `explorer/data.json`.

The data (`data.json`, or `window.HX_DATA` when a page embeds it) is made
when the site is built, by `hiesir_codebook.explorer.collect()` from the CSVs
of `output/`; nothing of the explorer is kept in `output/`. Its shape is
[`src/core/data.d.ts`](src/core/data.d.ts).

## The parts

Four layers, each importing only from the ones above it:

```
src/core/              pure JS, no DOM: runs in a browser, Node, a worker or a server
  data.d.ts            the shape of data.json: the contract with the Python build
  text.js              norm() and digits: the search keys
  model.js             model(DATA): series, heading nodes, labels by year
  compare.js           trace(), compare() (an item), gcompare() (a heading): states 0-3
  search.js            search(M, query)
  changes.js           events(M): the changes by year, KINDS
  snippets.js          codesSnippet(): the codes to add up, as Python
src/i18n/              the words and numbers, no DOM
  en.js, fa.js         the interface text, one file per language (same keys)
  index.js             the languages by code, for data-lang
  format.js            makeFormat(lang, years): numbers, years, ranges
src/ui/                the views: createX(ctx) factories returning HTML strings
  html.js              esc, code, fat (Persian text), links, the locate buttons
  labels.js            section titles and periods, heading names, a link's pills
  timeline.js          the states' colours, the strip, the verdict, the timeline
  layout.js            the skeleton (tabs, search bar, list, card); the empty card
  tree.js              the list as a tree: folding, sticky headings, the dot's popover
  item-card.js         an item's page
  group-card.js        a heading's page
  changes-view.js      changes by year: the kinds, the table, the list of changes
  pdf-viewer.js        a questionnaire page in a <dialog>, rows highlighted (PDF.js)
src/app/               putting it together
  state.js             the URL scheme: view state <-> location hash (no DOM)
  mount.js             mount(root, M): the context, the events, the routing
  element.js           <hies-explorer>: loads the data once, mounts in each element
src/explorer.js        the entry: defines <hies-explorer>
styles/explorer.css    the entry stylesheet: @imports the partials in cascade order
styles/*.css           tokens (colours, the comparability colours), theme-mkdocs,
                       base, list, card, timeline, history, changes, about,
                       viewer, states, responsive; all scoped under .hx
package.json           "type": "module", so Node and bundlers read src/ as ES modules
```

The ui/ factories share one context, built by `app/mount.js`:

| key | what |
|---|---|
| `M` | the model (`core/model.js`) |
| `t`, `lang`, `fa` | the strings of the language, its code, whether it is Farsi |
| `fmt` | `i18n/format.js` for the language |
| `state` | what is shown: `{ selected, focus, ref, selGroup }` (mutable) |
| `refOf(s)`, `nodeRef(n)` | the year a series or heading is compared with |
| `pdfBase`, `pdfUrl(c, y)` | where the PDFs are; the page of chain `c` in year `y` |
| `filesRoot`, `docs` | where the CSVs and the methods page are |
| `root` | the element |
| `labels`, `timeline` | the shared factories, created first |
| `actions.selectGroup` | for the tree to open a heading's page |

## Embedding it

Load the script and the stylesheet, and put the element where it goes:

```html
<link rel="stylesheet" href="explorer.css">
<hies-explorer data-lang="fa" data-src="data.json" data-pdf="pdf/" data-root="./"></hies-explorer>
<script src="explorer.js"></script>
```

The attributes are listed in [`src/app/element.js`](src/app/element.js). The
element has no shadow DOM, so the page's styles apply: to theme it, set the
variables of [`styles/tokens.css`](styles/tokens.css) on `.hx` (as
`styles/theme-mkdocs.css` does with Material's colours). `element.focusSearch()`
goes back to the items with the cursor in the search box.

The browser built-ins it relies on: custom elements, `<dialog>` (the PDF
viewer) and the Popover API (a heading's timeline; without it, a plain
positioned box is shown).

## Using the core elsewhere

`core/` takes the data and returns plain objects, so a server, a script or
another frontend can use it without the page. For example, in Node:

```js
import { readFileSync } from "node:fs";
import { model } from "./src/core/model.js";
import { search } from "./src/core/search.js";
import { compare } from "./src/core/compare.js";

const M = model(JSON.parse(readFileSync("data.json", "utf8")));
const [[series]] = search(M, "011111");        // [series, rank, chain]
const cmp = compare(M, series, 1403);         // year -> { st, set, via, ... }
cmp.get(1383).st;                             // "ref", 0-3, or null (not asked)
```

`app/state.js` and `i18n/` need no DOM either: a dynamic site can use the
same URL scheme for its routes, and the same strings and number formats.
`tests/test_explorer.py` runs all of these on the real data (when Node is
installed).

## Building

A site with its own build (Vite, Astro, …) can import `src/` and
`styles/explorer.css` as they are. For the site here,
`hiesir_codebook.explorer` bundles them without Node:

- `bundle_js()` follows the imports from `src/explorer.js` and joins the
  modules into one classic script, each in its own scope;
- `bundle_css()` inlines the `@import`s of `styles/explorer.css`.

The bundler reads only `import { a, b as c } from "./x.js";` and
`export function|const|let|class` / `export { … }`, and stops with the file
and line on anything else (a default export, a bare specifier, a bare
`import "./x.js"`), so keep to those forms.

No UI kit, CSS framework or charting library: the views are specific to this
data, and the colours come from `tokens.css`, which each host maps to its own
theme. PDF.js is loaded from its CDN on the first click.
