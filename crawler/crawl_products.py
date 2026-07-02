#!/usr/bin/env python3
"""Crawl Square product pages and write raw product data.

The crawler intentionally uses only the Python standard library so it can run
in a fresh GitHub-managed repository without dependency setup.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import ssl
import sys
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.error import URLError
from urllib.request import Request, urlopen


DEFAULT_OUTPUT = Path("raw_products.json")
USER_AGENT = "NagisaBeanNaviCrawler/1.0 (+https://github.com/)"


@dataclass
class RawProduct:
    """Raw product record before Bean Navi normalization."""

    name: str
    description: str | None
    price: int | None
    image_url: str | None
    product_url: str
    category: str | None
    available: bool | None
    tags: list[str] = field(default_factory=list)
    options: list[str] = field(default_factory=list)
    source: str = "square"


class ProductPageParser(HTMLParser):
    """Collects structured product hints from a Square product page."""

    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.meta: dict[str, str] = {}
        self.json_ld: list[dict[str, Any]] = []
        self._current_tag: str | None = None
        self._current_attrs: dict[str, str] = {}
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}

        if tag == "meta":
            key = attr_map.get("property") or attr_map.get("name")
            content = attr_map.get("content")
            if key and content:
                self.meta[key] = content

        if tag in {"title", "script"}:
            self._current_tag = tag
            self._current_attrs = attr_map
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._current_tag:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != self._current_tag:
            return

        content = "".join(self._buffer).strip()
        if tag == "title":
            self.title = content

        if tag == "script" and "ld+json" in self._current_attrs.get("type", ""):
            for item in parse_json_ld(content):
                self.json_ld.append(item)

        self._current_tag = None
        self._current_attrs = {}
        self._buffer = []


class LinkCollector(HTMLParser):
    """Collects candidate product links from a shop listing page."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return

        attr_map = {key: value or "" for key, value in attrs}
        href = attr_map.get("href")
        if not href:
            return

        absolute_url = urljoin(self.base_url, href)
        if looks_like_product_url(absolute_url):
            self.links.add(strip_fragment(absolute_url))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl Square product data into raw_products.json.")
    parser.add_argument("url", help="Square shop top page, category page, or product page URL.")
    parser.add_argument("-o", "--output", default=str(DEFAULT_OUTPUT), help="Output JSON path.")
    parser.add_argument("--max-pages", type=int, default=80, help="Maximum product pages to crawl.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start_url = args.url
    output_path = Path(args.output)

    try:
        square_products = crawl_square_online_api(start_url)
        if square_products:
            products = [asdict(product) for product in square_products]
        else:
            product_urls = discover_product_urls(start_url, args.max_pages)
            products = [asdict(crawl_product(url)) for url in product_urls]
    except Exception as exc:  # noqa: BLE001 - command line tool should surface context.
        print(f"crawl failed: {exc}", file=sys.stderr)
        return 1

    payload = {
        "source_url": start_url,
        "products": products,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(products)} products to {output_path}")
    return 0


def discover_product_urls(start_url: str, max_pages: int) -> list[str]:
    """Find product URLs from a listing page or return the given product URL."""

    if looks_like_product_url(start_url):
        return [start_url]

    html = fetch_text(start_url)
    collector = LinkCollector(start_url)
    collector.feed(html)
    urls = sorted(collector.links)
    return urls[:max_pages]


def crawl_product(product_url: str) -> RawProduct:
    """Fetch and parse one Square product page."""

    html = fetch_text(product_url)
    parser = ProductPageParser()
    parser.feed(html)

    product_data = first_product_json_ld(parser.json_ld)
    offers = normalize_offers(product_data.get("offers")) if product_data else {}

    name = text_or_none(product_data.get("name") if product_data else None)
    description = text_or_none(product_data.get("description") if product_data else None)
    image_url = image_from_json_ld(product_data) if product_data else None

    name = name or parser.meta.get("og:title") or parser.title or "Untitled product"
    description = description or parser.meta.get("og:description")
    image_url = image_url or parser.meta.get("og:image")

    category = text_or_none(product_data.get("category") if product_data else None)
    price = price_to_int(offers.get("price") or parser.meta.get("product:price:amount"))
    available = availability_to_bool(offers.get("availability") or parser.meta.get("product:availability"))
    tags = keywords_to_tags(parser.meta.get("keywords"))

    return RawProduct(
        name=clean_square_title(name),
        description=description,
        price=price,
        image_url=urljoin(product_url, image_url) if image_url else None,
        product_url=product_url,
        category=category,
        available=available,
        tags=tags,
        options=extract_options(html),
    )


def crawl_square_online_api(start_url: str) -> list[RawProduct]:
    """Fetch products from Square Online's public storefront API."""

    html_text = fetch_text(start_url)
    bootstrap = extract_bootstrap_state(html_text)
    if not bootstrap:
        return []

    site = bootstrap.get("siteData", {}).get("site", {})
    user = bootstrap.get("siteData", {}).get("user", {})
    properties = site.get("properties", {})
    user_id = str(user.get("id") or "")
    site_id = str(properties.get("classicSiteID") or properties.get("catalogSiteId") or "")
    if not user_id or not site_id:
        return []

    products: list[RawProduct] = []
    page = 1
    while True:
        payload = fetch_square_products(start_url, user_id, site_id, page)
        for item in payload.get("data", []):
            products.append(square_api_product_to_raw(item))

        pagination = payload.get("pagination") or payload.get("meta", {}).get("pagination") or {}
        total_pages = int(pagination.get("total_pages") or page)
        if page >= total_pages:
            break
        page += 1

    return products


def fetch_square_products(start_url: str, user_id: str, site_id: str, page: int) -> dict[str, Any]:
    """Fetch one page of products from Square Online's storefront API."""

    base_url = f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}"
    params = {
        "page": page,
        "per_page": 100,
        "include": "images,media_files,discounts,category,skus",
    }
    query = "&".join(f"{key}={quote_value(value)}" for key, value in params.items())
    api_url = f"{base_url}/app/store/api/v28/editor/users/{user_id}/sites/{site_id}/products?{query}"
    return json.loads(fetch_text(api_url))


