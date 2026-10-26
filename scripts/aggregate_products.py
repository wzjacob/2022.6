#!/usr/bin/env python3
"""Aggregate Tong Ren Tang SKUs into product-level records with primary/secondary fields."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

FEATURED_NAMES = [
    "安宫牛黄丸",
    "六味地黄丸",
    "同仁乌鸡白凤丸",
    "金匮肾气丸",
    "同仁牛黄清心丸",
    "同仁大活络丸",
    "国公酒",
    "阿胶",
]


def family_name(name: str) -> str:
    text = name.strip()
    text = re.sub(r"^【同仁堂】", "", text)
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    return re.sub(r"\s+", "", text)


def most_common_text(values: list[str]) -> str:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        return ""
    return Counter(cleaned).most_common(1)[0][0]


def unique_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def local_to_public(path: str | None) -> str | None:
    if not path:
        return None
    return path.removeprefix("images/")


def summary_from(indications: str) -> str:
    if not indications:
        return ""
    first = re.split(r"[。；;]", indications, maxsplit=1)[0].strip()
    return first


def aggregate(products: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for product in products:
        groups[family_name(product["name"])].append(product)

    aggregated: list[dict[str, Any]] = []
    for name, skus in groups.items():
        skus = sorted(skus, key=lambda item: (item.get("list_page") or 0, item.get("specification") or "", item["id"]))
        indications_list = [item.get("indications") or "" for item in skus]
        indications = most_common_text(indications_list)
        indication_variants = unique_keep_order([text for text in indications_list if text and text != indications])
        aliases = unique_keep_order([item["name"] for item in skus if item["name"] != name])
        dosage_forms = unique_keep_order([item.get("dosage_form") or "" for item in skus])
        manufacturers = unique_keep_order([item.get("manufacturer") or "" for item in skus])
        holders = unique_keep_order([item.get("marketing_authorization_holder") or "" for item in skus])

        gallery: list[dict[str, str]] = []
        seen_images: set[str] = set()
        for item in skus:
            urls = [item.get("list_image"), *(item.get("images") or [])]
            locals_ = [item.get("list_image_local"), *(item.get("images_local") or [])]
            for url, local in zip(urls, locals_ + [None] * len(urls)):
                if not url or url in seen_images:
                    continue
                seen_images.add(url)
                gallery.append({"url": url, "local": local_to_public(local) or ""})

        cover = gallery[0] if gallery else {"url": "", "local": ""}
        sku_records = []
        for item in skus:
            sku_records.append(
                {
                    "id": item["id"],
                    "listed_name": item["name"],
                    "specification": item.get("specification") or "",
                    "dosage_form": item.get("dosage_form") or "",
                    "indications": item.get("indications") or "",
                    "manufacturer": item.get("manufacturer") or "",
                    "marketing_authorization_holder": item.get("marketing_authorization_holder") or "",
                    "production_address": item.get("production_address") or "",
                    "detail_url": item.get("detail_url") or "",
                    "cover": item.get("list_image") or "",
                    "cover_local": local_to_public(item.get("list_image_local")),
                    "images": item.get("images") or [],
                }
            )

        aggregated.append(
            {
                "id": name,
                "name": name,
                "aliases": aliases,
                "category": most_common_text([item.get("category") or "" for item in skus]) or "中成药",
                "summary": summary_from(indications),
                "indications": indications,
                "indication_variants": indication_variants,
                "dosage_forms": dosage_forms,
                "manufacturers": manufacturers,
                "authorization_holders": holders,
                "sku_count": len(skus),
                "image_count": len(gallery),
                "featured": name in FEATURED_NAMES,
                "cover": cover.get("url") or "",
                "cover_local": cover.get("local") or "",
                "gallery": gallery,
                "skus": sku_records,
            }
        )

    featured_rank = {name: index for index, name in enumerate(FEATURED_NAMES)}
    aggregated.sort(
        key=lambda item: (
            0 if item["featured"] else 1,
            featured_rank.get(item["name"], 99),
            -item["sku_count"],
            item["name"],
        )
    )

    return {
        "source": "https://www.tongrentang.com/jtProductList/d502e93816624e6780a8e959701ec3af/1.html",
        "site_name": "中国北京同仁堂（集团）有限责任公司",
        "section": "同仁堂双龙标产品",
        "category": "中成药",
        "sku_count": len(products),
        "product_count": len(aggregated),
        "featured": [item["name"] for item in aggregated if item["featured"]],
        "products": aggregated,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/tongrentang/products.json")
    parser.add_argument("--output", default="data/tongrentang/products_aggregated.json")
    parser.add_argument("--gallery-copy", default="gallery/src/catalog.json")
    args = parser.parse_args()

    products = json.loads(Path(args.input).read_text(encoding="utf-8"))
    catalog = aggregate(products)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.gallery_copy:
        gallery_path = Path(args.gallery_copy)
        gallery_path.parent.mkdir(parents=True, exist_ok=True)
        gallery_path.write_text(json.dumps(catalog, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"wrote {catalog['product_count']} products / {catalog['sku_count']} skus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
