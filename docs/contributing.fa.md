# مشارکت

نیازمند Python 3.11 یا بالاتر و [uv](https://docs.astral.sh/uv/).

## مراحل کار {#the-pipeline}

<!-- diagram: pipeline -->

`output/1_extracted/` هر PDF را دقیقاً، حتی با غلط‌های تایپی‌اش، بازتولید می‌کند
تا معلوم شود با تغییر استخراج‌گر یا جایگزینی یک PDF چه چیزی عوض می‌شود. هر
انحراف از متن چاپی یک سطر در `curated/` است که برای ساختن `output/2_corrected/`
(با همان ستون‌ها) اعمال می‌شود. `output/` در git نگه داشته می‌شود تا هر تغییر به
صورت تفاوت (diff) دیده شود، و وقتی مرحله‌ای به‌روز نباشد آزمون‌ها شکست می‌خورند؛
GitHub این فایل‌ها را در نمایش تفاوت‌ها جمع می‌کند (`.gitattributes`).

```bash
uv run hiesir-codebook --help                # every command, each with its own --help
uv run hiesir-codebook build                 # regenerate every stage of output/
uv run hiesir-codebook build --no-extract    # keep 1_extracted/ (no PDFs needed)
uv run hiesir-codebook pdfs download         # the PDFs from the release, checked against data/pdfs.csv
uv run hiesir-codebook hazm download         # hazm's word list and data files -> data/hazm/, checked
uv run hiesir-codebook extract               # just extract: PDFs -> output/1_extracted/ (reports in reports/)
uv run hiesir-codebook extract 1383 1403     # or just some years
uv run hiesir-codebook correct --check       # correct and check against the raw data
uv run hiesir-codebook check-structure       # check the corrected CSVs from the CSVs alone
```

## اصلاح داده‌ها {#fixing-the-data}

هرگز `output/` را ویرایش نکنید. هر تغییری در `curated/` می‌رود، هر تصمیم در یک
سطر و همراه با دلیلش:

| فایل | چه چیزی را اصلاح می‌کند | اعمال توسط |
|---|---|---|
| `2_corrected/corrections.csv` | تک‌قلم‌ها و سرگروه‌ها در یک سال: کد نادرست، متن نادرست، بخش جاافتاده | `correct` |
| `2_corrected/spelling.csv` | غلط‌های املایی‌ای که هیچ قاعده‌ای حل نمی‌کند: غلط تایپی، واژه‌های بریده، واژه‌های چسبیده، متنی که خواندن PDF خراب کرده | `correct` |
| `2_corrected/words.csv` | واژه‌های درستی که در فهرست hazm نیستند، تا اصلاح خودکار به آن‌ها دست نزند | `autocorrect` |
| `2_corrected/header_exceptions.csv` | اقلامی که زیر سرگروهی چاپ شده‌اند که کدش آن‌ها را در بر نمی‌گیرد، پذیرفته همان‌طور که چاپ شده‌اند (فقط بررسی، چیزی را تغییر نمی‌دهد) | `check-structure` |
| `3_items/links.csv` | تصمیم درباره پیوند یک‌به‌یک میان زنجیره‌ها (`from_chain` ← `to_chain`، همان قلم یا تغییر کد): تأیید، رد، تغییر، افزودن | `relations` |
| `3_items/relations.csv` | تصمیم درباره ادغام، تفکیک و بازگروه‌بندی میان مجموعه زنجیره‌ها (`from_chains` ← `to_chains`): تأیید، رد، تغییر، افزودن | `relations` |
| `4_groups/links.csv` | تصمیم درباره پیوند میان سرگروه‌ها (`from_group` ← `to_group`: ادامه، تفکیک، ادغام، بازگروه‌بندی، جابه‌جایی): تأیید، رد، تغییر، افزودن | `groups` |

ستون‌های هر فایل در [روش کار](methods.md) آمده‌اند: [اصلاحات](methods.md#corrections)
و [تصمیم‌های پیوند](methods.md#matching-items-across-years). پس از ویرایش،
`uv run hiesir-codebook build --no-extract` را اجرا کنید و تفاوت‌ها را در
`output/` بازبینی کنید.

## آزمون‌ها {#tests}

```bash
uv run pytest                 # unit tests + regression against output/1_extracted/ (needs data/pdf/)
uv run pytest -m "not slow"   # unit tests only
uv run ruff check . && uv run ruff format --check .
```

آزمون‌های رگرسیون همه سال‌ها را دوباره استخراج و بایت‌به‌بایت با
`output/1_extracted/` مقایسه می‌کنند. وقتی تغییری در استخراج‌گر عمدی است، با
`uv run hiesir-codebook extract` دوباره بسازید و پیش از commit تفاوت‌های CSV را
بازبینی کنید. آزمون‌های سریع هم بررسی می‌کنند که `output/2_corrected/`،
`output/3_items/` و `output/4_groups/` به‌روز باشند؛ پس از تغییر `curated/` یا
کد، `uv run hiesir-codebook build --no-extract` را اجرا و تفاوت‌ها را بازبینی
کنید. آزمون‌هایی که به PDFها نیاز دارند، وقتی `data/pdf/` نباشد رد می‌شوند؛ در
GitHub گردش‌کار آن‌ها را از انتشار دانلود می‌کند و جدول‌های تعداد خانوار در git
هستند، پس همه آزمون‌ها آنجا اجرا می‌شوند. `hiesir-codebook check-structure`
ساختار CSVهای اصلاح‌شده را فقط از خود CSVها بررسی می‌کند (کد تکراری، ترتیب
زیرکد و بخش، شرح خالی، قلم بیرون از سرگروهش؛ یک آزمون هم آن را اجرا می‌کند).

## مستندات {#documentation}

این سایت با [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) از
`docs/` و `mkdocs.yml` ساخته می‌شود. فایل‌های CSV هنگام ساخت از `output/` افزوده
می‌شوند و داده‌های جست‌وجوی اقلام (`explorer/data.json`) همان‌جا از آن‌ها ساخته
می‌شود (`scripts/mkdocs_hooks.py`)، پس هیچ‌کدام در git تکرار نمی‌شوند.

جست‌وجوی اقلام یک جزء واحد در `web/explorer/` است، جدا از کد پایتون (اجزای آن
در `README.md` همان پوشه آمده است): عنصر `<hies-explorer>`، نوشته‌شده به
صورت ماژول‌های ES در `src/` (منطق داده در `src/core/`، متن‌های رابط در
`src/i18n/`، انگلیسی و فارسی، نماها در `src/ui/`) و سبک‌ها در `styles/`. ساخت پروژه، بدون Node،
آن‌ها را در یک اسکریپت و یک فایل سبک بسته‌بندی می‌کند. صفحه
`docs/explorer.md` (و `explorer.fa.md`) آن‌ها را از طریق `overrides/explorer.html`
درون سایت بار می‌کند و رنگ، قلم و حالت تیره سایت را می‌گیرد.

نمودارها را `scripts/diagrams.py` به صورت SVG درون صفحه می‌کشد، برای هر نمودار یک
تابع، با قاعده‌های ویرایشی [diagram-design](https://github.com/cathrynlavery/diagram-design):
هر گره یک مفهوم جدا، اتصال‌ها با زاویه قائم، برچسب‌ها روی زمینه‌ای جدا از خط خود، و
دست‌بالا یک جزء به رنگ تأکید. صفحه با نشانه `<!-- diagram: name -->` در سطری جدا
جای نمودار را تعیین می‌کند؛ صفحه فارسی همان چیدمان را قرینه و با متن خودش می‌گیرد.
رنگ‌ها و قلم‌ها از کلاس‌هایی می‌آیند که `docs/assets/extra.css` با رنگ‌های پوسته سایت
تعریف می‌کند، پس نمودار حالت روشن یا تیره سایت را می‌گیرد. نام ناشناخته ساخت سایت را متوقف می‌کند.

هیچ عددی دستی در صفحه نوشته نمی‌شود: نام یکی از اعداد `output/metrics.json` را
میان دو آکولاد دوتایی بنویسید، مثلاً `links.confirmed`، تا ساخت سایت عدد را
(در صفحه‌های فارسی با رقم‌های فارسی) جایش بگذارد. هر ساخت این فایل را از نو
می‌نویسد، پس تفاوت آن نشان می‌دهد هر تغییر چه کرد؛ نام ناشناخته ساخت سایت را
متوقف می‌کند و یک آزمون را شکست می‌دهد.

هر صفحه دو نسخه دارد: `page.md` (انگلیسی) و `page.fa.md` (فارسی، در نشانی
`/fa/`). اگر نسخه فارسی صفحه‌ای نباشد، نسخه انگلیسی نشان داده می‌شود. وقتی یک
صفحه را تغییر می‌دهید، نسخه دیگرش را هم به‌روز کنید؛ عنوان‌ها شناسه ثابت انگلیسی
دارند (`## اصلاحات {#corrections}`) تا پیوندها در هر دو زبان کار کنند.

```bash
uv run --group docs mkdocs serve      # preview at http://127.0.0.1:8000, reloads on save
uv run --group docs mkdocs build --strict   # what GitHub runs: fails on broken links
```

هر push به `main` آزمون‌ها را اجرا و سایت را در GitHub Pages منتشر می‌کند
(`.github/workflows/pages.yml`).

## فایل‌های PDF پرسشنامه {#questionnaire-pdfs}

فایل‌های PDF در git نیستند: به انتشار
[`questionnaires`](https://github.com/Open-Data-for-Iran/HIESIR-Codebook/releases/tag/questionnaires)
در GitHub پیوست شده‌اند و هر بار ساخت سایت آن‌ها را دریافت و در `pdf/` منتشر
می‌کند؛ در صفحه [پرسشنامه‌ها](questionnaires.md) فهرست شده‌اند و هر قلم در جست‌وجوی
اقلام به آن‌ها پیوند دارد. `data/pdfs.csv` (در git) هر فایل را با حجم و
SHA-256 آن فهرست می‌کند؛ `hiesir-codebook pdfs download` آن‌ها را با نام‌های
انتشار (`questionnaire_<year>[_urban|_rural].pdf`) در `data/pdf/` دانلود و هر یک را
با فهرست مقایسه می‌کند، و `pdfs verify` نسخه‌ای را که دارید بررسی می‌کند. گردش‌کار
سایت هم همین‌طور دانلود می‌کند. برای افزودن یا جایگزینی یک فایل:

```bash
cp <file> data/pdf/questionnaire_1404.pdf                               # the release name
uv run hiesir-codebook pdfs manifest                                    # data/pdfs.csv from data/pdf/
gh release upload questionnaires data/pdf/questionnaire_1404.pdf --clobber
```

سپس `data/pdfs.csv` را commit کنید. ساخت محلی سایت از `data/pdf/` یا پوشه
`$HIESIR_PDF_DIR` استفاده می‌کند. نسخه‌ای با نام‌های قدیمی (`Questionnaire 1386.pdf`)
با `hiesir-codebook pdfs rename` تغییر نام می‌یابد.

### فهرست واژه‌های hazm {#hazm-word-list}

[hazm](https://github.com/roshan-research/hazm) (مجوز MIT) فهرستی از واژه‌های
فارسی با بسامدشان در پیکره و نقش دستوری‌شان، بن‌های فعل، واژه‌های پرکاربرد و
کوته‌نوشت‌ها را به‌صورت فایل متنی ساده دارد. `hiesir-codebook hazm download` آن‌ها را از
مخزن hazm در نسخه‌ای ثابت (v0.12.1) در `data/hazm/` (بیرون از git) دانلود و هر یک را
با حجم و SHA-256 فهرست‌شده در `hazm_data.py` مقایسه می‌کند؛ `hazm verify` نسخه
موجود را بررسی می‌کند و `hazm list` نشان می‌دهد هر فایل چه دارد.
`hazm_data.words()`، `verbs()` و `stopwords()` آن‌ها را به‌صورت جدول polars
می‌خوانند، پس به خود hazm (که پایتون ۳.۱۲ یا ۳.۱۳ می‌خواهد) نیازی نیست.
واژه‌نامه اصلاح (`correction/lexicon.py`) از آن‌ها ساخته می‌شود.

## مجوز {#license}

MIT؛ فایل `LICENSE` را در مخزن ببینید.
