export function mediaSrc(remote: string, local?: string | null): string {
  if (local) {
    return `/product-images/${local}`;
  }
  return remote;
}
