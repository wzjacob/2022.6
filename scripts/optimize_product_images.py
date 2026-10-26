#!/usr/bin/env python3
"""Build 4:5 padded WebP covers for every aggregated Tong Ren Tang product."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

USER_AGENT = "Mozilla/5.0 (compatible; TongRenTangCatalogResearch/1.0)"
CANVAS = (800, 1000)
FILL_RATIO = 0.86
LOGO_RE = re.compile(r"(?:^|/)(?:l\d|logo|brand)|l1\.png|l2\.jpg|/l\d\.", re.I)


def encode_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return parsed._replace(path=urllib.parse.quote(parsed.path, safe="/-_.~")).geturl()


def fetch_bytes(url: str, retries: int = 4) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(encode_url(url), headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as response:
                data = response.read()
                if data.startswith(b"version https://git-lfs"):
                    raise RuntimeError("got git-lfs pointer")
                return data
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"download failed {url}: {last_error}") from last_error


def url_score(url: str) -> float:
    name = url.lower()
    score = 0.0
    if LOGO_RE.search(name):
        score -= 80
    if re.search(r"p1\.(png|jpg|jpeg|webp)", name):
        score += 24
    elif re.search(r"p2\.(png|jpg|jpeg|webp)", name):
        score += 16
    elif re.search(r"p3\.(png|jpg|jpeg|webp)", name):
        score += 10
    if "/gfgongsiimg/" in name or "/kjgongsiimg/" in name:
        score += 4
    return score


def image_score(url: str, image: Image.Image) -> float:
    score = url_score(url)
    width, height = image.size
    area = width * height
    if area < 80_000:
        score -= 18
    aspect = width / max(height, 1)
    score -= abs(math.log(aspect)) * 12
    score += min(22.0, math.log(max(area, 2)) - 8)
    return score


def plate_color(image: Image.Image) -> tuple[int, int, int]:
    sample = image.convert("RGB").resize((36, 36), Image.Resampling.BOX)
    pixels = list(sample.getdata())
    usable = [pixel for pixel in pixels if 28 < (pixel[0] + pixel[1] + pixel[2]) / 3 < 232]
    if len(usable) < 8:
        usable = pixels
    red = int(statistics.median(pixel[0] for pixel in usable))
    green = int(statistics.median(pixel[1] for pixel in usable))
    blue = int(statistics.median(pixel[2] for pixel in usable))
    # keep a muted plate so the pack stays readable
    return (
        max(18, min(210, int(red * 0.72 + 18))),
        max(18, min(210, int(green * 0.72 + 18))),
        max(18, min(210, int(blue * 0.72 + 18))),
    )


def compose_plate(image: Image.Image, background: tuple[int, int, int]) -> Image.Image:
    rgb = ImageOps.exif_transpose(image).convert("RGB")
    width, height = rgb.size
    scale = min((CANVAS[0] * FILL_RATIO) / width, (CANVAS[1] * FILL_RATIO) / height)
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    fitted = rgb.resize(new_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", CANVAS, background)
    canvas.paste(fitted, ((CANVAS[0] - new_size[0]) // 2, (CANVAS[1] - new_size[1]) // 2))
    return canvas


def hex_color(color: tuple[int, int, int]) -> str:
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def product_key(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]


def load_image(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return ImageOps.exif_transpose(image)


def collect_candidates(product: dict[str, Any]) -> list[dict[str, str]]:
    seen: set[str] = set()
    items: list[dict[str, str]] = []
    for item in product.get("gallery") or []:
        url = item.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        items.append({"url": url, "local": item.get("local") or ""})
    cover = product.get("cover") or ""
    if cover and cover not in seen:
        items.insert(0, {"url": cover, "local": product.get("cover_local") or ""})
    return items


def process_url(url: str, cache_dir: Path) -> dict[str, Any]:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
    cache_file = cache_dir / f"{digest}.bin"
    if cache_file.exists() and cache_file.stat().st_size > 32:
        data = cache_file.read_bytes()
    else:
        data = fetch_bytes(url)
        cache_file.write_bytes(data)
    image = load_image(data)
    color = plate_color(image)
    return {
        "url": url,
        "score": image_score(url, image),
        "width": image.size[0],
        "height": image.size[1],
        "color": color,
        "image": image,
    }


def save_webp(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "WEBP", quality=80, method=4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/tongrentang/products_aggregated.json")
    parser.add_argument("--out-dir", default="gallery/public/optimized")
    parser.add_argument("--cache-dir", default="/tmp/trt-img-cache")
    parser.add_argument("--max-gallery", type=int, default=4)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    catalog = json.loads(Path(args.input).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    needed: set[str] = set()
    per_product: list[list[dict[str, str]]] = []
    for product in catalog["products"]:
        candidates = collect_candidates(product)
        per_product.append(candidates)
        for item in candidates:
            needed.add(item["url"])

    print(f"downloading {len(needed)} unique images", flush=True)
    processed: dict[str, dict[str, Any]] = {}
    errors = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_url, url, cache_dir): url for url in needed}
        done = 0
        for future in as_completed(futures):
            url = futures[future]
            done += 1
            try:
                processed[url] = future.result()
            except (RuntimeError, UnidentifiedImageError, OSError) as exc:
                errors += 1
                print(f"skip {url}: {exc}", flush=True)
            if done % 40 == 0 or done == len(needed):
                print(f"images {done}/{len(needed)} ok={len(processed)} fail={errors}", flush=True)

    optimized_count = 0
    for product, candidates in zip(catalog["products"], per_product):
        scored = []
        for item in candidates:
            meta = processed.get(item["url"])
            if not meta:
                continue
            scored.append(meta)
        scored.sort(key=lambda item: item["score"], reverse=True)
        if not scored:
            product["cover_optimized"] = ""
            product["gallery_optimized"] = []
            product["plate_color"] = "#2a241c"
            continue

        key = product_key(product["id"])
        cover_meta = scored[0]
        gallery_meta = scored[: args.max_gallery]
        cover_path = out_dir / key / "cover.webp"
        save_webp(compose_plate(cover_meta["image"], cover_meta["color"]), cover_path)
        gallery_paths = []
        for index, meta in enumerate(gallery_meta):
            rel = Path(key) / f"g{index:02d}.webp"
            save_webp(compose_plate(meta["image"], meta["color"]), out_dir / rel)
            gallery_paths.append(f"/optimized/{rel.as_posix()}")
        product["cover"] = cover_meta["url"]
        product["cover_optimized"] = f"/optimized/{key}/cover.webp"
        product["gallery_optimized"] = gallery_paths
        product["plate_color"] = hex_color(cover_meta["color"])
        for sku in product.get("skus") or []:
            sku_urls = []
            seen: set[str] = set()
            for url in [sku.get("cover") or "", *(sku.get("images") or [])]:
                if not url or url in seen:
                    continue
                seen.add(url)
                if url in processed:
                    sku_urls.append(url)
            sku_urls.sort(key=lambda url: processed[url]["score"], reverse=True)
            sku_paths = []
            for url in sku_urls[:6]:
                meta = processed[url]
                digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
                rel = Path("sku") / f"{digest}.webp"
                save_webp(compose_plate(meta["image"], meta["color"]), out_dir / rel)
                sku_paths.append(f"/optimized/{rel.as_posix()}")
            sku["cover"] = sku_urls[0] if sku_urls else sku.get("cover") or ""
            sku["cover_optimized"] = sku_paths[0] if sku_paths else ""
            sku["gallery_optimized"] = sku_paths
            sku["plate_color"] = hex_color(processed[sku_urls[0]]["color"]) if sku_urls else product["plate_color"]
        optimized_count += 1

    Path(args.input).write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gallery_copy = Path("gallery/src/catalog.json")
    gallery_copy.write_text(json.dumps(catalog, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"optimized {optimized_count}/{len(catalog['products'])} products, download_fail={errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
