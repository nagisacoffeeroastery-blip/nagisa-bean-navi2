#!/usr/bin/env python3
"""Normalize raw Square crawl data into the Bean Navi products.json schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("raw_products.json")
DEFAULT_OUTPUT = Path("products.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize raw Square products for Bean Navi.")
    parser.add_argument("-i", "--input", default=str(DEFAULT_INPUT), help="Input raw_products.json path.")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT), help="Output products.json path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_payload = read_json(Path(args.input))
    raw_products = raw_payload if isinstance(raw_payload, list) else raw_payload.get("products", [])
    products = [normalize_product(product) for product in raw_products]
    output = {"products": products}

    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(products)} products to {args.output}")
    return 0


def read_json(path: Path) -> Any:
    """Read JSON from a file."""

    return json.loads(path.read_text(encoding="utf-8"))


def normalize_product(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert one raw product to the app's product schema."""

    name = string_or_default(raw.get("name"), "未設定の商品")
    description = string_or_default(raw.get("description"), "TODO: 商品説明を確認してください。")
    options = list_or_empty(raw.get("options"))
    tags = infer_flavor_tags(name, description, list_or_empty(raw.get("tags")))
    raw_category = string_or_default(raw.get("category"), "")
    category = raw_category if raw_category and is_product_category(raw_category) else infer_category(name, tags)
    available = raw.get("available")
    recommend_enabled = is_diagnosis_target(name, description)
    workshop = infer_workshop(name, description)
    subscription = infer_subscription(name, description)
    seasonal = infer_seasonal(name, description, tags)
    sales_rank = infer_sales_rank(name)
    sales_score = infer_sales_score(sales_rank)

    return {
        "id": make_product_id(name),
        "name": name,
        "category": category,
        "roast": infer_roast(name, description, tags),
        "description": description,
        "price": raw.get("price"),
        "image_url": raw.get("image_url") or "",
        "square_url": raw.get("product_url") or raw.get("square_url") or "",
        "seasonal": seasonal,
        "priority": infer_priority(name, description, tags, seasonal, workshop, subscription),
        "workshop": workshop,
        "subscription": subscription,
        "sales_rank": sales_rank,
        "sales_score": sales_score,
        "flavor_tags": tags,
        "acid_level": infer_level("acid", name, description, tags),
        "body_level": infer_level("body", name, description, tags),
        "sweetness_level": infer_level("sweetness", name, description, tags),
        "bitter_level": infer_level("bitter", name, description, tags),
        "recommended_for": infer_recommended_for(name, description, tags),
        "decaf": infer_decaf(name, description, tags),
        "recommend_enabled": recommend_enabled,
        "available": True if available is None else bool(available),
        "todo": build_todos(sales_rank),
    }


def make_product_id(name: str) -> str:
    """Make a stable ASCII-ish product id from the product name."""

    normalized = name.lower()
    replacements = {
        "ブラジル": "brazil",
        "エチオピア": "ethiopia",
        "コロンビア": "colombia",
        "グアテマラ": "guatemala",
        "マンデリン": "mandheling",
        "ブレンド": "blend",
        "blend": "blend",
        "デカフェ": "decaf",
    }
    for source, replacement in replacements.items():
        normalized = normalized.replace(source, replacement)

    normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    if normalized:
        return f"{normalized}_{digest}"
    return f"product_{digest}"


def infer_category(name: str, tags: list[str]) -> str:
    """Infer a category when Square did not expose one."""

    text = " ".join([name, *tags])
    if "デカフェ" in text:
        return "デカフェ"
    if "ブレンド" in text or "BLEND" in text.upper():
        return "ブレンド"
    if "ワークショップ" in text:
        return "ワークショップ"
    if "定期便" in text:
        return "定期便"
    if "ギフト" in text:
        return "ギフト"
    if "ドリップバッグ" in text:
        return "ドリップバッグ"
    return "シングルオリジン"


def is_product_category(category: str) -> bool:
    """Return whether a Square category is already a product category."""

    return category in {"シングルオリジン", "ブレンド", "デカフェ", "ギフト", "ドリップバッグ", "ワークショップ", "定期便"}


