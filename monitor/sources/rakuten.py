"""楽天市場: 公式「楽天市場商品検索API」（2026年移行後の openapi.rakuten.co.jp 系）。

必要な環境変数: RAKUTEN_APP_ID（applicationId）, RAKUTEN_ACCESS_KEY（accessKey）
楽天のアプリ設定に登録したWebサイトURLを Referer / Origin に付けて呼ぶ。
エンドポイントの版は変わることがあるので RAKUTEN_ENDPOINT で差し替えられる。
"""
from __future__ import annotations

import os
import urllib.parse

import requests

from monitor.normalize import Raw
from monitor.sources import SourceResult, error_status, to_int

DEFAULT_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601"


def parse(data: dict) -> list[Raw]:
    raws = []
    for row in data.get("Items") or []:
        if not isinstance(row, dict):
            continue
        it = row.get("Item", row)   # formatVersion 1 は {"Item": {...}}、2 はそのまま
        price = to_int(it.get("itemPrice")) if isinstance(it, dict) else None
        if not price or not it.get("itemName"):
            continue
        raws.append(Raw(
            market="rakuten",
            store=str(it.get("shopName") or "楽天市場"),
            title=str(it["itemName"]),
            price=price,
            url=str(it.get("itemUrl") or ""),
            shipping=0 if it.get("postageFlag") == 0 else None,   # 0=送料込
        ))
    return raws


def _headers(site_url: str) -> dict:
    parts = urllib.parse.urlsplit(site_url)
    return {"Referer": site_url, "Origin": f"{parts.scheme}://{parts.netloc}"}


def fetch(target: dict, cfg: dict) -> SourceResult:
    app_id = os.environ.get("RAKUTEN_APP_ID", "")
    access_key = os.environ.get("RAKUTEN_ACCESS_KEY", "")
    if not app_id or not access_key:
        return SourceResult("未設定（RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY なし）")
    params = {
        "applicationId": app_id,
        "accessKey": access_key,
        "keyword": target["query"],
        "hits": cfg["fetch"]["rakuten_hits"],
        "sort": "+itemPrice",
        "availability": 1,
        "formatVersion": 2,
    }
    endpoint = os.environ.get("RAKUTEN_ENDPOINT") or DEFAULT_ENDPOINT
    try:
        resp = requests.get(endpoint, params=params, headers=_headers(cfg["site_url"]), timeout=20)
        resp.raise_for_status()
        return SourceResult("ok", parse(resp.json()))
    except (requests.RequestException, ValueError) as e:
        return SourceResult(error_status(e))
