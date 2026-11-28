"""各市場から出品を取ってくる部分。どれも fetch(target, cfg) -> SourceResult を返す。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import requests

from monitor.normalize import Raw

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


@dataclass(frozen=True)
class SourceResult:
    status: str                      # "ok" / "未設定" / "エラー: ..."
    items: list[Raw] = field(default_factory=list)


def to_int(v: object) -> int | None:
    """価格を整数に。"1,980" や 12.5 も受け付け、読めなければ None。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        digits = v.replace(",", "").replace("円", "").strip()
        return int(float(digits)) if digits.replace(".", "", 1).isdigit() else None
    return None


def error_status(e: Exception) -> str:
    """エラーを短い状態文に。URL（キー入り）は出さない。"""
    code = getattr(getattr(e, "response", None), "status_code", "")
    return f"エラー: {type(e).__name__} {code}".strip()


_NEXT_DATA = re.compile(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def next_data(html: str) -> dict:
    """Next.js のページに埋め込まれたデータ（__NEXT_DATA__）を取り出す。"""
    m = _NEXT_DATA.search(html)
    if not m:
        raise ValueError("ページの形式が変わった可能性（__NEXT_DATA__ が見つからない）")
    return json.loads(m.group(1))


def embedded_state(html: str, marker: str) -> dict:
    """`window.__INITIAL_STATE__ = {...}` のような埋め込みデータを取り出す。"""
    i = html.find(marker)
    if i < 0:
        raise ValueError(f"ページの形式が変わった可能性（{marker.split('=')[0].strip()} が見つからない）")
    data, _ = json.JSONDecoder().raw_decode(html[i + len(marker):].lstrip())
    return data


def get_page(url: str, params: dict | None = None) -> str:
    resp = requests.get(url, params=params, timeout=20,
                        headers={"User-Agent": USER_AGENT, "Accept-Language": "ja"})
    resp.raise_for_status()
    return resp.text
