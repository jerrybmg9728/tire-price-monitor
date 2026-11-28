"""Yahoo!ショッピング: 公式「商品検索API（v3）」。環境変数 YAHOO_APP_ID（Client ID）が必要。"""
from __future__ import annotations

import os

import requests

from monitor.normalize import Raw
from monitor.sources import SourceResult, error_status

API_URL = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"
_SHIPPING_FREE = 2   # shipping.code: 1=設定なし 2=送料無料 3=条件付き送料無料


def parse(data: dict) -> list[Raw]:
    raws = []
    for h in data.get("hits") or []:
        if not h.get("name") or not h.get("price"):
            continue
        raws.append(Raw(
            market="yahoo_shopping",
            store=(h.get("seller") or {}).get("name") or "Yahoo!ショッピング",
            title=h["name"],
            price=int(h["price"]),
            url=h.get("url") or "",
            shipping=0 if (h.get("shipping") or {}).get("code") == _SHIPPING_FREE else None,
        ))
    return raws


def fetch(target: dict, cfg: dict) -> SourceResult:
    app_id = os.environ.get("YAHOO_APP_ID", "")
    if not app_id:
        return SourceResult("未設定（YAHOO_APP_ID なし）")
    params = {
        "appid": app_id,
        "query": target["query"],
        "results": cfg["fetch"]["yahoo_shopping_results"],
        "sort": "+price",
        "in_stock": "true",
        "condition": "new",
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=20)
        resp.raise_for_status()
        return SourceResult("ok", parse(resp.json()))
    except (requests.RequestException, ValueError) as e:
        # appid を含むURLをそのまま出さない
        return SourceResult(error_status(e))
