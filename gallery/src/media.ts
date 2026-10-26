import type { SyntheticEvent } from "react";
import type { Product } from "./types";

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
