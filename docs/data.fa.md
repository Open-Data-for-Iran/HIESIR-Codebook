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

chains = pd.read_csv("output/3_matched/chains.csv", dtype={"expenditure_code": str})
links = pd.read_csv("output/3_matched/links.csv")
relations = pd.read_csv("output/3_matched/relations.csv")
relations = relations[relations.verified != "rejected"]

# join with the raw data, which stores codes as numbers
items = items.assign(Commodity_Code=items.expenditure_code.astype(int))
```

همین فایل‌ها را می‌توانید از این سایت دریافت کنید:
[2_corrected/questionnaire_1403.csv](2_corrected/questionnaire_1403.csv) (هر سال دیگری را به جای ۱۴۰۳ بگذارید)،
[3_matched/chains.csv](3_matched/chains.csv)، [3_matched/links.csv](3_matched/links.csv) و [3_matched/relations.csv](3_matched/relations.csv).

| فایل | هر سطر یعنی | جزئیات |
|---|---|---|
| `2_corrected/questionnaire_<year>.csv` | یک بخش، سرگروه یا قلمِ پرسشنامه آن سال | [ستون‌ها](#csv-columns) |
| `3_matched/chains.csv` | یک قلم (زنجیره): یک کد با یک عبارت، تا زمانی که هر دو ثابت بمانند | [مرحله ۱](methods.md#matching-items-across-years) |
| `3_matched/links.csv` | یک پیوند یک‌به‌یک که قلمی را ادامه می‌دهد: همان قلم، تغییر کد | [مرحله ۲](methods.md#matching-items-across-years) |
| `3_matched/relations.csv` | یک رابطه میان مجموعه‌ای از اقلام: ادغام، تفکیک، بازگروه‌بندی | [مرحله ۲](methods.md#matching-items-across-years) |
| `3_matched/series.csv`، `codes.csv`، `history.csv`، `review.csv` | سری‌های تطبیق‌دهنده قدیمی تک‌مرحله‌ای | [روش کار](methods.md#matching-items-across-years) |

## پوشه‌ها {#folders}

| پوشه | محتوا | در git | ویرایش توسط |
|---|---|---|---|
| `data/` | ورودی‌های بیرونی: فایل‌های PDF و جدول‌های تعداد خانوارهای گزارش‌دهنده هر کد | خیر | هیچ‌کس (فقط جایگزین می‌شود) |
| `curated/` | تصمیم‌های دستی: `source.csv` (اصلاح اقلام)، `labels.csv` (اصلاح املا)، `links.csv` و `relations.csv` (تصمیم‌های پیوند) | بله | افراد |
| `output/` | خروجی همه مراحل: `1_extracted/`، `2_corrected/`، `3_matched/` و صفحه `explorer/` | بله | فقط برنامه |
| `reports/` | کمک‌های بازبینی، مانند `hazm_suggestions.csv` | خیر | فقط برنامه |

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
| ۱۳۸۲ | ۰ | نظام کدگذاری قدیمی ۳+۲ رقمی |
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

ورودی‌ها در git نیستند (`.gitignore` را ببینید) و انتظار می‌رود در `data/` باشند:

```
data/
  pdf/Questionnaire <year>.pdf
  commodity_code_occurrence_1363-1382.csv
  commodity_code_occurrence_1383-1403.csv
```

با `--data <folder>` می‌توانید پوشه دیگری را به برنامه معرفی کنید.
