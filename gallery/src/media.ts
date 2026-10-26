import type { SyntheticEvent } from "react";
import type { Product, Sku } from "./types";

export function mediaSrc(remote: string, local?: string | null, optimized?: string | null): string {
  if (optimized) return optimized;
  if (remote) return remote;
  if (local) return `/product-images/${local}`;
  return "";
}

export function productCover(product: Product): string {
  return mediaSrc(product.cover, product.cover_local, product.cover_optimized);
}

export function productFrames(product: Product): string[] {
  if (product.gallery_optimized && product.gallery_optimized.length > 0) {
    return product.gallery_optimized;
  }
  if (product.gallery.length > 0) {
    return product.gallery.map((item) => mediaSrc(item.url, item.local));
  }
  const cover = productCover(product);
  return cover ? [cover] : [];
}

export function skuCover(sku: Sku | undefined, product: Product): string {
  if (!sku) return productCover(product);
  return mediaSrc(sku.cover, sku.cover_local, sku.cover_optimized) || productCover(product);
}

export function skuFrames(sku: Sku | undefined, product: Product): string[] {
  if (sku?.gallery_optimized && sku.gallery_optimized.length > 0) {
    return sku.gallery_optimized;
  }
  if (sku?.cover_optimized) {
    return [sku.cover_optimized];
  }
  const remotes = [sku?.cover, ...(sku?.images ?? [])].filter((url): url is string => Boolean(url));
  const unique = Array.from(new Set(remotes));
  if (unique.length > 0) return unique;
  return productFrames(product);
}

export function defaultSku(product: Product): Sku | undefined {
  const cover = product.cover;
  return (
    product.skus.find((item) => item.cover === cover || item.images.includes(cover)) ??
    product.skus[0]
  );
}

export function onImageError(remote: string, local?: string | null) {
  return (event: SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    if (local && !image.dataset.localTried) {
      image.dataset.localTried = "1";
      image.src = `/product-images/${local}`;
      return;
    }
    if (remote && image.src !== remote) {
      image.src = remote;
    }
  };
}
