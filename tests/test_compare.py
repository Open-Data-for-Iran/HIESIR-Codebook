import pytest

from hbsir_questionnaire.compare import compare, relate, split_qualifier


@pytest.mark.parametrize(
    ("old", "new", "kind"),
    [
        ("برنج صدری ، دمسیاه واستخوانی", "برنج صدری، دم‌سیاه و استخوانی", "same"),
        ("گوسفند، بره، بز، بزغاله (به صورت زنده)", "گوسفند، بره، بز و بزغاله (به صورت زنده)", "minor"),
        ("ویزیت پزشک متخصص به جز روانپزشک", "ویزیت پزشک متخصص بجز روانپزشک", "minor"),
        ("انواع پودر ماشین لباسشویی", "انواع پودر ماشین لباسشویی و ظرفشویی", "broadened"),
        ("قهوه جوش ،کتری برقی", "قهوه‌جوش، کتری‌برقی، سبزی خردکن، غذاساز", "broadened"),
        ("انواع رادیو ترانزیستوری", "انواع رادیو", "narrowed"),
        ("چادر آماده رنگی", "سایر انواع چادر آماده", "reworded"),
        ("پنیر پیتزا", "تخم مرغ غیر ماشینی", "different"),
        ("انواع آبگرمکن گازی", "کولرگازی", "different"),  # 053125 in 1384
    ],
)
def test_compare(old, new, kind):
    assert compare(old, new).kind == kind


def test_short_words_do_not_match_inside_longer_ones():
    # "شیر" (milk) is not found inside "شیرینی" (sweets)
    assert compare("سایر انواع شیر", "شکر پنیر و سایر انواع شیرینی").old_kept < 0.8


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("خدمات آمبولانس G", ("خدمات آمبولانس", "public")),
        ("خدمات آمبولانس NG", ("خدمات آمبولانس", "private")),
        ("ویزیت روانپزشک(دولتی)", ("ویزیت روانپزشک", "public")),
        ("ویزیت روانپزشک (خصوصی)", ("ویزیت روانپزشک", "private")),
        ("پرستار خصوصی در منزل", ("پرستار خصوصی در منزل", "")),  # not a qualifier
        ("هزینه ثبت نام و شهریه در مدارس دولتی", ("هزینه ثبت نام و شهریه در مدارس دولتی", "")),
    ],
)
def test_split_qualifier(text, expected):
    assert split_qualifier(text) == expected


def test_relate_requires_same_provider():
    assert relate("ویزیت روانپزشک (دولتی)", "ویزیت روانپزشک G").kind == "same"
    assert relate("خدمات آمبولانس G", "خدمات آمبولانس NG").kind == "different"
    assert relate("خدمات آمبولانس", "خدمات آمبولانس G").kind == "different"
