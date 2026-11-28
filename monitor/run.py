"""1回分の価格チェック: 各市場から取得 → 判定 → 集計 → 保存 → ページ生成。

実行: python -m monitor.run            （本番。data/ と index.html を更新）
      python -m monitor.run --dry-run  （取得と集計だけ。ファイルは書かない）
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import time
from collections import Counter
from pathlib import Path

import yaml

from monitor import render, store
from monitor.aggregate import summarize
from monitor.normalize import judge
from monitor.sources import amazon, rakuten, yahoo_auction, yahoo_shopping

ROOT = Path(__file__).resolve().parent.parent
JST = dt.timezone(dt.timedelta(hours=9))
SOURCES = {
    "rakuten": rakuten.fetch,
    "yahoo_shopping": yahoo_shopping.fetch,
    "yahoo_auction": yahoo_auction.fetch,
    "amazon": amazon.fetch,
}
log = logging.getLogger("monitor")


def check_target(target: dict, cfg: dict, checked_at: str) -> dict:
    offers, excluded, status = [], Counter(), {}
    for market, fetch in SOURCES.items():
        if not cfg["markets"].get(market):
            continue
        result = fetch(target, cfg)
        status[market] = result.status
        for raw in result.items:
            offer, reason = judge(raw, target, cfg["common_exclude"], cfg["size"])
            if offer:
                offers.append(offer)
            else:
                excluded[reason.split("（")[0]] += 1
        log.info("%s / %s: %s（取得%d件）", target["id"], market, result.status, len(result.items))
        time.sleep(cfg["fetch"]["request_delay_seconds"])
    return summarize(offers, checked_at, status, dict(excluded))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    checked_at = dt.datetime.now(JST).isoformat(timespec="seconds")
    history = store.load_json(ROOT / "data/history.json", {"targets": {}})

    snapshots = {}
    for t in cfg["targets"]:
        snap = check_target(t, cfg, checked_at)
        snapshots[t["id"]] = {**snap, "previousLowestUnitPrice": store.previous_lowest(history, t["id"])}
        log.info("→ %s 最安 %s / 中央値 %s / 件数 %s", t["id"], snap["lowestUnitPrice"],
                 snap["medianUnitPrice"], snap["offerCount"])

    if args.dry_run:
        return
    latest = {"checkedAt": checked_at, "size": cfg["size"], "targets": cfg["targets"], "snapshots": snapshots}
    history = store.append_history(history, snapshots, cfg["history_limit"] // len(cfg["targets"]))
    store.save_json(ROOT / "data/latest.json", latest)
    store.save_json(ROOT / "data/history.json", history)
    (ROOT / "index.html").write_text(render.page(latest, history), encoding="utf-8")


if __name__ == "__main__":
    main()
