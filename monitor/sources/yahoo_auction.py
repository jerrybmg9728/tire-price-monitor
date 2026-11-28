"""ヤフオク!: 検索結果ページに埋め込まれたデータ（__NEXT_DATA__）から出品を読む。公式APIは無い。"""
from __future__ import annotations

import json
import re
import urllib.parse

import requests

from monitor.normalize import Raw
from monitor.sources import USER_AGENT, SourceResult, to_int

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
    return [r for r in (_to_raw(it) for it in items or [] if isinstance(it, dict)) if r]


def _to_raw(it: dict) -> Raw | None:
    price = to_int(it.get("buyNowPrice")) or to_int(it.get("price"))
    if not price or not it.get("title") or not it.get("auctionId"):
        return None
    seller = it.get("seller") if isinstance(it.get("seller"), dict) else {}
    name = str(seller.get("displayName") or "").strip("*").strip()
    return Raw(
        market="yahoo_auction",
        store=name or ("ストア出品" if seller.get("isStore") else "個人出品"),
        title=str(it["title"]),
        price=price,
        url=f"https://auctions.yahoo.co.jp/jp/auction/{urllib.parse.quote(str(it['auctionId']))}",
        shipping=0 if it.get("isFreeShipping") else None,
        condition=str(it.get("itemCondition") or "") or None,
        fixed_price=bool(it.get("isFixedPrice")) and bool(it.get("buyNowPrice")),
        bids=to_int(it.get("bidCount")) or 0,
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
