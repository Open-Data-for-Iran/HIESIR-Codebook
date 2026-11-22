# The explorer

The page that searches and browses the matched questionnaire items across
years. It is website code, kept apart from the Python package, so it can be
reused as is by another site.

It is drawn in two places from the same files:

- the documentation site: `docs/explorer.md` → `overrides/explorer.html`, which
  loads the files that `scripts/mkdocs_hooks.py` publishes under `assets/explorer/`
  and fetches `explorer/data.json`;
- the offline page `output/explorer/index.html`, written by
  `python -m hiesir_codebook.explorer` from `hosts/standalone.html` with the
  scripts, styles and data inlined.

The data (`data.json`, or `window.HX_DATA`) is built by
`hiesir_codebook.explorer.collect()` from `output/`.

## Layout now

```
src/core/             pure JS, no DOM: runs in a browser, Node, a worker or a server
  data.d.ts           the shape of data.json: the contract with the Python build
  text.js             norm() and digits: the search keys
  model.js            model(DATA): series, heading nodes, labels by year
  compare.js          trace(), compare() (an item), gcompare() (a heading): states 0-3
  search.js           search(M, query)
  changes.js          events(M): the changes by year, KINDS
  snippets.js         codesSnippet(): the codes to add up, as Python
src/explorer.js       the component (entry module): views, routing, PDF viewer
src/i18n/en.js, fa.js the interface text, one file per language (same keys)
src/i18n/index.js     the languages by code, for data-lang
styles/explorer.css   the entry stylesheet: @imports the partials in cascade order
styles/*.css          tokens (colours, the comparability colours), theme-mkdocs,
                      base, list, card, timeline, history, changes, about,
                      viewer, states, responsive; all scoped under .hx
hosts/standalone.html the offline page's shell
package.json          "type": "module", so Node and bundlers read src/ as ES modules
```

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

`tests/test_explorer.py` runs this on the real data (when Node is installed).

## Building

Everything is plain ES modules and CSS, with no dependencies. A site with its
own build (Vite, Astro, …) can import `src/` and `styles/explorer.css` as
they are. For the two pages here, `hiesir_codebook.explorer` bundles them
without Node:

- `bundle_js()` follows the imports from `src/explorer.js` and joins the
  modules into one classic script, each in its own scope;
- `bundle_css()` inlines the `@import`s of `styles/explorer.css`.

The bundler reads only `import { a, b as c } from "./x.js";` and
`export function|const|let|class` / `export { … }`, and stops with the file
and line on anything else (a default export, a bare specifier), so keep to
those forms.

    uv run python -m hiesir_codebook.explorer   # writes output/explorer/index.html

## Where it is going

The component is being split into layers, each importing only from the ones
above it:

```
src/core/     pure JS, no DOM (done, above)
src/i18n/     en.js, fa.js, format.js (numbers, years, ranges per language)
src/ui/       render functions, (ctx, …) → HTML: html, timeline, tree,
              item-card, group-card, changes-view, pdf-viewer
src/app/      state.js (view state ↔ URL hash), mount.js, boot.js,
              element.js (the <hies-explorer> custom element)
styles/       the partials above (done)
hosts/        standalone.html and its header script
```

Steps:

1. ~~Move the files here from `src/hiesir_codebook/data/explorer/`.~~
2. ~~The bundler; `strings.js` split into `i18n/en.js` and `fa.js`; the CSS into partials.~~
3. ~~`core/` taken out of `explorer.js` (already pure functions).~~
4. `mount()` split into `ui/` and `app/`, sharing an explicit `ctx`
   (`{ M, t, fmt, pdfUrl, state }`), with three browser built-ins in place of
   hand-written code:
   - a custom element, `<hies-explorer data-lang data-src data-pdf …>`, in place
     of the `.hx` lookup, so any page or framework can embed it;
   - `<dialog>` for the PDF viewer (focus, Esc, backdrop);
   - the Popover API for a heading's timeline on hover in the tree.
5. This README: the layers, the data contract, how to embed it.

No UI kit, CSS framework or charting library: the views are specific to this
data, and the colours come from `tokens.css`, which each host maps to its own
theme. PDF.js is loaded from the CDN on the first click.
