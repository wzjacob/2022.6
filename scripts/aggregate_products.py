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

UNIT_MAP = {
    "g": "克",
    "kg": "千克",
    "mg": "毫克",
    "ml": "毫升",
    "l": "升",
}

ITEM_WORDS = "丸|袋|瓶|盒|支|片|块|颗|粒|板|贴|枚"
MEASURE_WORDS = "毫克|千克|毫升|克|kg|mg|ml|g|升"
NUM = r"(\d+(?:\.\d+)?)"
NUM_TOKEN = r"(?:\d+(?:\.\d+)?)"

SPEC_CASES = {
    "3g×2丸": "3克 × 2丸",
    "3g×4丸": "3克 × 4丸",
    "3g×1丸": "3克 × 1丸",
    "每丸重3g": "3克 / 丸",
    "每丸重3g，每盒装2丸。": "3克 × 2丸",
    "每丸重3g，每盒装8丸。": "3克 × 8丸",
    "每盒1蜡壳丸，每蜡壳丸1丸，每丸重3克": "3克 × 1丸（蜡壳）",
    "每盒2小盒，每小盒1蜡壳丸，每蜡壳丸1丸，每丸重3克": "3克 × 2丸（蜡壳）",
    "每盒6小盒，每小盒1蜡壳丸，每蜡壳丸1丸，每丸重3克": "3克 × 6丸（蜡壳）",
    "每丸重9克，每盒装10丸。": "9克 × 10丸",
    "每丸重9克，每盒装20丸（大蜜丸）。": "9克 × 20丸",
    "每瓶装600粒，每盒装1瓶。": "600粒 × 1瓶",
    "每瓶装60克，每盒装1瓶。": "60克 × 1瓶",
    "每袋装30粒，每盒装20袋。": "30粒 × 20袋",
    "每瓶装6克，每盒装6瓶": "6克 × 6瓶",
    "每瓶装36克": "36克 / 瓶",
    "6克×10袋": "6克 × 10袋",
    "每盒装6丸，每丸重9克": "9克 × 6丸",
    "每瓶装12片,每盒装3瓶。": "12片 × 3瓶",
    "每瓶装24片,每盒装1瓶。": "24片 × 1瓶",
    "每瓶装180粒每盒装6瓶": "180粒 × 6瓶",
    "每瓶装1.5g 每盒装6瓶": "1.5克 × 6瓶",
    "每瓶装1.5g每盒装10瓶": "1.5克 × 10瓶",
    "塑料瓶装，每瓶装30g，每盒装2瓶": "30克 × 2瓶",
    "每袋装12克,每盒装10袋。": "12克 × 10袋",
    "每袋装2.5g,每盒装6袋。": "2.5克 × 6袋",
    "每袋装2.5g,每盒装10袋。": "2.5克 × 10袋",
    "每袋装5g,每盒装10袋。": "5克 × 10袋",
    "每袋装4g，每盒装10袋（小蜜丸）。": "4克 × 10袋",
    "每袋装3克（无蔗糖，相当于饮片7g），每盒装10袋。": "3克 × 10袋（无蔗糖）",
    "每袋装5克（相当于饮片7g），每盒装10袋。": "5克 × 10袋",
    "每袋装5克（相当于饮片7g），每袋装18袋。": "5克 × 18袋",
    "每袋装30粒，每袋装5袋。": "30粒 × 5袋",
    "每板装12片，每袋装2板，每盒装1袋。": "12片 × 2板 × 1袋",
    "钠钙玻璃管制口服液体瓶装，每盒装10支": "10支 / 盒",
    "20g水蜜丸/瓶装": "20克 / 瓶",
    "187.5g/盒": "187.5克 / 盒",
    "玻璃瓶装，每瓶装750毫升，每盒装2瓶": "750毫升 × 2瓶",
    "玻璃瓶装，每瓶装750ml，每盒装1瓶": "750毫升 × 1瓶",
    "每支装10毫升，每盒装10支。": "10毫升 × 10支",
    "每块重31.25克，每盒装4块。": "31.25克 × 4块",
    "10丸/盒每丸重9g": "9克 × 10丸",
    "10毫升/支×24支/盒": "10毫升 × 24支",
    "10粒/板×6板": "10粒 × 6板",
    "0.3g*10瓶*3板": "0.3克 × 10瓶 × 3板",
    "10g×4袋×3盒": "10克 × 4袋 × 3盒",
    "150ml/瓶。": "150毫升 / 瓶",
}


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


