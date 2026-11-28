"""楽天市場: 検索結果ページに埋め込まれたデータ（window.__INITIAL_STATE__）から出品を読む。

キー不要。robots.txt で並べ替え（?s=）付きのURLは自動取得が禁止されているため、
標準の並び順のページだけを読み、安い順への並べ替えはこちらで行う。
"""
from __future__ import annotations

import urllib.parse

import requests

from monitor.normalize import Raw
from monitor.sources import SourceResult, embedded_state, error_status, get_page, to_int

SEARCH_URL = "https://search.rakuten.co.jp/search/mall/{}/"
_MARKER = "window.__INITIAL_STATE__ ="


def parse(html: str) -> list[Raw]:
    state = embedded_state(html, _MARKER)
    try:
        items = state["state"]["data"]["ichibaSearch"]["items"]
    except (KeyError, TypeError) as e:
        raise ValueError(f"ページの形式が変わった可能性（出品一覧が見つからない: {e}）") from e
    return [r for r in (_to_raw(it) for it in items or [] if isinstance(it, dict)) if r]


def _to_raw(it: dict) -> Raw | None:
    price = to_int(it.get("price"))
    if not price or not it.get("name") or it.get("isSoldOut"):
        return None
    shop = it.get("shop") if isinstance(it.get("shop"), dict) else {}
    shipping = it.get("shipping") if isinstance(it.get("shipping"), dict) else {}
    url = str(it.get("url") or "").split("?")[0]
    return Raw(
        market="rakuten",
        store=str(shop.get("name") or "楽天市場"),
        title=str(it["name"]),
        price=price,
        url=url,
        shipping=0 if to_int(shipping.get("price")) == 0 else None,
    )


def fetch(target: dict, cfg: dict) -> SourceResult:
    url = SEARCH_URL.format(urllib.parse.quote(target["query"]))
    try:
        return SourceResult("ok", parse(get_page(url)))
    except ValueError as e:
        return SourceResult(f"エラー: {e}")
    except requests.RequestException as e:
        return SourceResult(error_status(e))
