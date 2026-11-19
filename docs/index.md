# HIESIR Codebook

The expenditure items of the Household Income and Expenditure Survey of Iran (HIES)
questionnaires, 1383–1403, extracted from the PDF forms, corrected, and
matched across years, so that the same item can be followed as its code and
wording change.

[Open the explorer :material-magnify:](explorer.md){ .md-button .md-button--primary }
[Download the data :material-download:](data.md#quick-start){ .md-button }

## What do you want to do?

<div class="grid cards" markdown>

-   :material-magnify: **Look up an item**

    ---

    Search a code (`011114`, or the raw data's `11114`) or Persian text and see
    the years it was asked, its code and label changes, and whether it is
    comparable across years.

    [Explorer](explorer.md)

-   :material-calendar-range: **See what a year changed**

    ---

    New, dropped, recoded, merged and split items for each questionnaire, with
    the big redesigns of 1386, 1390 and 1395 at a glance.

    [Changes by year](explorer.md#year=1386)

-   :material-table: **Use the data**

    ---

    The corrected questionnaires and the matched tables as CSV, the columns,
    and how to join them with the raw data without losing leading zeros.

    [Data files](data.md)

-   :material-microscope: **Check the method**

    ---

    How printing errors were corrected, how items are linked across years,
    and how each link was verified against household counts.

    [Methods](methods.md)

</div>

## At a glance

| | |
|---|---|
| Questionnaires | 21 years: 1382–1400, 1402, 1403 (1401's PDF is a data dictionary; 1363–1381 are scans) |
| Items | about 1,900 chains: one code with one label, followed while both stay the same |
| Links between them | 415 links that continue an item (reworded or recoded) and 141 merges, splits and regroupings; every one verified |
| Corrections | 35 fixes to the printed questionnaires, plus spelling and punctuation across all years |

## How it is made

```
PDFs ─extract─▶ as printed ─correct─▶ as intended ─match─▶ chains, links, relations ─group─▶ groups, members, links ─▶ explorer
                                ▲                     ▲                                 ▲
                      curated/2_corrected/    curated/3_items/                  curated/4_groups/
```

Every deviation from the print, and every matching decision a person made, is
one row in `curated/` with its reason; everything else is generated. See
[Contributing](contributing.md) to rebuild it or propose a fix.
