#!/usr/bin/env python3
"""Crawl Tong Ren Tang product listings into structured JSON / JSONL / CSV.

Default source is the 中成药 category page provided by the user:
https://www.tongrentang.com/jtProductList/d502e93816624e6780a8e959701ec3af/1.html
"""

from __future__ import annotations

import argparse
import csv
import html as html_lib
import json
import re
import sys
import time
from collections import Counter
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlparse

BASE = "https://www.tongrentang.com"
DEFAULT_CATEGORY_ID = "d502e93816624e6780a8e959701ec3af"
DEFAULT_CATEGORY_NAME = "中成药"
USER_AGENT = (
    "Mozilla/5.0 (compatible; TongRenTangCatalogResearch/1.0; "
    "+https://www.tongrentang.com)"
)

ATTR_KEY_MAP = {
    "产品名称": "name",
    "品类": "category",
    "包装规格": "specification",
    "剂型": "dosage_form",
    "药品上市许可持有人": "marketing_authorization_holder",
    "功能主治": "indications",
    "生产企业": "manufacturer",
    "生产地址": "production_address",
    "保健功能": "health_function",
    "委托企业": "entrusting_enterprise",
    "受托企业": "entrusted_enterprise",
    "批准文号": "approval_number",
    "执行标准": "standard",
    "用法用量": "usage",
    "成分": "ingredients",
    "主要原料": "main_ingredients",
    "适宜人群": "suitable_crowd",
    "不适宜人群": "unsuitable_crowd",
    "注意事项": "precautions",
    "贮藏": "storage",
}

KNOWN_OUTPUT_FIELDS = [
    "id",
    "name",
    "category",
    "category_id",
    "specification",
    "dosage_form",
    "marketing_authorization_holder",
    "indications",
    "manufacturer",
    "production_address",
    "health_function",
    "entrusting_enterprise",
    "entrusted_enterprise",
    "approval_number",
    "standard",
    "usage",
    "ingredients",
    "main_ingredients",
    "suitable_crowd",
    "unsuitable_crowd",
    "precautions",
    "storage",
    "title",
    "list_image",
    "list_image_local",
    "detail_url",
    "list_page",
    "images",
    "images_local",
    "brand_logos",
    "brand_logos_local",
    "attributes",
    "extra_attributes",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, retries: int = 5, timeout: int = 30) -> str:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, "replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 16))
    raise RuntimeError(f"failed to fetch {url}: {last_error}") from last_error


def encode_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(path=quote(parsed.path, safe="/-_.~")).geturl()


def fetch_bytes(url: str, retries: int = 5, timeout: int = 90) -> tuple[bytes, str]:
    last_error: Exception | None = None
    encoded = encode_url(url)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(encoded, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                content_type = (response.headers.get_content_type() or "").lower()
                data = response.read()
                return data, content_type
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 16))
    raise RuntimeError(f"failed to download {url}: {last_error}") from last_error


def url_to_image_relpath(url: str) -> str:
    parsed = urlparse(url)
    path = unquote(parsed.path).lstrip("/")
    path = path.replace(" ", "_")
    if not path:
        digest = sha256(url.encode("utf-8")).hexdigest()[:16]
        path = f"misc/{digest}"
    if parsed.query:
        digest = sha256(parsed.query.encode("utf-8")).hexdigest()[:8]
        suffix = Path(path).suffix
        path = f"{path[: -len(suffix)] if suffix else path}_{digest}{suffix}"
    return path


def unescape_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    text = html_lib.unescape(text)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def parse_total_pages(html: str) -> int:
    match = re.search(r"共(\d+)页", html)
    if match:
        return int(match.group(1))
    return 1


