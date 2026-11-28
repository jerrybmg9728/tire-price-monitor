"""各市場から出品を取ってくる部分。どれも fetch(target, cfg) -> SourceResult を返す。"""
from __future__ import annotations

from dataclasses import dataclass, field

from monitor.normalize import Raw

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"


@dataclass(frozen=True)
class SourceResult:
    status: str                      # "ok" / "未設定" / "エラー: ..."
    items: list[Raw] = field(default_factory=list)


def error_status(e: Exception) -> str:
    """エラーを短い状態文に。URL（キー入り）は出さない。"""
    code = getattr(getattr(e, "response", None), "status_code", "")
    return f"エラー: {type(e).__name__} {code}".strip()
