import json

from monitor import run, store
from monitor.normalize import Raw
from monitor.sources import SourceResult

CFG = {
    "size": "155/65R14", "site_url": "https://x/", "common_exclude": ["中古"],
    "markets": {"rakuten": True, "yahoo_shopping": True, "yahoo_auction": False, "amazon": True},
    "fetch": {"request_delay_seconds": 0},
}
TARGET = {"id": "vrx3", "require_any": ["VRX3"], "exclude": [], "unit_range": [4000, 16000], "query": "q"}


def fake(items, status="ok"):
    return lambda target, cfg: SourceResult(status, items)


def test_check_target_combines_markets(monkeypatch):
    monkeypatch.setattr(run, "SOURCES", {
        "rakuten": fake([Raw("rakuten", "S", "VRX3 155/65R14 4本", 34000, "u1"),
                         Raw("rakuten", "S", "VRX3 155/65R14 中古 4本", 10000, "u2")]),
        "yahoo_shopping": fake([Raw("yahoo_shopping", "Y", "VRX3 155/65R14 1本", 9000, "u3")]),
        "yahoo_auction": fake([Raw("yahoo_auction", "A", "VRX3 155/65R14 4本", 1, "u4")]),
        "amazon": fake([], "未接続"),
    })
    s = run.check_target(TARGET, CFG, "2026-11-28T00:00:00+09:00")
    assert s["lowestUnitPrice"] == 8500 and s["offerCount"] == 2
    assert s["excluded"] == {"除外語「中古」": 1}
    assert s["marketStatus"] == {"rakuten": "ok", "yahoo_shopping": "ok", "amazon": "未接続"}   # 無効の市場は呼ばない


def test_save_and_load_json(tmp_path):
    p = tmp_path / "d" / "h.json"
    assert store.load_json(p, {"targets": {}}) == {"targets": {}}
    store.save_json(p, {"日本語": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"日本語": 1}
    assert store.load_json(p, {}) == {"日本語": 1}


def test_check_target_survives_crashing_source(monkeypatch):
    def boom(target, cfg):
        raise TypeError("bad data")
    monkeypatch.setattr(run, "SOURCES", {"rakuten": boom,
                                         "yahoo_shopping": fake([Raw("yahoo_shopping", "Y", "VRX3 155/65R14 4本", 34000, "u")])})
    s = run.check_target(TARGET, CFG, "t")
    assert s["marketStatus"]["rakuten"] == "エラー: TypeError" and s["lowestUnitPrice"] == 8500


def test_settle():
    ok = {"checkedAt": "2", "marketStatus": {"rakuten": "ok", "amazon": "未接続"}}
    part = {"checkedAt": "2", "marketStatus": {"rakuten": "ok", "yahoo_shopping": "エラー: X 500"}}
    dead = {"checkedAt": "2", "marketStatus": {"rakuten": "エラー: X 403", "amazon": "未接続"}}
    prev = {"checkedAt": "1", "lowestUnitPrice": 7000, "marketStatus": {"rakuten": "ok"}}
    assert run.settle(ok, prev) == ({**ok, "degraded": []}, True)
    assert run.settle(part, prev)[0]["degraded"] == ["yahoo_shopping"]
    shown, record = run.settle(dead, prev)
    assert not record and shown["stale"] and shown["lowestUnitPrice"] == 7000 and shown["staleAt"] == "2"
    shown, record = run.settle(dead, None)
    assert not record and shown["stale"]
