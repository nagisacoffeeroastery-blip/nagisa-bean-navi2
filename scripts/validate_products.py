#!/usr/bin/env python3
"""Validate products.json for the Bean Navi static app."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PRODUCTS_PATH = Path("products.json")
REQUIRED_FIELDS = {
    "id": str,
    "name": str,
    "category": str,
    "roast": str,
    "description": str,
    "price": int,
    "image_url": str,
    "square_url": str,
    "seasonal": bool,
    "priority": int,
    "workshop": bool,
    "subscription": bool,
    "sales_score": int,
    "flavor_tags": list,
    "acid_level": int,
    "body_level": int,
    "sweetness_level": int,
    "bitter_level": int,
    "recommended_for": list,
    "decaf": bool,
    "recommend_enabled": bool,
    "available": bool,
}
LEVEL_FIELDS = ["acid_level", "body_level", "sweetness_level", "bitter_level"]
ROASTS = {"Light", "Cinnamon", "Medium", "High", "City", "Full City", "French", "Italian"}
DECAF_PRODUCT_NAMES = {
    "ホンジュラス　デカフェ JASオーガニック",
    "夜凪ブレンド30",
    "夜凪ブレンド50",
    "夜凪ブレンド70",
}


def main() -> int:
    errors = validate_products(PRODUCTS_PATH)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    products = load_products(PRODUCTS_PATH)
    enabled_count = sum(1 for product in products if product["recommend_enabled"] and product["available"])
    print(f"Validated {len(products)} products ({enabled_count} recommendable).")
    return 0


def validate_products(path: Path) -> list[str]:
    """Validate product records and return human-readable errors."""

    errors: list[str] = []
    try:
        products = load_products(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [str(exc)]

    seen_ids: set[str] = set()
    recommendable_count = 0
    drip_bag_count = 0

    for index, product in enumerate(products):
        label = f"products[{index}]"
        if not isinstance(product, dict):
            errors.append(f"{label} must be an object.")
            continue

        product_id = product.get("id", f"index-{index}")
        product_label = f"{label} ({product_id})"
        errors.extend(validate_required_fields(product, product_label))

        if isinstance(product.get("id"), str):
            if product["id"] in seen_ids:
                errors.append(f"{product_label}: duplicate id.")
            seen_ids.add(product["id"])

        errors.extend(validate_levels(product, product_label))
        errors.extend(validate_string_list(product, "flavor_tags", product_label))
        errors.extend(validate_string_list(product, "recommended_for", product_label))
        errors.extend(validate_url(product, "square_url", product_label))
        errors.extend(validate_url(product, "image_url", product_label))

        if product.get("roast") not in ROASTS:
            errors.append(f"{product_label}: roast must be one of {sorted(ROASTS)}.")

        if isinstance(product.get("price"), int) and product["price"] < 0:
            errors.append(f"{product_label}: price must be 0 or greater.")
        if isinstance(product.get("priority"), int) and product["priority"] < 0:
            errors.append(f"{product_label}: priority must be 0 or greater.")
        if isinstance(product.get("sales_score"), int) and not 0 <= product["sales_score"] <= 100:
            errors.append(f"{product_label}: sales_score must be from 0 to 100.")
        if product.get("sales_rank") is not None and not isinstance(product.get("sales_rank"), int):
            errors.append(f"{product_label}: sales_rank must be an integer or null.")
        if isinstance(product.get("sales_rank"), int) and product["sales_rank"] < 1:
            errors.append(f"{product_label}: sales_rank must be 1 or greater.")

        if product.get("recommend_enabled") and product.get("available"):
            recommendable_count += 1

        if "ドリップバッグ" in str(product.get("name", "")):
            drip_bag_count += 1
            if product.get("recommend_enabled") is not True:
                errors.append(f"{product_label}: drip bag products must be recommend_enabled=true.")
            if "ドリップバッグ" not in product.get("recommended_for", []):
                errors.append(f"{product_label}: drip bag products must include recommended_for 'ドリップバッグ'.")
        if "ワークショップ" in str(product.get("name", "")) and product.get("workshop") is not True:
            errors.append(f"{product_label}: workshop products must have workshop=true.")
        if "定期便" in str(product.get("name", "")) and product.get("subscription") is not True:
            errors.append(f"{product_label}: subscription products must have subscription=true.")
        if product.get("decaf") is not (product.get("name") in DECAF_PRODUCT_NAMES):
            errors.append(f"{product_label}: decaf must be true only for the approved decaf products.")

    if not products:
        errors.append("products must contain at least one item.")
    if recommendable_count < 3:
        errors.append("at least 3 available recommendable products are required.")
    if drip_bag_count < 1:
        errors.append("at least one drip bag product is expected.")

    return errors


def load_products(path: Path) -> list[dict[str, Any]]:
    """Load products from products.json."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    products = payload if isinstance(payload, list) else payload.get("products")
    if not isinstance(products, list):
        raise ValueError("products.json must contain a products array.")
    return products


def validate_required_fields(product: dict[str, Any], product_label: str) -> list[str]:
    """Validate presence and basic type of required fields."""

    errors: list[str] = []
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in product:
            errors.append(f"{product_label}: missing required field '{field}'.")
            continue
        if not isinstance(product[field], expected_type):
            errors.append(f"{product_label}: field '{field}' must be {expected_type.__name__}.")
    return errors


def validate_levels(product: dict[str, Any], product_label: str) -> list[str]:
    """Validate flavor level fields."""

    errors: list[str] = []
    for field in LEVEL_FIELDS:
        value = product.get(field)
        if isinstance(value, int) and 1 <= value <= 5:
            continue
        errors.append(f"{product_label}: {field} must be an integer from 1 to 5.")
    return errors


def validate_string_list(product: dict[str, Any], field: str, product_label: str) -> list[str]:
    """Validate a field is a list of non-empty strings."""

    value = product.get(field)
    if not isinstance(value, list):
        return [f"{product_label}: {field} must be a list."]
    if not value:
        return [f"{product_label}: {field} must not be empty."]
    invalid = [item for item in value if not isinstance(item, str) or not item.strip()]
    if invalid:
        return [f"{product_label}: {field} must contain only non-empty strings."]
    return []


def validate_url(product: dict[str, Any], field: str, product_label: str) -> list[str]:
    """Validate URL-like fields."""

    value = product.get(field)
    if not isinstance(value, str) or not value.strip():
        return [f"{product_label}: {field} must be a non-empty URL."]
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return [f"{product_label}: {field} must be an absolute http(s) URL."]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
