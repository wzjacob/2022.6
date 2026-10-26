import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Connect, PreviewServer, ViteDevServer } from "vite";
import { defineConfig } from "vite";

const root = path.dirname(fileURLToPath(import.meta.url));
const imageRoot = path.resolve(root, "../data/tongrentang/images");

const MIME: Record<string, string> = {
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".gif": "image/gif",
  ".webp": "image/webp",
};

function serveLocalImages(req: IncomingMessage, res: ServerResponse, next: Connect.NextFunction) {
  const url = req.url || "";
  if (!url.startsWith("/product-images/")) {
    next();
    return;
  }
  const relative = decodeURIComponent(url.replace("/product-images/", ""));
  const file = path.resolve(imageRoot, relative);
  if (!file.startsWith(imageRoot) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    next();
    return;
  }
  const ext = path.extname(file).toLowerCase();
  res.setHeader("Content-Type", MIME[ext] || "application/octet-stream");
  res.setHeader("Cache-Control", "public, max-age=86400");
  fs.createReadStream(file).pipe(res);
}

function localImagePlugin() {
  return {
    name: "local-product-images",
    configureServer(server: ViteDevServer) {
      server.middlewares.use(serveLocalImages);
    },
    configurePreviewServer(server: PreviewServer) {
      server.middlewares.use(serveLocalImages);
    },
  };
}

export default defineConfig({
  plugins: [react(), localImagePlugin()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    fs: {
      allow: [path.resolve(root, "..")],
    },
  },
});
