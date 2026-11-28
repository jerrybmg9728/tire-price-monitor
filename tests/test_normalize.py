from monitor.normalize import (
    Raw, has_size, parse_quantity, mentions_other_price, judge, normalize_text,
)

VRX3 = {"id": "vrx3", "require_any": ["VRX3"], "exclude": [], "unit_range": [4000, 30000]}
SUMMER = {"id": "summer", "require_any": [], "exclude": ["スタッドレス", "VRX"], "unit_range": [2500, 25000]}
COMMON = ["ホイールセット", "中古", "予約"]
SIZE = "155/65R14"


def raw(title, price, market="rakuten", **kw):
    return Raw(market=market, store="店", title=title, price=price, url="https://x", **kw)


def test_normalize_text_full_width():
    assert normalize_text("１５５／６５Ｒ１４　ＶＲＸ３") == "155/65R14 VRX3"


def test_has_size_variants():
    for t in ["155/65R14 75Q", "155/65 R14", "155/65-14", "１５５／６５Ｒ１４", "155/65r14"]:
        assert has_size(t, SIZE), t
    assert not has_size("165/65R14", SIZE)
    assert not has_size("155/65R15", SIZE)


def test_parse_quantity():
    assert parse_quantity("VRX3 155/65R14 4本セット") == 4
    assert parse_quantity("単品4本価格 送料無料") == 4
    assert parse_quantity("タイヤ１本 155/65R14") == 1
    assert parse_quantity("2本セット") == 2
    assert parse_quantity("155/65R14 75Q") is None
    assert parse_quantity("1本価格 4本セット購入で送料無料") is None   # 本数が2通り書かれている → 決めない


def test_mentions_other_price():
    assert mentions_other_price("4本/本州法人宛26800円～ VRX3", 13800)
    assert mentions_other_price("送料込4本セット\\26,500円～", 13500)
    assert not mentions_other_price("VRX3 4本 25,000円", 25000)
    assert not mentions_other_price("VRX3 4本", 25000)
    assert not mentions_other_price("VRX3 4本 5,000円OFFクーポン", 25000)
    assert not mentions_other_price("VRX3 4本 送料1,500円", 25000)
    assert not mentions_other_price("VRX3 4本 3000円引き", 25000)


def test_judge_ok_set_price():
    o, reason = judge(raw("VRX3 155/65R14 4本セット", 34000), VRX3, COMMON, SIZE)
    assert reason is None and o.quantity == 4 and o.unit_price == 8500


def test_judge_infers_set_when_unit_too_high():
    # 本数の記載なし・1本としては高すぎる → 4本として妥当なら4本扱い
    o, reason = judge(raw("VRX3 155/65R14", 32000), VRX3, COMMON, SIZE)
    assert reason is None and o.quantity == 4 and o.inferred


def test_judge_ambiguous_quantity_is_excluded():
    # 1本とも4本とも取れる価格は除外（VRX3 の範囲 4,000〜30,000 では ¥20,000 はどちらにも当てはまる）
    o, reason = judge(raw("VRX3 155/65R14", 20000), VRX3, COMMON, SIZE)
    assert o is None and "本数不明" in reason


def test_judge_rejections():
    cases = [
        (raw("VRX3 165/65R14 4本", 30000), "サイズ違い"),
        (raw("ヨコハマ 155/65R14 4本", 30000), "銘柄違い"),
        (raw("VRX3 155/65R14 ホイールセット 4本", 60000), "除外語"),
        (raw("VRX3 155/65R14 中古 4本", 20000), "除外語"),
        (raw("VRX3 155/65R14 4本", 4000), "単価が範囲外"),
    ]
    for r, expected in cases:
        o, reason = judge(r, VRX3, COMMON, SIZE)
        assert o is None and expected in reason, (r.title, reason)


def test_judge_summer_excludes_studless():
    o, reason = judge(raw("155/65R14 スタッドレス 4本", 20000), SUMMER, COMMON, SIZE)
    assert o is None and "除外語" in reason


def test_judge_auction_rules():
    base = dict(market="yahoo_auction", condition="NEW", fixed_price=True, bids=0)
    ok, reason = judge(raw("VRX3 155/65R14 新品4本セット", 28000, **base), VRX3, COMMON, SIZE)
    assert reason is None and ok.unit_price == 7000
    _, reason = judge(raw("VRX3 155/65R14 4本 26800円～", 13800, **base), VRX3, COMMON, SIZE)
    assert "別の価格" in reason
    _, reason = judge(raw("VRX3 155/65R14 4本", 28000, **{**base, "fixed_price": False}), VRX3, COMMON, SIZE)
    assert "即決なし" in reason
    _, reason = judge(raw("VRX3 155/65R14 4本", 28000, **{**base, "condition": "USED60"}), VRX3, COMMON, SIZE)
    assert "新品以外" in reason
    _, reason = judge(raw("VRX3 155/65R14 4本", 28000, **{**base, "bids": 3}), VRX3, COMMON, SIZE)
    assert "入札あり" in reason
    _, reason = judge(raw("VRX3 155/65R14 新品", 20000, **base), VRX3, COMMON, SIZE)
    assert "本数の記載なし" in reason
    _, reason = judge(raw("VRX3 155/65R14 4本", 28000, **{**base, "condition": None}), VRX3, COMMON, SIZE)
    assert "新品以外" in reason