def parse_list_items(html: str, page: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    pattern = re.compile(
        r'<div class="item-cell">\s*'
        r'<div class="item-pic"><a href="([^"]+)"><img src="([^"]+)" alt="([^"]*)"></a></div>\s*'
        r'<div class="item-tit">\s*'
        r'<a href="[^"]+">([^<]*)</a>\s*'
        r"<span>(?:<!--.*?-->)?([^<]*)</span>",
        re.S,
    )
    for href, image, alt, name, spec in pattern.findall(html):
        detail_url = href if href.startswith("http") else urljoin(BASE, href)
        product_id_match = re.search(r"/jtProDetail/([a-f0-9]+)\.html", detail_url)
        if not product_id_match:
            continue
        product_id = product_id_match.group(1)
        if product_id in seen:
            continue
        seen.add(product_id)
        items.append(
            {
                "id": product_id,
                "name": unescape_text(name) or unescape_text(alt),
                "specification": unescape_text(spec),
                "list_image": image if image.startswith("http") else urljoin(BASE, image),
                "detail_url": detail_url,
                "list_page": page,
            }
        )
    return items


def parse_detail(html: str) -> dict[str, Any]:
    title_match = re.search(r'class="prortits20">([^<]+)', html)
    title = unescape_text(title_match.group(1)) if title_match else ""

    attributes: dict[str, str] = {}
    for raw_key, raw_value in re.findall(
        r"<li>\s*<span>([^<]+)</span>\s*<cite>([\s\S]*?)</cite>", html
    ):
        key = unescape_text(raw_key).rstrip("：:")
        value = unescape_text(raw_value)
        if key:
            attributes[key] = value

    images: list[str] = []
    for src in re.findall(
        r'<div class="swiper-slide">\s*<img src="([^"]+)"', html
    ):
        url = src if src.startswith("http") else urljoin(BASE, src)
        if url not in images:
            images.append(url)

    brand_logos: list[str] = []
    for src in re.findall(r'class="bsimg"><img src="([^"]+)"', html):
        url = src if src.startswith("http") else urljoin(BASE, src)
        if url not in brand_logos:
            brand_logos.append(url)

    mapped: dict[str, Any] = {}
    extra: dict[str, str] = {}
    for key, value in attributes.items():
        field = ATTR_KEY_MAP.get(key)
        if field:
            mapped[field] = value
        else:
            extra[key] = value

    return {
        "title": title,
        "images": images,
        "brand_logos": brand_logos,
        "attributes": attributes,
        "extra_attributes": extra,
        **mapped,
    }


def collect_list(category_id: str, workers: int) -> tuple[str, int, list[dict[str, Any]]]:
    first_url = f"{BASE}/jtProductList/{category_id}/1.html"
    first_html = fetch(first_url)
    total_pages = parse_total_pages(first_html)

    category_name = DEFAULT_CATEGORY_NAME
    cat_match = re.search(r"<em>([^<]+)</em>", first_html)
    if cat_match:
        category_name = unescape_text(cat_match.group(1))

    items = parse_list_items(first_html, 1)
    print(f"category={category_name} pages={total_pages} page=1 items={len(items)}", flush=True)

    if total_pages > 1:
        urls = [
            (page, f"{BASE}/jtProductList/{category_id}/{page}.html")
            for page in range(2, total_pages + 1)
        ]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fetch, url): page for page, url in urls}
            for future in as_completed(futures):
                page = futures[future]
                html = future.result()
                page_items = parse_list_items(html, page)
                items.extend(page_items)
                print(f"page={page} items={len(page_items)}", flush=True)

    items.sort(key=lambda row: (row["list_page"], row["name"], row["id"]))
    return category_name, total_pages, items


def merge_product(list_item: dict[str, Any], detail: dict[str, Any], category_id: str, category_name: str) -> dict[str, Any]:
    product: dict[str, Any] = {
        "id": list_item["id"],
        "name": detail.get("name") or list_item["name"],
        "title": detail.get("title") or list_item["name"],
        "category": detail.get("category") or category_name,
        "category_id": category_id,
        "specification": detail.get("specification") or list_item["specification"],
        "list_image": list_item["list_image"],
        "detail_url": list_item["detail_url"],
        "list_page": list_item["list_page"],
        "images": detail.get("images") or ([list_item["list_image"]] if list_item["list_image"] else []),
        "brand_logos": detail.get("brand_logos") or [],
        "attributes": detail.get("attributes") or {},
        "extra_attributes": detail.get("extra_attributes") or {},
    }
    for field in ATTR_KEY_MAP.values():
        if field in ("name", "category", "specification"):
            continue
        if field in detail:
            product[field] = detail[field]
    return product


def scrape_details(items: list[dict[str, Any]], category_id: str, category_name: str, workers: int) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    def load(item: dict[str, Any]) -> dict[str, Any]:
        html = fetch(item["detail_url"])
        return merge_product(item, parse_detail(html), category_id, category_name)

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(load, item): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            completed += 1
            try:
                products.append(future.result())
            except Exception as exc:  # noqa: BLE001
                errors.append({"id": item["id"], "url": item["detail_url"], "error": str(exc)})
                products.append(
                    merge_product(item, {"title": item["name"], "images": [], "brand_logos": [], "attributes": {}, "extra_attributes": {"_fetch_error": str(exc)}}, category_id, category_name)
                )
            if completed % 25 == 0 or completed == len(items):
                print(f"details {completed}/{len(items)}", flush=True)

    products.sort(key=lambda row: (row["list_page"], row["name"], row["id"]))
    if errors:
        print(f"warning: {len(errors)} detail pages failed", flush=True)
    return products