def infer_roast(name: str, description: str, tags: list[str]) -> str:
    """Infer roast from Japanese labels, otherwise use City as a reviewable default."""

    name_text = name.upper()
    tag_text = " ".join(tags)

    if "シャキッソ" in name or "イルガチェフェ コチャレ Qグレード（ウォッシュト）" in name:
        return "Cinnamon"
    if "コチャレ（ナチュラル）" in name or "ジャガーハニー" in name:
        return "Light"

    if "ITALIAN" in name_text:
        return "Italian"
    if "FRENCH" in name_text or any(word in name_text for word in ["DEEP", "BITTER"]) or "深煎" in name:
        return "French"
    if "FULLCITY" in name_text or "FULL CITY" in name_text:
        return "Full City"
    if "CITY" in name_text:
        return "City"
    if "HIGH" in name_text:
        return "High"
    if "CINNAMON" in name_text:
        return "Cinnamon"
    if "LIGHT" in name_text:
        return "Light"
    if "浅煎り】 CINNAMON ROAST" in description or "シナモン〜ライトロースト" in description:
        return "Cinnamon"
    if "■ ライトロースト" in description or "【浅煎り】 LIGHT ROAST" in description:
        return "Light"
    if "アイス" in name and any(word in name_text for word in ["RICH", "SWEET"]):
        return "Full City"
    if "アイス" in name:
        return "City"
    if "BLEND" in name_text or "ブレンド" in name:
        return "Medium"
    if any(tag in tag_text for tag in ["すっきり", "華やか", "果実感"]):
        return "Medium"
    if any(tag in tag_text for tag in ["コク", "苦味"]):
        return "Full City"
    return "City"


def infer_decaf(name: str, description: str, tags: list[str]) -> bool:
    """Infer decaf status."""

    return ("ホンジュラス" in name and "デカフェ" in name) or "夜凪ブレンド" in name


def infer_workshop(name: str, description: str) -> bool:
    """Infer whether the product is a workshop."""

    return "ワークショップ" in f"{name} {description}"


def infer_subscription(name: str, description: str) -> bool:
    """Infer whether the product is a subscription."""

    text = f"{name} {description}"
    return "定期便" in text or "サブスク" in text or "subscription" in text.lower()


def infer_seasonal(name: str, description: str, tags: list[str]) -> bool:
    """Infer seasonal products."""

    text = " ".join([name, description, *tags])
    seasonal_words = [
        "Sakura",
        "さくら",
        "桜",
        "アイスブレンド",
        "ICE BLEND",
        "ニューイヤー",
        "秋",
        "雨の日",
        "ノエル",
        "クリスマス",
    ]
    return any(word.lower() in text.lower() for word in seasonal_words)


def infer_priority(name: str, description: str, tags: list[str], seasonal: bool, workshop: bool, subscription: bool) -> int:
    """Infer initial shop-controlled recommendation priority."""

    text = " ".join([name, description, *tags])
    priority = 100
    if "ブラジル" in text or "ホンジュラス SHG" in text:
        priority += 35
    if "ドリップバッグ" in text:
        priority += 15
    if seasonal:
        priority += 10
    if workshop or subscription:
        priority += 5
    if "⭐️個性派・スペシャル" in tags:
        priority += 8
    return priority


def infer_sales_rank(name: str) -> int | None:
    """Provide a reviewable initial sales rank until Square sales data is connected."""

    ranking = [
        "ブラジル",
        "ホンジュラス SHG",
        "さじまブレンド",
        "エチオピア",
        "ドリップバッグアソートBOX：３種",
        "ドリップバッグアソートBOX：４種",
        "ドリップバッグアソートBOX：６種",
        "ドリップバッグアソートBOX：２種",
    ]
    for index, keyword in enumerate(ranking, start=1):
        if keyword in name:
            return index
    return None


def infer_sales_score(sales_rank: int | None) -> int:
    """Convert a sales rank into a 0-100 score."""

    if sales_rank is None:
        return 0
    return max(0, 105 - sales_rank * 5)


def build_todos(sales_rank: int | None) -> list[str]:
    """Build review notes for generated product data."""

    todos = ["TODO: 診断公開前に味覚レベル、焙煎度、タグを人が確認してください。"]
    if sales_rank is None:
        todos.append("TODO: Squareオンラインと実店舗を合算したsales_rank/sales_scoreを確認してください。")
    return todos