def square_api_product_to_raw(item: dict[str, Any]) -> RawProduct:
    """Convert a Square Online API product into a raw product record."""

    category = nested_text(item, ["category", "data", "name"])
    tags = [category] if category else []
    tags.extend(infer_tags_from_text(f"{item.get('name', '')} {strip_html(item.get('short_description') or '')}"))

    return RawProduct(
        name=text_or_none(item.get("name")) or "Untitled product",
        description=strip_html(item.get("short_description") or item.get("description") or ""),
        price=square_price_to_int(item.get("price")),
        image_url=square_image_url(item),
        product_url=text_or_none(item.get("absolute_site_link")) or "",
        category=category,
        available=item.get("visibility") == "visible",
        tags=dedupe(tags),
        options=square_options(item),
    )


def fetch_text(url: str) -> str:
    """Fetch a URL and decode it as text."""

    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    except URLError as exc:
        if not is_certificate_error(exc):
            raise
        context = ssl._create_unverified_context()
        with urlopen(request, timeout=20, context=context) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def extract_bootstrap_state(content: str) -> dict[str, Any]:
    """Extract window.__BOOTSTRAP_STATE__ from a Square Online page."""

    marker = "window.__BOOTSTRAP_STATE__ = "
    if marker not in content:
        return {}

    start = content.index(marker) + len(marker)
    level = 0
    in_string = False
    escaped = False
    for index, char in enumerate(content[start:], start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            level += 1
        elif char == "}":
            level -= 1
            if level == 0:
                return json.loads(content[start : index + 1])

    return {}


def is_certificate_error(exc: URLError) -> bool:
    """Return whether urllib failed because local certificate verification failed."""

    reason = getattr(exc, "reason", None)
    return isinstance(reason, ssl.SSLCertVerificationError)


def parse_json_ld(content: str) -> list[dict[str, Any]]:
    """Parse one JSON-LD block into a flat list of dictionaries."""

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    items = data if isinstance(data, list) else [data]
    flattened: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        graph = item.get("@graph")
        if isinstance(graph, list):
            flattened.extend([entry for entry in graph if isinstance(entry, dict)])
        flattened.append(item)
    return flattened


def first_product_json_ld(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the first JSON-LD Product object."""

    for item in items:
        item_type = item.get("@type")
        if item_type == "Product" or (isinstance(item_type, list) and "Product" in item_type):
            return item
    return {}


def normalize_offers(offers: Any) -> dict[str, Any]:
    """Normalize JSON-LD offers to one dictionary."""

    if isinstance(offers, list):
        return offers[0] if offers and isinstance(offers[0], dict) else {}
    return offers if isinstance(offers, dict) else {}


def image_from_json_ld(product_data: dict[str, Any]) -> str | None:
    """Extract an image URL from JSON-LD Product data."""

    image = product_data.get("image")
    if isinstance(image, str):
        return image
    if isinstance(image, list) and image:
        first = image[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return text_or_none(first.get("url"))
    if isinstance(image, dict):
        return text_or_none(image.get("url"))
    return None


def price_to_int(value: Any) -> int | None:
    """Convert a price-like value to integer yen."""

    if value is None:
        return None
    match = re.search(r"\d+(?:[,.]\d+)?", str(value).replace(",", ""))
    if not match:
        return None
    return int(float(match.group(0)))


def availability_to_bool(value: Any) -> bool | None:
    """Convert schema.org or Square availability text to a boolean."""

    if value is None:
        return None
    normalized = str(value).lower()
    if "instock" in normalized or "in stock" in normalized or "available" in normalized:
        return True
    if "outofstock" in normalized or "sold out" in normalized or "unavailable" in normalized:
        return False
    return None


def keywords_to_tags(value: str | None) -> list[str]:
    """Split meta keywords into tags."""

    if not value:
        return []
    return [tag.strip() for tag in re.split(r"[,、]", value) if tag.strip()]


def extract_options(html: str) -> list[str]:
    """Extract simple option labels from embedded page text."""

    options: set[str] = set()
    for label in ["豆", "粉", "100g", "200g", "ギフト", "定期便"]:
        if label in html:
            options.add(label)
    return sorted(options)


def square_options(item: dict[str, Any]) -> list[str]:
    """Extract option labels from Square SKU names."""

    skus = item.get("skus", {}).get("data", []) if isinstance(item.get("skus"), dict) else []
    labels = [text_or_none(sku.get("name")) for sku in skus if isinstance(sku, dict)]
    return dedupe([label for label in labels if label])


def square_image_url(item: dict[str, Any]) -> str | None:
    """Return the best product image URL from Square API data."""

    images = item.get("images", {}).get("data", []) if isinstance(item.get("images"), dict) else []
    if images:
        first = images[0]
        urls = first.get("urls") if isinstance(first, dict) else {}
        return (
            text_or_none(urls.get("1280") if isinstance(urls, dict) else None)
            or text_or_none(first.get("absolute_url"))
            or text_or_none(first.get("url"))
        )
    thumbnail = item.get("thumbnail")
    if isinstance(thumbnail, dict):
        return text_or_none(thumbnail.get("absolute_url") or thumbnail.get("url"))
    return None


def square_price_to_int(price: Any) -> int | None:
    """Convert Square price object to integer yen."""

    if isinstance(price, dict):
        return price_to_int(price.get("low") or price.get("current") or price.get("regular_low"))
    return price_to_int(price)


def strip_html(value: str) -> str:
    """Convert simple HTML descriptions to plain text."""

    without_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(without_tags).split())


def infer_tags_from_text(text: str) -> list[str]:
    """Extract coarse flavor tags from Japanese product text."""

    tag_patterns = {
        "すっきり": ["すっきり", "スッキリ", "爽やか", "クリーン", "軽やか", "シャープ"],
        "コク": ["コク", "ボディ", "重厚", "濃厚", "力強"],
        "甘み": ["甘み", "甘さ", "スイート", "チョコ", "キャラメル", "はちみつ", "蜜"],
        "苦味": ["苦味", "ビター", "深み"],
        "華やか": ["華やか", "フローラル", "花"],
        "果実感": ["フルーティ", "果実", "ベリー", "柑橘", "シトラス", "オレンジ"],
        "ナッツ": ["ナッツ", "アーモンド"],
        "チョコ": ["チョコ", "カカオ"],
        "まろやか": ["まろやか", "丸い", "やわらか"],
    }
    return [tag for tag, needles in tag_patterns.items() if any(needle in text for needle in needles)]


def nested_text(value: dict[str, Any], keys: list[str]) -> str | None:
    """Read a nested text value from dictionaries."""

    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return text_or_none(current)


def quote_value(value: Any) -> str:
    """URL-encode a query value without importing a larger helper."""

    from urllib.parse import quote

    return quote(str(value), safe="")


def dedupe(values: list[str]) -> list[str]:
    """Return unique non-empty values in order."""

    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def looks_like_product_url(url: str) -> bool:
    """Heuristic for Square product URLs."""

    path = urlparse(url).path.lower()
    return any(marker in path for marker in ["/product/", "/item/", "/s/shop/", "/shop/"])


def strip_fragment(url: str) -> str:
    """Remove URL fragments for stable de-duplication."""

    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def clean_square_title(value: str) -> str:
    """Remove common shop-name suffixes from a page title fallback."""

    return re.split(r"\s+[|｜-]\s+", value, maxsplit=1)[0].strip()


def text_or_none(value: Any) -> str | None:
    """Return stripped text or None."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


if __name__ == "__main__":
    raise SystemExit(main())
