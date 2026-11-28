"""Yahoo!ショッピング: 検索結果ページに埋め込まれたデータ（__NEXT_DATA__）から出品を読む。キー不要。"""
from __future__ import annotations

import requests

from monitor.normalize import Raw
from monitor.sources import SourceResult, error_status, get_page, next_data, to_int

SEARCH_URL = "https://shopping.yahoo.co.jp/search"


def _result_items(data: dict) -> list:
    """検索結果のブロック（type=RESULT）にある出品を集める。"""
    try:
        groups = data["props"]["initialState"]["bff"]["searchResults"]["items"]
    except (KeyError, TypeError) as e:
        raise ValueError(f"ページの形式が変わった可能性（検索結果が見つからない: {e}）") from e
    blocks = [b for g in (groups.values() if isinstance(groups, dict) else [groups])
              for b in (g if isinstance(g, list) else [g]) if isinstance(b, dict)]
    return [it for b in blocks if b.get("type") == "RESULT"
            for it in ((b.get("content") or {}).get("items") or [])]


def parse(html: str) -> list[Raw]:
    return [r for r in (_to_raw(it) for it in _result_items(next_data(html)) if isinstance(it, dict)) if r]


def _to_raw(it: dict) -> Raw | None:
    price = to_int(it.get("price"))
    if not price or not it.get("name"):
        return None
    store = it.get("store") if isinstance(it.get("store"), dict) else {}
    return Raw(
        market="yahoo_shopping",
        store=str(store.get("name") or "Yahoo!ショッピング"),
        title=str(it["name"]),
        price=price,
        url=str(it.get("url") or "").split("?")[0],
        shipping=0 if it.get("freeCondition") == "FREE" else None,
    )


def fetch(target: dict, cfg: dict) -> SourceResult:
    try:
        return SourceResult("ok", parse(get_page(SEARCH_URL, {"p": target["query"]})))
    except ValueError as e:
        return SourceResult(f"エラー: {e}")
    except requests.RequestException as e:
        return SourceResult(error_status(e))