def infer_flavor_tags(name: str, description: str, raw_tags: list[str]) -> list[str]:
    """Infer diagnosis-friendly flavor tags."""

    text = " ".join([name, description, *raw_tags])
    patterns = {
        "すっきり": ["すっきり", "スッキリ", "爽やか", "クリーン", "軽やか", "シャープ", "澄んだ"],
        "コク": ["コク", "ボディ", "重厚", "濃厚", "力強", "深み"],
        "甘み": ["甘み", "甘さ", "スイート", "チョコ", "キャラメル", "はちみつ", "蜜"],
        "苦味": ["苦味", "ビター"],
        "華やか": ["華やか", "フローラル", "花"],
        "果実感": ["フルーティ", "果実", "ベリー", "柑橘", "シトラス", "オレンジ", "マンダリン"],
        "ナッツ": ["ナッツ", "アーモンド"],
        "チョコ": ["チョコ", "カカオ"],
        "まろやか": ["まろやか", "丸い", "やわらか", "優しい", "穏やか"],
    }
    inferred = [tag for tag, needles in patterns.items() if any(needle in text for needle in needles)]
    tags = dedupe([*raw_tags, *inferred])
    if tags:
        return tags
    if "送料" in text:
        return ["送料"]
    if "ギフト" in text:
        return ["ギフト"]
    return ["その他"]


def infer_level(level_type: str, name: str, description: str, tags: list[str]) -> int:
    """Infer a 1-5 flavor level from text. This is a reviewable first draft."""

    text = " ".join([name, description, *tags])
    scores = {
        "acid": 3,
        "body": 3,
        "sweetness": 3,
        "bitter": 2,
    }

    if any(word in text for word in ["酸味", "柑橘", "シトラス", "ベリー", "フルーティ", "華やか"]):
        scores["acid"] += 1
    if any(word in text for word in ["明るい酸味", "爽やか", "シャープ"]):
        scores["acid"] += 1
    if any(word in text for word in ["穏やかな酸味", "酸味は穏やか", "酸味が少", "酸味を控え"]):
        scores["acid"] -= 2

    if any(word in text for word in ["コク", "ボディ", "重厚", "濃厚", "深み", "力強"]):
        scores["body"] += 1
    if any(word in text for word in ["深煎", "アイス", "マンデリン"]):
        scores["body"] += 1
    if any(word in text for word in ["軽やか", "すっきり", "スッキリ"]):
        scores["body"] -= 1

    if any(word in text for word in ["甘み", "甘さ", "スイート", "チョコ", "キャラメル", "はちみつ", "蜜"]):
        scores["sweetness"] += 1
    if any(word in text for word in ["芳醇", "熟した", "果実"]):
        scores["sweetness"] += 1

    if any(word in text for word in ["苦味", "ビター", "深煎", "カカオ"]):
        scores["bitter"] += 2
    if any(word in text for word in ["苦味は強くなく", "苦味は少", "苦味控え"]):
        scores["bitter"] -= 2

    return max(1, min(5, scores[level_type]))


def is_diagnosis_target(name: str, description: str) -> bool:
    """Return whether a product should be included in bean recommendations."""

    text = f"{name} {description}"
    excluded = ["送料", "ギフトボックス"]
    return not any(word in text for word in excluded)


def infer_recommended_for(name: str, description: str, tags: list[str]) -> list[str]:
    """Infer initial recommended_for labels from raw text."""

    text = " ".join([name, description, *tags])
    recommended: list[str] = []

    if "デカフェ" in text or "カフェインレス" in text:
        recommended.append("デカフェ")
    if "ギフト" in text:
        recommended.append("ギフト")
    if "ドリップバッグ" in text:
        recommended.append("ドリップバッグ")
    if "ミルク" in text or "深煎" in text:
        recommended.append("ミルク")
    if "アイス" in text:
        recommended.append("アイス")
    if "酸味" in text and ("穏やか" in text or "少な" in text or "控え" in text):
        recommended.append("酸味苦手")

    for default in ["ブラック", "自宅"]:
        if default not in recommended:
            recommended.append(default)

    return recommended


def dedupe(values: list[str]) -> list[str]:
    """Return unique strings in order."""

    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def string_or_default(value: Any, default: str) -> str:
    """Return non-empty string or default."""

    if value is None:
        return default
    text = str(value).strip()
    return text or default


def list_or_empty(value: Any) -> list[str]:
    """Return a list of non-empty strings."""

    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


if __name__ == "__main__":
    raise SystemExit(main())
