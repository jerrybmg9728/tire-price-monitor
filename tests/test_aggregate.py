from monitor.aggregate import dedupe, summarize
from monitor.normalize import Offer


def offer(unit, market="rakuten", url=None, q=4):
    return Offer(market, "店", "t", unit * q, q, unit, url or f"https://x/{unit}/{market}", 0)


def test_dedupe_same_url_keeps_cheapest_and_sorts():
    a = offer(9000, url="https://same")
    b = offer(8000, url="https://same")
    c = offer(7000)
    assert [o.unit_price for o in dedupe([a, b, c])] == [7000, 8000]


def test_summarize_stats():
    offers = [offer(7000), offer(8000, "yahoo_shopping"), offer(9000, "yahoo_auction"), offer(12000)]
    s = summarize(offers, "2026-11-28T00:00:00+09:00", {"rakuten": "ok"}, {"サイズ違い": 3})
    assert s["status"] == "ok"
    assert s["lowestUnitPrice"] == 7000 and s["lowestSetPrice"] == 28000
    assert s["medianUnitPrice"] == 8500
    assert s["top3AvgUnitPrice"] == 8000
    assert s["perMarket"] == {"rakuten": 2, "yahoo_shopping": 1, "yahoo_auction": 1, "amazon": 0}
    assert s["excluded"] == {"サイズ違い": 3}
    assert len(s["offers"]) == 4


def test_summarize_empty():
    s = summarize([], "t", {}, {})
    assert s["status"] == "no_results"
    assert s["lowestUnitPrice"] is None and s["medianUnitPrice"] is None and s["top3AvgUnitPrice"] is None
