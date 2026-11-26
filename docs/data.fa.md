# فایل‌های داده

هر فایل کجاست، هر ستون چه معنایی دارد، و چگونه فایل‌ها را بدون از دست دادن صفر ابتدای کدها بخوانید.

!!! tip "فقط دنبال یک قلم هستید؟"
    [جست‌وجوی اقلام](explorer.md) بیشتر پرسش‌ها را بدون باز کردن هیچ CSV پاسخ می‌دهد.

## شروع سریع {#quick-start}

```python
import pandas as pd

TEXT = {"code": str, "sub": str, "expenditure_code": str}
q = pd.read_csv("output/2_corrected/questionnaire_1403.csv", dtype=TEXT)
items = q[q.kind == "item"]

chains = pd.read_csv("output/3_items/chains.csv", dtype={"expenditure_code": str})
changes = pd.read_csv("output/3_items/changes.csv")  # same, recoded, merged, split, regrouped
series = pd.read_csv("output/3_items/series.csv", dtype={"codes": str})  # chains that continuing changes join

# or the results: one table per thing, with English labels
crosswalk = pd.read_csv("output/5_results/items.csv", dtype={"expenditure_code": str, "code": str, "sub": str})

# join with the raw data, which stores codes as numbers
items = items.assign(Commodity_Code=items.expenditure_code.astype(int))
```

همین فایل‌ها را می‌توانید از این سایت دریافت کنید:
[2_corrected/questionnaire_1403.csv](2_corrected/questionnaire_1403.csv) (هر سال دیگری را به جای ۱۴۰۳ بگذارید)،
[3_items/chains.csv](3_items/chains.csv)، [3_items/changes.csv](3_items/changes.csv)، [3_items/series.csv](3_items/series.csv)،
[4_groups/groups.csv](4_groups/groups.csv)، [4_groups/members.csv](4_groups/members.csv) [4_groups/changes.csv](4_groups/changes.csv)، و نتیجه‌ها: [5_results/items.csv](5_results/items.csv)، [5_results/chains.csv](5_results/chains.csv)، [5_results/series.csv](5_results/series.csv)، [5_results/groups.csv](5_results/groups.csv)، [5_results/changes.csv](5_results/changes.csv)، [5_results/change_chains.csv](5_results/change_chains.csv) و [5_results/group_changes.csv](5_results/group_changes.csv).

