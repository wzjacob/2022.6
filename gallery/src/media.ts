import type { SyntheticEvent } from "react";

export function mediaSrc(remote: string, local?: string | null): string {
  if (remote) return remote;
  if (local) return `/product-images/${local}`;
  return "";
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