def collect_image_urls(products: list[dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for product in products:
        candidates = [product.get("list_image"), *(product.get("images") or []), *(product.get("brand_logos") or [])]
        for url in candidates:
            if not url or url in seen:
                continue
            seen.add(url)
            urls.append(url)
    return urls


def download_images(urls: list[str], images_dir: Path, workers: int) -> dict[str, dict[str, Any]]:
    images_dir.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, dict[str, Any]] = {}

    def save(url: str) -> dict[str, Any]:
        relpath = url_to_image_relpath(url)
        dest = images_dir / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0:
            data = dest.read_bytes()
            return {
                "url": url,
                "local_path": f"images/{relpath}",
                "bytes": dest.stat().st_size,
                "sha256": sha256(data).hexdigest(),
                "status": "exists",
            }
        data, content_type = fetch_bytes(url)
        if not data:
            raise RuntimeError("empty response")
        if content_type and not content_type.startswith("image/") and not content_type.startswith("application/octet-stream"):
            raise RuntimeError(f"unexpected content-type {content_type}")
        dest.write_bytes(data)
        return {
            "url": url,
            "local_path": f"images/{relpath}",
            "bytes": len(data),
            "sha256": sha256(data).hexdigest(),
            "content_type": content_type,
            "status": "ok",
        }

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(save, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            completed += 1
            try:
                mapping[url] = future.result()
            except Exception as exc:  # noqa: BLE001
                mapping[url] = {
                    "url": url,
                    "local_path": None,
                    "status": "error",
                    "error": str(exc),
                }
            if completed % 25 == 0 or completed == len(urls):
                print(f"images {completed}/{len(urls)}", flush=True)
    return mapping


def attach_local_images(products: list[dict[str, Any]], mapping: dict[str, dict[str, Any]]) -> None:
    def local_of(url: str | None) -> str | None:
        if not url:
            return None
        return mapping.get(url, {}).get("local_path")

    for product in products:
        product["list_image_local"] = local_of(product.get("list_image"))
        product["images_local"] = [path for path in (local_of(url) for url in product.get("images") or []) if path]
        product["brand_logos_local"] = [path for path in (local_of(url) for url in product.get("brand_logos") or []) if path]


def write_outputs(out_dir: Path, catalog: dict[str, Any], products: list[dict[str, Any]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    catalog_path = out_dir / "catalog.json"
    products_json = out_dir / "products.json"
    products_jsonl = out_dir / "products.jsonl"
    products_csv = out_dir / "products.csv"
    schema_path = out_dir / "schema.json"

    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    products_json.write_text(json.dumps(products, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with products_jsonl.open("w", encoding="utf-8") as handle:
        for product in products:
            handle.write(json.dumps(product, ensure_ascii=False) + "\n")

    fieldnames = list(KNOWN_OUTPUT_FIELDS)
    extra_keys: set[str] = set()
    for product in products:
        extra_keys.update(product.keys())
    for key in sorted(extra_keys):
        if key not in fieldnames:
            fieldnames.append(key)

    with products_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for product in products:
            row = {}
            for key in fieldnames:
                value = product.get(key, "")
                if isinstance(value, (list, dict)):
                    row[key] = json.dumps(value, ensure_ascii=False)
                else:
                    row[key] = value if value is not None else ""
            writer.writerow(row)

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "TongRenTangProduct",
        "type": "object",
        "required": ["id", "name", "detail_url"],
        "properties": {
            "id": {"type": "string", "description": "详情页 URL 中的产品 ID"},
            "name": {"type": "string", "description": "产品名称"},
            "title": {"type": "string", "description": "详情页标题"},
            "category": {"type": "string", "description": "品类，如中成药"},
            "category_id": {"type": "string", "description": "列表页品类 ID"},
            "specification": {"type": "string", "description": "包装规格"},
            "dosage_form": {"type": "string", "description": "剂型"},
            "marketing_authorization_holder": {"type": "string", "description": "药品上市许可持有人"},
            "indications": {"type": "string", "description": "功能主治"},
            "manufacturer": {"type": "string", "description": "生产企业"},
            "production_address": {"type": "string", "description": "生产地址"},
            "health_function": {"type": "string", "description": "保健功能"},
            "list_image": {"type": "string", "format": "uri"},
            "list_image_local": {"type": ["string", "null"], "description": "相对 data/tongrentang 的本地封面图路径"},
            "detail_url": {"type": "string", "format": "uri"},
            "list_page": {"type": "integer"},
            "images": {"type": "array", "items": {"type": "string", "format": "uri"}},
            "images_local": {"type": "array", "items": {"type": "string"}, "description": "详情图本地路径"},
            "brand_logos": {"type": "array", "items": {"type": "string", "format": "uri"}},
            "brand_logos_local": {"type": "array", "items": {"type": "string"}, "description": "商标图本地路径"},
            "attributes": {"type": "object", "additionalProperties": {"type": "string"}, "description": "详情页原始键值"},
            "extra_attributes": {"type": "object", "additionalProperties": {"type": "string"}, "description": "未映射到标准字段的属性"},
        },
    }
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Tong Ren Tang product catalog")
    parser.add_argument("--category-id", default=DEFAULT_CATEGORY_ID)
    parser.add_argument("--out-dir", default="data/tongrentang")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--list-only", action="store_true", help="only crawl listing pages")
    parser.add_argument("--from-json", help="reuse an existing products.json and skip HTML crawl")
    parser.add_argument("--download-images", action="store_true", help="download product and brand images")
    parser.add_argument("--skip-images", action="store_true", help="do not download images")
    return parser.parse_args()


def build_catalog(products: list[dict[str, Any]], args: argparse.Namespace, category_name: str, total_pages: int, started: str, image_stats: dict[str, Any] | None) -> dict[str, Any]:
    def coverage(field: str) -> int:
        return sum(1 for product in products if product.get(field))

    catalog = {
        "source": f"{BASE}/jtProductList/{args.category_id}/1.html",
        "site": BASE,
        "site_name": "中国北京同仁堂（集团）有限责任公司",
        "section": "同仁堂双龙标产品",
        "category": category_name,
        "category_id": args.category_id,
        "total_pages": total_pages,
        "product_count": len(products),
        "unique_product_names": len({product["name"] for product in products}),
        "scraped_at": now_iso(),
        "started_at": started,
        "list_only": bool(args.list_only),
        "field_coverage": {
            field: coverage(field)
            for field in [
                "name",
                "specification",
                "dosage_form",
                "marketing_authorization_holder",
                "indications",
                "manufacturer",
                "production_address",
                "images",
                "brand_logos",
                "list_image_local",
                "images_local",
                "brand_logos_local",
            ]
        },
        "top_manufacturers": [
            {"name": name, "count": count}
            for name, count in Counter(product.get("manufacturer", "") for product in products).most_common(10)
            if name
        ],
        "dosage_forms": [
            {"name": name, "count": count}
            for name, count in Counter(product.get("dosage_form", "") for product in products).most_common()
            if name
        ],
    }
    if image_stats:
        catalog["image_download"] = image_stats
    return catalog


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    started = now_iso()
    should_download_images = args.download_images or (bool(args.from_json) and not args.skip_images)

    if args.from_json:
        products_path = Path(args.from_json)
        products = json.loads(products_path.read_text(encoding="utf-8"))
        existing_catalog = {}
        catalog_path = products_path.parent / "catalog.json"
        if catalog_path.exists():
            existing_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        category_name = existing_catalog.get("category") or DEFAULT_CATEGORY_NAME
        total_pages = int(existing_catalog.get("total_pages") or 0)
        args.category_id = existing_catalog.get("category_id") or args.category_id
        print(f"loaded {len(products)} products from {products_path}", flush=True)
    else:
        category_name, total_pages, items = collect_list(args.category_id, args.workers)
        print(f"list complete: {len(items)} products across {total_pages} pages", flush=True)

        if args.list_only:
            products = [
                merge_product(item, {"title": item["name"], "images": [item["list_image"]], "brand_logos": [], "attributes": {}, "extra_attributes": {}}, args.category_id, category_name)
                for item in items
            ]
        else:
            products = scrape_details(items, args.category_id, category_name, args.workers)
        should_download_images = args.download_images and not args.skip_images

    image_stats = None
    if should_download_images:
        urls = collect_image_urls(products)
        print(f"downloading {len(urls)} unique images", flush=True)
        mapping = download_images(urls, out_dir / "images", args.workers)
        attach_local_images(products, mapping)
        ok = sum(1 for item in mapping.values() if item.get("status") in {"ok", "exists"})
        failed = [item for item in mapping.values() if item.get("status") == "error"]
        total_bytes = sum(int(item.get("bytes") or 0) for item in mapping.values())
        image_stats = {
            "unique_urls": len(urls),
            "downloaded": ok,
            "failed": len(failed),
            "bytes": total_bytes,
            "directory": "images",
        }
        manifest_path = out_dir / "images_manifest.json"
        manifest_path.write_text(
            json.dumps(sorted(mapping.values(), key=lambda item: item.get("url") or ""), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"images downloaded={ok} failed={len(failed)} bytes={total_bytes}", flush=True)

    catalog = build_catalog(products, args, category_name, total_pages, started, image_stats)
    write_outputs(out_dir, catalog, products)
    print(f"wrote {len(products)} products to {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
