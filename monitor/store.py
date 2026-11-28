"""履歴（data/history.json）と最新結果（data/latest.json）の読み書き。"""
from __future__ import annotations

import json
from pathlib import Path

HISTORY_KEYS = ("checkedAt", "lowestUnitPrice", "top3AvgUnitPrice", "medianUnitPrice", "offerCount", "status",
                "degraded")


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    tmp.replace(path)   # 途中で落ちても壊れたファイルを残さない


def append_history(history: dict, snapshots: dict[str, dict], limit_per_target: int) -> dict:
    """スナップショットを履歴に足した新しい dict を返す（元の dict は変えない）。"""
    targets = dict(history.get("targets", {}))
    for tid, snap in snapshots.items():
        row = {k: snap.get(k) for k in HISTORY_KEYS}
        targets[tid] = (list(targets.get(tid, [])) + [row])[-limit_per_target:]
    return {**history, "targets": targets}


def previous_lowest(history: dict, tid: str) -> int | None:
    """前回（価格が取れた直近）の最安単価。"""
    for row in reversed(history.get("targets", {}).get(tid, [])):
        if row.get("lowestUnitPrice") is not None:
            return row["lowestUnitPrice"]
    return None