| فایل | هر سطر یعنی | جزئیات |
|---|---|---|
| `2_corrected/questionnaire_<year>.csv` | یک بخش، سرگروه یا قلمِ پرسشنامه آن سال | [ستون‌ها](#csv-columns) |
| `2_corrected/autocorrect/canonical.csv` | عبارتی که به چند شکل چاپ شده، با نوشتاری که گروهش می‌گیرد و دلیل آن | [اصلاحات](methods.md#corrections) |
| `2_corrected/autocorrect/words.csv` | واژه‌ای که به‌طور خودکار اصلاح شده: آموخته از گروه‌های عبارت‌ها، یکی‌شده (ی، ک، همزه)، یک شکل برای واژه‌ای که یک قلم به دو شکل چاپ کرده، یا یافته با فهرست واژه‌های hazm، با نوع، شمار کاربرد و شاهد آن | [اصلاحات](methods.md#corrections) |
| `3_items/chains.csv` | یک قلم (زنجیره): یک کد با یک عبارت، تا زمانی که هر دو ثابت بمانند | [مرحله ۱](methods.md#matching-items-across-years) |
| `3_items/changes.csv` | یک تغییر میان زنجیره‌ها: تغییری پیوسته که قلمی را ادامه می‌دهد (همان قلم، تغییر کد، ۱ ← ۱)، یا ادغام، تفکیک یا بازگروه‌بندی میان مجموعه‌هایی از زنجیره‌ها | [مرحله ۲](methods.md#matching-items-across-years) |
| `3_items/series.csv` | یک سری: زنجیره‌هایی که تغییرهای پیوسته به هم وصل می‌کنند، یک کالا یا خدمت که تا ادغام، تفکیک یا بازگروه‌بندی دنبال می‌شود | [مرحله ۳](methods.md#matching-items-across-years) |
| `3_items/suggested/changes.csv` | تغییری که برنامه پیدا کرده، همان‌گونه که پیدا کرده، با این‌که چه کسی و چگونه درباره‌اش تصمیم گرفته؛ ردشده‌ها و تصمیم‌نگرفته‌ها فقط این‌جا هستند | [مرحله ۲](methods.md#matching-items-across-years) |
| `4_groups/groups.csv` | یک سرگروه: یک کد چاپی، تا زمانی که چاپ می‌شود | [سرگروه‌ها](methods.md#groups-across-years) |
| `4_groups/members.csv` | یک قلم در یک سال: گروه آن در سطح ۲، ۳ و ۴ | [سرگروه‌ها](methods.md#groups-across-years) |
| `4_groups/changes.csv` | دو گروهی که اقلامی میانشان جابه‌جا شده: ادامه، تفکیک، ادغام، بازگروه‌بندی، جابه‌جایی | [سرگروه‌ها](methods.md#groups-across-years) |
| `4_groups/suggested/changes.csv` | تغییر گروهی که برنامه پیدا کرده، همان‌گونه که پیدا کرده، با این‌که چه کسی و چگونه درباره‌اش تصمیم گرفته | [سرگروه‌ها](methods.md#groups-across-years) |
| `5_results/items.csv` | یک قلم در یک سال: عبارت فارسی و انگلیسی، زنجیره، سری، گروه در سطح ۲، ۳ و ۴، و جای چاپ آن: جدول پیوند با داده‌های خانوار | [نتیجه‌ها](#results) |
| `5_results/chains.csv`، `series.csv`، `groups.csv` | یک زنجیره، سری یا گروه، با `label_fa` و `label_en` (برچسب سری همان برچسب آخرین زنجیره آن است) | [نتیجه‌ها](#results) |
| `5_results/changes.csv`، `group_changes.csv` | یک تغییر میان زنجیره‌ها یا میان گروه‌ها، مانند `3_items/` و `4_groups/`، با ستون‌های متنی `from_label_fa` / `to_label_fa` | [نتیجه‌ها](#results) |
| `5_results/change_chains.csv` | زنجیره‌ای در یک سوی یک تغییر: `from_chains` / `to_chains` به شکل بلند | [نتیجه‌ها](#results) |

فایل‌های `changes.csv` بیرون از `suggested/` نتیجه‌اند: درباره هر سطرشان، برنامه یا `curated/`
تصمیم گرفته و هیچ‌کدام رد نشده. پیشنهادهای برنامه پیش از هر تصمیم در `suggested/`
هستند، با همان شناسه‌ها.

## نتیجه‌ها {#results}

`output/5_results/` آنچه کاربر دفترچه کد لازم دارد را در یک پوشه تخت جمع
می‌کند، بی‌آن‌که لازم باشد مرحله‌ها را بشناسد. در آن هیچ تصمیم تازه‌ای گرفته
نمی‌شود: `2_corrected/`، `3_items/` و `4_groups/` را با برچسب‌های انگلیسی
پیوند می‌دهد که دستی نگه داشته می‌شوند: `curated/3_items/labels_en.csv` (یکی
برای هر زنجیره) و `curated/4_groups/labels_en.csv` (یکی برای هر گروه). هر
ستون متنی `label_fa` یا `label_en` است.

برچسب‌های انگلیسی هرجا که با فارسی جور باشند واژه‌هایشان را از عنوان‌های
انگلیسی COICOP گرفته‌اند؛ طبقه‌بندی COICOP نیستند. واژه‌ای که نام انگلیسی
درستی ندارد با حروف انگلیسی نوشته می‌شود (`Charghad`، `Kalbas`). در هر فایل
برچسب، ستون `note` می‌گوید چه بررسی شده و ستون `source` کجا.

ساخت بررسی می‌کند که هر قلم یک زنجیره، یک سری و یک گروه داشته باشد، و هر
زنجیره و گروه برچسب انگلیسی داشته باشد و هیچ برچسبی به زنجیره یا گروهی که
دیگر نیست اشاره نکند.

## پوشه‌ها {#folders}

| پوشه | محتوا | در git | ویرایش توسط |
|---|---|---|---|
| `data/` | ورودی‌های بیرونی: فایل‌های PDF و جدول تعداد خانوارهای گزارش‌دهنده هر کد | جدول تعداد خانوار و `pdfs.csv` (PDFها در یک انتشار GitHub‌اند) | هیچ‌کس (فقط جایگزین می‌شود) |
| `curated/` | تصمیم‌های دستی: `2_corrected/` (`corrections.csv`: اصلاح اقلام و سرگروه‌ها؛ `spelling.csv`؛ `words.csv`: واژه‌هایی که hazm ندارد؛ `header_exceptions.csv`)، `3_items/` (`changes.csv`؛ `labels_en.csv`: برچسب انگلیسی زنجیره‌ها)، `4_groups/` (`changes.csv`؛ `labels_en.csv`: برچسب انگلیسی گروه‌ها): تصمیم‌های پوشه هم‌نام در `output/`؛ `data/` (`code_corrections.csv`): کدهای اشتباه داده خام، برای بعد | بله | افراد |
| `output/` | خروجی همه مراحل: `1_extracted/`، `2_corrected/`، `3_items/`، `4_groups/`، `5_results/` و `metrics.json` (اعداد ساخت، که همین صفحه‌ها نقل می‌کنند) | بله | فقط برنامه |
| `reports/` | کمک‌های بازبینی: `change_evidence.csv` (تعداد خانوارهای پشت هر تغییر) و `code_reuse.csv` (کدهایی که برای قلم دیگری به کار رفته‌اند) | خیر | فقط برنامه |

## ستون‌های CSV {#csv-columns}

| ستون | معنی |
|---|---|
| `section` | شماره بخش |
| `kind` | `section` (بخش)، `header` (سطر سرگروه) یا `item` (قلم) |
| `level` | ۲ تا ۴ برای سرگروه‌ها، ۵ برای اقلام |
| `code` | کد به شکل چاپی، یکسان‌سازی‌شده: `0111`، `091 A`، `01111, 01112` |
| `sub` | کد فرعی دورقمی قلم |
| `expenditure_code` | کد کامل قلم: رقم‌های `code` و سپس `sub` (`0111` + `11` ← `011111`)؛ برای بخش‌ها و سرگروه‌ها خالی |
| `description` | شرح قلم، یا عنوان کامل بخش در سطرهای بخش |
| `page` | شماره صفحه PDF (از ۱) |
| `top`، `bottom`، `left`، `right` | سطر جدولی که قلم در آن چاپ شده، در همان صفحه، بر حسب پوینت (۱/۷۲ اینچ) از گوشه بالا و چپ صفحه: میان خطوط آن سطر و تا مرزهای بیرونی جدول (جایی که سطر خط ندارد، محدوده سطر کد و سطرهای شکسته شرح)؛ برای سطرهایی که در PDF چاپ نشده‌اند (مثلاً بخشی که از سال دیگر کپی شده) خالی است. جست‌وجوی اقلام با آن‌ها سطر را روی فرم چاپی برجسته می‌کند |

«کد هزینه» هم کالا و هم خدمات را در بر می‌گیرد (اجاره، شهریه، بیمه، انتقالات)،
مطابق ستون «شرح هزینه» پرسشنامه. این همان کدی است که در داده‌های خام
`Commodity_Code` نام دارد.

کدها متن هستند و صفر ابتدایی‌شان حفظ می‌شود (`011111`): گروه‌های اصلی ۰۱ تا ۰۹
طبقه‌بندی COICOP با صفر شروع می‌شوند و این صفر بخشی از کد است. داده‌های خام
کدها را به صورت عدد ذخیره می‌کنند (`11111`)، پس اتصال را با
`int(expenditure_code)` انجام دهید. در pandas با
`dtype={"code": str, "sub": str, "expenditure_code": str}` بخوانید. اگر CSV را
مستقیم در Excel باز کنید صفرها روی صفحه حذف می‌شوند؛ از مسیر
Data → From Text/CSV استفاده کنید و نوع این ستون‌ها را Text بگذارید.

فایل‌ها UTF-8 همراه با BOM هستند تا Excel متن فارسی را درست نشان دهد، و پایان
سطرشان LF است (با `.gitattributes`) تا تفاوت‌ها در هر سیستم‌عاملی تمیز دیده شوند.

## پوشش {#coverage}

«کدهای جاافتاده داده خام» یعنی کدهایی که در داده‌های خام آن سال هستند ولی در
پرسشنامه نیستند، پیش از اصلاحات ← پس از اصلاحات.

| سال‌ها | کدهای جاافتاده داده خام | توضیح |
|---|---|---|
| ۱۳۸۳ | ۷ ← ۱ | صفحه بخش ۲ در PDF خالی است؛ تنها کد باقی‌مانده، `231`، کد قلم نیست |
| ۱۳۸۴ | ۱ ← ۰ | |
| ۱۳۸۵ | ۰ | |
| ۱۳۸۶ | ۹ ← ۰ | غلط‌های تایپی کد در صفحه ۲۷ و جاهای دیگر |
| ۱۳۸۷ تا ۱۳۸۹ | ۰، ۵، ۱ | کدهای باقی‌مانده را هر کدام فقط ۱ یا ۲ خانوار گزارش کرده‌اند |
| ۱۳۹۰ تا ۱۴۰۳ | ۰ | ۱۳۹۵، ۱۳۹۶، ۱۳۹۹ و ۱۴۰۲ از ترمیم قلم (فونت) عبور می‌کنند |
| ۱۳۶۳ تا ۱۳۸۱ | — | فقط تصویر اسکن‌شده؛ نیاز به OCR دارد |

در زمان توسعه، خروجی‌ها با کاربرگ‌های دستی قبلی هم مقایسه شدند: کد اقلام یکسان
بود و ۹۶ تا ۹۹ درصد شرح‌ها برای ۱۳۹۰ تا ۱۴۰۳ یکسان بود. باقی تفاوت‌ها ویرایش‌های
دستی بودند (اصلاح غلط تایپی، رقم فارسی، عبارت‌های بعدی)، نه خطای استخراج.

## فایل‌های ورودی {#input-files}

فایل‌های PDF در git نیستند (`.gitignore` را ببینید؛ انتشار `questionnaires` آن‌ها را نگه می‌دارد،
`data/pdfs.csv` آن‌ها را با حجم و SHA-256 فهرست می‌کند و `hiesir-codebook pdfs download`
آن‌ها را دانلود و بررسی می‌کند) و جدول تعداد خانوار در git است. همه انتظار می‌رود در `data/` باشند:

```
data/
  pdf/questionnaire_<year>[_urban|_rural].pdf
  pdfs.csv
  code_usage.csv
```

جدول تعداد خانوار در قالب بلند است، یک سطر برای هر سال و کد (۱۳۶۳ تا ۱۴۰۳):
`year`، `expenditure_code` (عدد، همان‌طور که داده‌های خام ذخیره می‌کنند: `11111`)،
`occurrence` (تعداد خانوارهایی که آن را گزارش کرده‌اند) و `expenditure_share` (درصد آن از
هزینه‌های آن سال؛ ممکن است خالی باشد).

با `--data <folder>` می‌توانید پوشه دیگری را به برنامه معرفی کنید.
