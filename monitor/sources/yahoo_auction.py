"""ヤフオク!: 検索結果ページに埋め込まれたデータ（__NEXT_DATA__）から出品を読む。公式APIは無い。"""
from __future__ import annotations

import json
import re
import urllib.parse

import requests

from monitor.normalize import Raw
from monitor.sources import USER_AGENT, SourceResult

SEARCH_URL = "https://auctions.yahoo.co.jp/search/search"
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)


def parse(html: str) -> list[Raw]:
    m = _NEXT_DATA.search(html)
    if not m:
        raise ValueError("ページの形式が変わった可能性（__NEXT_DATA__ が見つからない）")
    data = json.loads(m.group(1))
    try:
        items = data["props"]["pageProps"]["initialState"]["search"]["items"]["listing"]["items"]
    except (KeyError, TypeError) as e:
        raise ValueError(f"ページの形式が変わった可能性（出品一覧が見つからない: {e}）") from e
    return [_to_raw(it) for it in items if it.get("title") and it.get("auctionId")]


def _to_raw(it: dict) -> Raw:
    price = int(it.get("buyNowPrice") or it.get("price") or 0)
    seller = it.get("seller") or {}
    name = (seller.get("displayName") or "").strip("*").strip()
    return Raw(
        market="yahoo_auction",
        store=name or ("ストア出品" if seller.get("isStore") else "個人出品"),
        title=it["title"],
        price=price,
        url=f"https://auctions.yahoo.co.jp/jp/auction/{it['auctionId']}",
        shipping=0 if it.get("isFreeShipping") else None,
        condition=it.get("itemCondition"),
        fixed_price=bool(it.get("isFixedPrice")) and bool(it.get("buyNowPrice")),
        bids=int(it.get("bidCount") or 0),
    )


def fetch(target: dict, cfg: dict) -> SourceResult:
    params = {"p": target["query"], "n": cfg["fetch"]["yahoo_auction_per_page"]}
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ja"}, timeout=20)
        resp.raise_for_status()
        return SourceResult("ok", parse(resp.text))
    except (requests.RequestException, ValueError) as e:
        return SourceResult(f"エラー: {e}")
