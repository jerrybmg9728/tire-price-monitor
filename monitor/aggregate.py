"""1回のチェック結果を1件のスナップショットにまとめる（純関数）。"""
from __future__ import annotations

import statistics
from dataclasses import asdict

from monitor.normalize import Offer

MARKET_LABEL = {
    "rakuten": "楽天市場",
    "yahoo_shopping": "Yahoo!ショッピング",
    "yahoo_auction": "ヤフオク!",
    "amazon": "Amazon",
}


def dedupe(offers: list[Offer]) -> list[Offer]:
    """同じ商品ページの重複を除き、単価の安い順に並べる。"""
    seen: dict[str, Offer] = {}
    for o in offers:
        key = o.url or f"{o.market}|{o.store}|{o.title}|{o.price}"
        if key not in seen or o.unit_price < seen[key].unit_price:
            seen[key] = o
    return sorted(seen.values(), key=lambda o: (o.unit_price, o.market))


def summarize(offers: list[Offer], checked_at: str, market_status: dict[str, str],
              excluded: dict[str, int], keep: int = 10) -> dict:
    """スナップショット: 最安・中央値・上位3件平均・市場別件数・掲載用の出品。"""
    ranked = dedupe(offers)
    units = [o.unit_price for o in ranked]
    best = ranked[0] if ranked else None
    per_market = {m: sum(1 for o in ranked if o.market == m) for m in MARKET_LABEL}
    return {
        "checkedAt": checked_at,
        "status": "ok" if ranked else "no_results",
        "lowestUnitPrice": units[0] if units else None,
        "lowestSetPrice": (best.price if best.quantity == 4 else best.unit_price * 4) if best else None,
        "lowestStore": best.store if best else None,
        "lowestMarket": best.market if best else None,
        "lowestUrl": best.url if best else None,
        "medianUnitPrice": round(statistics.median(units)) if units else None,
        "top3AvgUnitPrice": round(sum(units[:3]) / len(units[:3])) if units else None,
        "offerCount": len(ranked),
        "perMarket": per_market,
        "marketStatus": market_status,
        "excluded": excluded,
        "offers": [asdict(o) for o in ranked[:keep]],
    }
