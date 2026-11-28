"""Amazon: 公式の Creators API（旧 PA-API 5 の後継）で取得する予定の枠。

Creators API はAmazonアソシエイトの登録と専用の資格情報が必要。資格情報を受け取り、
日本（amazon.co.jp）で使えることを確認してから実装する。それまでは「未接続」を返す。
※ Amazonの画面を直接読み取る方法は利用規約に反するため使わない。
"""
from __future__ import annotations

from monitor.sources import SourceResult


def fetch(target: dict, cfg: dict) -> SourceResult:
    return SourceResult("未接続（Creators API の資格情報待ち）")
