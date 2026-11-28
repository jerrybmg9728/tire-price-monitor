import json

from monitor import render, store
from monitor.aggregate import summarize
from monitor.normalize import Offer
from monitor.sources import error_status, rakuten, yahoo_auction, yahoo_shopping


def test_yahoo_auction_parse():
    items = [{"auctionId": "x1", "title": "VRX3 155/65R14 4本", "price": 28000, "buyNowPrice": 28000,
              "isFixedPrice": True, "bidCount": 0, "itemCondition": "NEW", "isFreeShipping": True,
              "seller": {"displayName": "*****", "isStore": False}},
             {"auctionId": "x2", "title": "", "price": 1}]
    data = {"props": {"pageProps": {"initialState": {"search": {"items": {"listing": {"items": items}}}}}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    [r] = yahoo_auction.parse(html)
    assert r.price == 28000 and r.fixed_price and r.bids == 0 and r.shipping == 0
    assert r.store == "個人出品" and r.url.endswith("/x1")


def test_yahoo_auction_parse_changed_page():
    try:
        yahoo_auction.parse("<html></html>")
        raise AssertionError("should fail")
    except ValueError as e:
        assert "形式が変わった" in str(e)


def test_yahoo_shopping_parse():
    data = {"hits": [{"name": "VRX3", "price": 30000, "url": "u", "seller": {"name": "店A"}, "shipping": {"code": 2}},
                     {"name": "x", "price": 0}]}
    [r] = yahoo_shopping.parse(data)
    assert (r.store, r.price, r.shipping) == ("店A", 30000, 0)


def test_rakuten_parse_both_formats():
    v2 = {"Items": [{"itemName": "A", "itemPrice": 34000, "itemUrl": "u", "shopName": "S", "postageFlag": 0}]}
    v1 = {"Items": [{"Item": {"itemName": "B", "itemPrice": 9000, "itemUrl": "u2", "shopName": "T", "postageFlag": 1}}]}
    assert rakuten.parse(v2)[0].shipping == 0
    assert rakuten.parse(v1)[0].shipping is None


def test_missing_keys_report_unset(monkeypatch):
    monkeypatch.delenv("YAHOO_APP_ID", raising=False)
    monkeypatch.delenv("RAKUTEN_APP_ID", raising=False)
    assert yahoo_shopping.fetch({"query": "q"}, {}).status.startswith("未設定")
    assert rakuten.fetch({"query": "q"}, {}).status.startswith("未設定")


def test_error_status_hides_url():
    class Resp:
        status_code = 403
    e = Exception("https://api?appid=SECRET")
    e.response = Resp()
    assert error_status(e) == "エラー: Exception 403"


def test_history_append_is_immutable_and_trims():
    h = {"targets": {"a": [{"checkedAt": "1", "lowestUnitPrice": 1}]}}
    snap = {"checkedAt": "2", "lowestUnitPrice": None, "offers": [1]}
    h2 = store.append_history(h, {"a": snap}, limit_per_target=1)
    assert len(h["targets"]["a"]) == 1 and h2["targets"]["a"] == [
        {"checkedAt": "2", "lowestUnitPrice": None, "top3AvgUnitPrice": None, "medianUnitPrice": None,
         "offerCount": None, "status": None}]
    assert store.previous_lowest(h, "a") == 1 and store.previous_lowest(h2, "a") is None


def test_render_page_escapes_and_shows_values():
    o = Offer("rakuten", "店<b>", "VRX3 <script>alert(1)</script>", 34000, 4, 8500, "https://x", 0)
    snap = {**summarize([o], "2026-11-28T12:31:00+09:00", {"rakuten": "ok", "amazon": "未接続（…）"}, {"サイズ違い": 2}),
            "previousLowestUnitPrice": 9000}
    latest = {"checkedAt": snap["checkedAt"], "size": "155/65R14",
              "targets": [{"id": "vrx3", "name": "VRX3", "season": "winter"}], "snapshots": {"vrx3": snap}}
    page = render.page(latest, {"targets": {"vrx3": [{"checkedAt": snap["checkedAt"], "lowestUnitPrice": 8500}]}})
    assert "¥8,500" in page and "前回比 −¥500" in page and "2026/11/28 12:31" in page
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page
    assert "店&lt;b&gt;" in page and "サイズ違い 2件" in page
