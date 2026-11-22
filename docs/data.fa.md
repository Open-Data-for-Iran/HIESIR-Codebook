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
links = pd.read_csv("output/3_items/links.csv")
relations = pd.read_csv("output/3_items/relations.csv")
relations = relations[relations.verified != "rejected"]

# join with the raw data, which stores codes as numbers
items = items.assign(Commodity_Code=items.expenditure_code.astype(int))
```

همین فایل‌ها را می‌توانید از این سایت دریافت کنید:
[2_corrected/questionnaire_1403.csv](2_corrected/questionnaire_1403.csv) (هر سال دیگری را به جای ۱۴۰۳ بگذارید)،
[3_items/chains.csv](3_items/chains.csv)، [3_items/links.csv](3_items/links.csv)، [3_items/relations.csv](3_items/relations.csv)،
[4_groups/groups.csv](4_groups/groups.csv)، [4_groups/members.csv](4_groups/members.csv) و [4_groups/links.csv](4_groups/links.csv).

| فایل | هر سطر یعنی | جزئیات |
|---|---|---|
| `2_corrected/questionnaire_<year>.csv` | یک بخش، سرگروه یا قلمِ پرسشنامه آن سال | [ستون‌ها](#csv-columns) |
| `2_corrected/autocorrect/hazm.csv` | واژه‌ای که با فهرست واژه‌های hazm به‌طور خودکار اصلاح شده، با قاعده و شاهد آن | [اصلاحات](methods.md#corrections) |
| `3_items/chains.csv` | یک قلم (زنجیره): یک کد با یک عبارت، تا زمانی که هر دو ثابت بمانند | [مرحله ۱](methods.md#matching-items-across-years) |
| `3_items/links.csv` | یک پیوند یک‌به‌یک که قلمی را ادامه می‌دهد: همان قلم، تغییر کد | [مرحله ۲](methods.md#matching-items-across-years) |
| `3_items/relations.csv` | یک رابطه میان مجموعه‌ای از اقلام: ادغام، تفکیک، بازگروه‌بندی | [مرحله ۲](methods.md#matching-items-across-years) |
| `4_groups/groups.csv` | یک سرگروه: یک کد چاپی، تا زمانی که چاپ می‌شود | [سرگروه‌ها](methods.md#groups-across-years) |
| `4_groups/members.csv` | یک قلم در یک سال: گروه آن در سطح ۲، ۳ و ۴ | [سرگروه‌ها](methods.md#groups-across-years) |
| `4_groups/links.csv` | دو گروهی که اقلامی میانشان جابه‌جا شده: ادامه، تفکیک، ادغام، بازگروه‌بندی، جابه‌جایی | [سرگروه‌ها](methods.md#groups-across-years) |

## پوشه‌ها {#folders}

| پوشه | محتوا | در git | ویرایش توسط |
|---|---|---|---|
| `data/` | ورودی‌های بیرونی: فایل‌های PDF و جدول‌های تعداد خانوارهای گزارش‌دهنده هر کد | جدول‌های تعداد خانوار و `pdfs.csv` (PDFها در یک انتشار GitHub‌اند) | هیچ‌کس (فقط جایگزین می‌شود) |
| `curated/` | تصمیم‌های دستی: `2_corrected/` (`corrections.csv`: اصلاح اقلام و سرگروه‌ها؛ `spelling.csv`)، `3_items/` (`links.csv`، `relations.csv`) و `4_groups/` (`links.csv`): تصمیم‌های پوشه هم‌نام در `output/` | بله | افراد |
| `output/` | خروجی همه مراحل: `1_extracted/`، `2_corrected/`، `3_items/`، `4_groups/`، صفحه `explorer/` و `metrics.json` (اعداد ساخت، که همین صفحه‌ها نقل می‌کنند) | بله | فقط برنامه |
| `reports/` | کمک‌های بازبینی: `relation_evidence.csv` (تعداد خانوارهای پشت هر پیوند و رابطه) و `code_reuse.csv` (کدهایی که برای قلم دیگری به کار رفته‌اند) | خیر | فقط برنامه |

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
| ۱۳۹۰ تا ۱۴۰۰، ۱۴۰۲، ۱۴۰۳ | ۰ | ۱۳۹۵، ۱۳۹۶، ۱۳۹۹ و ۱۴۰۲ از ترمیم قلم (فونت) عبور می‌کنند |
| ۱۴۰۱ | — | فایل PDF راهنمای داده است، نه پرسشنامه |
| ۱۳۶۳ تا ۱۳۸۱ | — | فقط تصویر اسکن‌شده؛ نیاز به OCR دارد |

در زمان توسعه، خروجی‌ها با کاربرگ‌های دستی قبلی هم مقایسه شدند: کد اقلام یکسان
بود و ۹۶ تا ۹۹ درصد شرح‌ها برای ۱۳۹۰ تا ۱۴۰۳ یکسان بود. باقی تفاوت‌ها ویرایش‌های
دستی بودند (اصلاح غلط تایپی، رقم فارسی، عبارت‌های بعدی)، نه خطای استخراج.

## فایل‌های ورودی {#input-files}

فایل‌های PDF در git نیستند (`.gitignore` را ببینید؛ انتشار `questionnaires` آن‌ها را نگه می‌دارد،
`data/pdfs.csv` آن‌ها را با حجم و SHA-256 فهرست می‌کند و `hiesir-codebook pdfs download`
آن‌ها را دانلود و بررسی می‌کند) و دو جدول تعداد خانوار در git هستند. همه انتظار می‌رود در `data/` باشند:

```
data/
  pdf/questionnaire_<year>[_urban|_rural].pdf
  pdfs.csv
  commodity_code_occurrence_1363-1382.csv
  commodity_code_occurrence_1383-1403.csv
```

با `--data <folder>` می‌توانید پوشه دیگری را به برنامه معرفی کنید.
