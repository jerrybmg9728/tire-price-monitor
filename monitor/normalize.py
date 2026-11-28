"""出品タイトルの正規化と、集計に入れてよいかの判定（純関数）。"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Raw:
    """各市場から取ってきたままの出品。"""
    market: str            # rakuten / yahoo_shopping / yahoo_auction / amazon
    store: str
    title: str
    price: int             # 表示価格（セットならセット総額）
    url: str
    shipping: int | None = None    # 送料（無料=0、不明=None）
    condition: str | None = None   # ヤフオク: NEW / USED60 など
    fixed_price: bool | None = None  # ヤフオク: 即決価格があるか
    bids: int | None = None          # ヤフオク: 入札数


@dataclass(frozen=True)
class Offer:
    """集計に使う出品（1本あたり単価に換算済み）。"""
    market: str
    store: str
    title: str
    price: int
    quantity: int
    unit_price: int
    url: str
    shipping: int | None
    inferred: bool = False   # 本数をタイトルから読めず、価格から推定した


def normalize_text(text: str) -> str:
    """全角→半角、連続空白を1つに。"""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "")).strip()


def _size_pattern(size: str) -> re.Pattern[str]:
    m = re.fullmatch(r"(\d{3})/(\d{2})R(\d{2})", size.upper())
    if not m:
        raise ValueError(f"サイズの形式が不正です: {size}")
    w, a, r = m.groups()
    return re.compile(rf"(?<!\d){w}\s*/\s*{a}\s*(?:Z?R|-)?\s*-?\s*{r}(?!\d)", re.I)


def has_size(title: str, size: str) -> bool:
    return bool(_size_pattern(size).search(normalize_text(title)))


def parse_quantity(title: str) -> int | None:
    """タイトルの「4本」「1本」などから本数を読む。違う本数が複数書かれていたら決めない（None）。"""
    found = {int(n) for n in re.findall(r"(?<!\d)([124])\s*本", normalize_text(title))}
    return found.pop() if len(found) == 1 else None


_PRICE_IN_TITLE = re.compile(
    r"[\\¥]\s*(\d{1,3}(?:,\d{3})+|\d{4,6})|(\d{1,3}(?:,\d{3})+|\d{4,6})\s*円"
)


_NOT_ITEM_PRICE = ("OFF", "オフ", "引", "割引", "クーポン", "値引")


def mentions_other_price(title: str, price: int) -> bool:
    """タイトルに表示価格と違う金額が書かれているか（ヤフオクの「4本26,800円～」など）。"""
    text = normalize_text(title)
    for m in _PRICE_IN_TITLE.finditer(text):
        before, after = text[max(0, m.start() - 4):m.start()], text[m.end():m.end() + 5].upper()
        if "送料" in before or after.startswith(_NOT_ITEM_PRICE):
            continue
        value = int((m.group(1) or m.group(2)).replace(",", ""))
        if value >= 1000 and value != price:
            return True
    return False


def _contains_any(title: str, words: list[str]) -> str | None:
    upper = normalize_text(title).upper()
    for w in words:
        if normalize_text(w).upper() in upper:
            return w
    return None


def _auction_reason(raw: Raw) -> str | None:
    if (raw.condition or "").upper() != "NEW":
        return f"新品以外（{raw.condition or '状態不明'}）"
    if raw.fixed_price is False:
        return "即決なし（落札額が未確定）"
    if raw.bids:
        return f"入札あり（{raw.bids}件・価格が未確定）"
    if mentions_other_price(raw.title, raw.price):
        return "タイトルに別の価格の記載あり（表示価格が何本分か不明）"
    if parse_quantity(raw.title) is None:
        return "本数の記載なし（2本・4本などの区別がつかない）"
    return None


def _to_offer(raw: Raw, target: dict) -> tuple[Offer | None, str | None]:
    lo, hi = target["unit_range"]
    q = parse_quantity(raw.title)
    inferred = q is None
    if q is None:
        fits = [n for n in (1, 4) if lo <= raw.price / n <= hi]
        if len(fits) != 1:
            # どちらにも当てはまる／どちらにも当てはまらない → 本数を決められないので除外
            return None, f"本数不明（¥{raw.price:,}）"
        q = fits[0]
    unit = round(raw.price / q)
    if not lo <= unit <= hi:
        return None, f"単価が範囲外（¥{unit:,}/本）"
    offer = Offer(raw.market, raw.store, normalize_text(raw.title), raw.price, q, unit,
                  raw.url, raw.shipping, inferred)
    return offer, None


def judge(raw: Raw, target: dict, common_exclude: list[str], size: str) -> tuple[Offer | None, str | None]:
    """集計に入れる出品なら (Offer, None)、除外なら (None, 理由)。"""
    if not has_size(raw.title, size):
        return None, "サイズ違い"
    hit = _contains_any(raw.title, common_exclude + target.get("exclude", []))
    if hit:
        return None, f"除外語「{hit}」"
    if target.get("require_any") and not _contains_any(raw.title, target["require_any"]):
        return None, "銘柄違い"
    if raw.market == "yahoo_auction":
        reason = _auction_reason(raw)
        if reason:
            return None, reason
    return _to_offer(raw, target)