def tidy_num(value: str) -> str:
    if "." in value:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return value.rstrip("0").rstrip(".")
    return value


def unit_cn(unit: str) -> str:
    return UNIT_MAP.get(unit.lower(), unit)


def measure(amount: str, unit: str) -> str:
    return f"{tidy_num(amount)}{unit_cn(unit)}"


def normalize_dosage_form(text: str) -> str:
    raw = (text or "").strip().replace("（", "(").replace("）", ")")
    if not raw:
        return ""
    match = re.fullmatch(r".+剂\((.+)\)", raw)
    inner = match.group(1) if match else raw
    aliases = {
        "薄膜衣": "薄膜衣片",
        "糖衣": "糖衣片",
        "口服液": "口服液",
        "膏滋": "膏滋",
        "内服": "散剂",
    }
    return aliases.get(inner, inner)


def _prep_spec(text: str) -> tuple[str, str]:
    cleaned = (text or "").strip()
    cleaned = cleaned.replace("（", "(").replace("）", ")")
    cleaned = cleaned.replace("＊", "×").replace("*", "×").replace("x", "×").replace("X", "×")
    cleaned = re.sub(
        r"^(?:塑料瓶装|玻璃瓶装|钠钙玻璃管制口服液体瓶装)[，,]?",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = cleaned.replace(",", "，")
    note = "（无蔗糖）" if "无蔗糖" in cleaned else ""
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    cleaned = re.sub(rf"(装{NUM_TOKEN}(?:{MEASURE_WORDS}|{ITEM_WORDS}))每", r"\1，每", cleaned)
    cleaned = re.sub(r"[。．.]+$", "", cleaned)
    return cleaned, note


def _with_note(label: str, note: str) -> str:
    return f"{label}{note}" if note and note not in label else label


def normalize_spec(raw: str) -> str:
    text, note = _prep_spec(raw)
    if not text:
        return "规格未标明"

    wax_box = re.fullmatch(
        rf"每盒{NUM}小盒，每小盒1蜡壳丸，每蜡壳丸1丸，每丸重{NUM}({MEASURE_WORDS})",
        text,
    )
    if wax_box:
        return _with_note(
            f"{measure(wax_box.group(2), wax_box.group(3))} × {tidy_num(wax_box.group(1))}丸（蜡壳）",
            note,
        )

    wax_one = re.fullmatch(
        rf"每盒{NUM}蜡壳丸，每蜡壳丸1丸，每丸重{NUM}({MEASURE_WORDS})",
        text,
    )
    if wax_one:
        return _with_note(
            f"{measure(wax_one.group(2), wax_one.group(3))} × {tidy_num(wax_one.group(1))}丸（蜡壳）",
            note,
        )

    slash_then_weight = re.fullmatch(
        rf"{NUM}({ITEM_WORDS})/盒每({ITEM_WORDS})重{NUM}({MEASURE_WORDS})",
        text,
    )
    if slash_then_weight:
        return _with_note(
            f"{measure(slash_then_weight.group(4), slash_then_weight.group(5))} × {tidy_num(slash_then_weight.group(1))}{slash_then_weight.group(2)}",
            note,
        )

    unit_and_box = re.fullmatch(
        rf"每({ITEM_WORDS})重{NUM}({MEASURE_WORDS})，每(?:盒|袋)装{NUM}({ITEM_WORDS})",
        text,
    )
    if unit_and_box:
        return _with_note(
            f"{measure(unit_and_box.group(2), unit_and_box.group(3))} × {tidy_num(unit_and_box.group(4))}{unit_and_box.group(5)}",
            note,
        )

    box_then_unit = re.fullmatch(
        rf"每(?:盒|袋)装{NUM}({ITEM_WORDS})，每({ITEM_WORDS})重{NUM}({MEASURE_WORDS})",
        text,
    )
    if box_then_unit:
        return _with_note(
            f"{measure(box_then_unit.group(4), box_then_unit.group(5))} × {tidy_num(box_then_unit.group(1))}{box_then_unit.group(2)}",
            note,
        )

    triple = re.fullmatch(
        rf"每({ITEM_WORDS})装{NUM}({MEASURE_WORDS}|{ITEM_WORDS})，每({ITEM_WORDS})装{NUM}({ITEM_WORDS})，每({ITEM_WORDS})装{NUM}({ITEM_WORDS})",
        text,
    )
    if triple:
        return _with_note(
            f"{measure(triple.group(2), triple.group(3))} × {tidy_num(triple.group(5))}{triple.group(6)} × {tidy_num(triple.group(8))}{triple.group(9)}",
            note,
        )

    inner_and_box = re.fullmatch(
        rf"每({ITEM_WORDS})装{NUM}({MEASURE_WORDS}|{ITEM_WORDS})，每(?:盒|袋)装{NUM}({ITEM_WORDS})",
        text,
    )
    if inner_and_box:
        return _with_note(
            f"{measure(inner_and_box.group(2), inner_and_box.group(3))} × {tidy_num(inner_and_box.group(4))}{inner_and_box.group(5)}",
            note,
        )

    pack_only = re.fullmatch(rf"每({ITEM_WORDS})装{NUM}({MEASURE_WORDS}|{ITEM_WORDS})", text)
    if pack_only:
        return _with_note(f"{measure(pack_only.group(2), pack_only.group(3))} / {pack_only.group(1)}", note)

    unit_only = re.fullmatch(rf"每({ITEM_WORDS})重{NUM}({MEASURE_WORDS})", text)
    if unit_only:
        return _with_note(f"{measure(unit_only.group(2), unit_only.group(3))} / {unit_only.group(1)}", note)

    box_count = re.fullmatch(rf"每盒装{NUM}({ITEM_WORDS})", text)
    if box_count:
        return _with_note(f"{tidy_num(box_count.group(1))}{box_count.group(2)} / 盒", note)

    slash = re.fullmatch(rf"{NUM}({MEASURE_WORDS}|{ITEM_WORDS})(?:{ITEM_WORDS}|水蜜丸|大蜜丸|水丸)?[/／]({ITEM_WORDS})装?", text)
    if slash:
        return _with_note(f"{measure(slash.group(1), slash.group(2))} / {slash.group(3)}", note)

    if "×" in text:
        parts: list[str] = []
        for chunk in text.split("×"):
            chunk = re.sub(rf"[/／]({ITEM_WORDS})装?$", "", chunk)
            piece = re.fullmatch(rf"{NUM}({MEASURE_WORDS}|{ITEM_WORDS})", chunk)
            if piece:
                parts.append(measure(piece.group(1), piece.group(2)))
            else:
                parts.append(chunk)
        if parts:
            return _with_note(" × ".join(parts), note)

    return _with_note(raw.strip().rstrip("。．."), note)


def spec_sort_key(label: str) -> tuple[Any, ...]:
    incomplete = 1 if " / " in label and "×" not in label else 0
    wax = 1 if "蜡壳" in label else 0
    numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", label)]
    unit = numbers[0] if numbers else 0.0
    pack = numbers[1] if len(numbers) > 1 else 0.0
    extra = numbers[2] if len(numbers) > 2 else 0.0
    return (incomplete, unit, pack, extra, wax, label)


def spec_group_key(sku: dict[str, Any]) -> str:
    return f"{sku['spec_label']}|{sku['dosage_form']}"


def merge_skus(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[spec_group_key(record)].append(record)

    merged: list[dict[str, Any]] = []
    for items in groups.values():
        images = unique_keep_order(
            [url for item in items for url in [item.get("cover") or "", *(item.get("images") or [])]]
        )
        locals_ = unique_keep_order(
            [path for item in items if item.get("cover_local") for path in [item.get("cover_local") or ""]]
        )
        merged.append(
            {
                "id": items[0]["id"],
                "listed_name": items[0]["listed_name"],
                "specification": items[0]["specification"],
                "spec_label": items[0]["spec_label"],
                "dosage_form": items[0]["dosage_form"],
                "indications": most_common_text([item.get("indications") or "" for item in items]),
                "manufacturer": most_common_text([item.get("manufacturer") or "" for item in items]),
                "manufacturers": unique_keep_order([item.get("manufacturer") or "" for item in items]),
                "marketing_authorization_holder": most_common_text(
                    [item.get("marketing_authorization_holder") or "" for item in items]
                ),
                "production_address": most_common_text([item.get("production_address") or "" for item in items]),
                "detail_url": next((item.get("detail_url") or "" for item in items if item.get("detail_url")), ""),
                "cover": images[0] if images else "",
                "cover_local": locals_[0] if locals_ else None,
                "images": images,
                "member_count": len(items),
            }
        )
    merged.sort(key=lambda item: spec_sort_key(item["spec_label"]))
    return merged


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
        aliases = unique_keep_order([item["name"] for item in skus if family_name(item["name"]) == name and item["name"] != name])

        sku_records = []
        for item in skus:
            sku_records.append(
                {
                    "id": item["id"],
                    "listed_name": item["name"],
                    "specification": item.get("specification") or "",
                    "spec_label": normalize_spec(item.get("specification") or ""),
                    "dosage_form": normalize_dosage_form(item.get("dosage_form") or "") or (item.get("dosage_form") or ""),
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
        sku_records = merge_skus(sku_records)

        gallery: list[dict[str, str]] = []
        seen_images: set[str] = set()
        for item in sku_records:
            for url, local in zip(
                item.get("images") or [],
                [item.get("cover_local"), *([None] * len(item.get("images") or []))],
            ):
                if not url or url in seen_images:
                    continue
                seen_images.add(url)
                gallery.append({"url": url, "local": local or ""})

        cover = gallery[0] if gallery else {"url": "", "local": ""}
        dosage_forms = unique_keep_order([item.get("dosage_form") or "" for item in sku_records])
        manufacturers = unique_keep_order(
            [name for item in sku_records for name in (item.get("manufacturers") or [item.get("manufacturer") or ""])]
        )
        holders = unique_keep_order([item.get("marketing_authorization_holder") or "" for item in sku_records])

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
                "sku_count": len(sku_records),
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


def check_spec_cases() -> None:
    failed = []
    for raw, expected in SPEC_CASES.items():
        got = normalize_spec(raw)
        if got != expected:
            failed.append((raw, expected, got))
    if failed:
        lines = "\n".join(f"  {raw!r} -> {got!r} (want {expected!r})" for raw, expected, got in failed)
        raise SystemExit(f"spec normalize mismatch:\n{lines}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/tongrentang/products.json")
    parser.add_argument("--output", default="data/tongrentang/products_aggregated.json")
    parser.add_argument("--gallery-copy", default="gallery/src/catalog.json")
    args = parser.parse_args()

    check_spec_cases()
    products = json.loads(Path(args.input).read_text(encoding="utf-8"))
    catalog = aggregate(products)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.gallery_copy:
        gallery_path = Path(args.gallery_copy)
        gallery_path.parent.mkdir(parents=True, exist_ok=True)
        gallery_path.write_text(json.dumps(catalog, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"wrote {catalog['product_count']} products / {catalog['sku_count']} source skus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
