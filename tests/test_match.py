from hiesir_codebook.match import Item, code_periods, link


def _items(year, *rows):
    return [Item(year, 1, code, text) for code, text in rows]


def test_link_relations():
    data = {
        1: _items(
            1,
            ("011", "برنج طارم"),
            ("012", "گوشت گوسفند"),
            ("013", "تودوزی اتومبیل"),
            ("014", "صافکاری و نقاشی اتومبیل"),
            ("015", "پنیر پیتزا"),
            ("016", "جوش شیرین، وانیل و مایه خمیر نان"),
        ),
        2: _items(
            2,
            ("011", "برنج  طارم،"),  # trivial difference: no change recorded
            ("022", "گوشت گوسفند"),  # new code, same item
            ("014", "صافکاری، نقاشی و تودوزی اتومبیل"),  # absorbs 013
            ("015", "تخم مرغ غیر ماشینی"),  # code reused for something else
            ("016", "جوش شیرین و وانیل"),
            ("017", "خمیر نان"),  # split out of 016
        ),
        3: _items(3, ("022", "گوشت گوسفند"), ("014", "صافکاری، نقاشی و تودوزی اتومبیل")),
        4: _items(4, ("011", "برنج طارم"), ("022", "گوشت گوسفند")),
    }
    series = {s.id: s for s in link(data, max_gap=2)}
    changes = {sid: [c.change for c in s.history] for sid, s in series.items()}

    assert changes["011-1"] == ["start", "reappeared"]  # missing in year 3
    assert series["011-1"].years == [1, 2, 4]
    assert changes["012-1"] == ["start", "recoded"]
    assert series["012-1"].code == "022"
    assert code_periods(series["012-1"]) == [("012", 1, 1), ("022", 2, 4)]
    assert code_periods(series["011-1"]) == [("011", 1, 4)]  # missing in year 3, one code
    # a merge ends both series; the merged item starts a new one
    assert series["013-1"].end == "merged_into 014-2"
    assert series["014-1"].end == "merged_into 014-2"
    assert series["014-1"].years == [1]
    assert changes["014-2"] == ["merged_from"]
    assert series["014-2"].history[0].related == "014-1 013-1"
    assert series["014-2"].years == [2, 3]
    assert changes["015-2"] == ["code_reused"]
    # a split ends the source; what is left of it and the new part start anew
    assert series["016-1"].end == "split_into 016-2 017-2"
    assert changes["016-2"] == ["split_from"]
    assert changes["017-2"] == ["split_from"]
    assert series["017-2"].history[0].related == "016-1"


def test_link_provider_split():
    data = {
        1: _items(
            1, ("031", "خدمات آمبولانس"), ("041", "ویزیت روانپزشک (دولتی)"), ("042", "ویزیت روانپزشک (خصوصی)")
        ),
        2: _items(
            2,
            ("043", "خدمات آمبولانس G"),
            ("044", "خدمات آمبولانس NG"),
            ("017", "ویزیت روانپزشک و روانشناس بالینی G"),
            ("018", "ویزیت روانپزشک و روانشناس بالینی NG"),
        ),
    }
    series = {s.id: s for s in link(data)}
    assert series["031-1"].end == "split_into 043-2 044-2"
    assert [c.change for c in series["043-2"].history] == ["split_from"]
    assert series["044-2"].history[0].related == "031-1"
    # public continues into G, private into NG
    assert series["041-1"].code == "017"
    assert series["042-1"].code == "018"


def test_link_collapsed_group():
    # 1390: "other domestic colour TVs" + "21-inch domestic TVs" -> "all domestic colour TVs"
    data = {
        1: _items(
            1,
            ("01112", "انواع تلویزیون 21 اینچ رنگی تولید داخل"),
            ("01113", "انواع تلویزیون 21 اینچ رنگی تولید خارج"),
            ("01114", "سایر انواع تلویزیون رنگی داخلی"),
            ("01115", "سایر انواع تلویزیون رنگی خارجی"),
            ("01116", "کرایه لوازم سفره عقد"),
        ),
        2: _items(
            2,
            ("01128", "انواع تلویزیون رنگی داخلی"),
            ("01129", "انواع تلویزیون رنگی خارجی"),
        ),
    }
    series = {s.id: s for s in link(data)}
    assert series["01128-2"].history[0].change == "merged_from"
    assert series["01128-2"].history[0].related == "01114-1 01112-1"
    assert series["01129-2"].history[0].related == "01115-1 01113-1"
    assert series["01112-1"].end == "merged_into 01128-2"
    assert series["01116-1"].end == ""  # unrelated: dropped, not merged
