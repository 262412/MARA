import path from "node:path";

const CONTENT_TYPES: Record<string, string> = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
};

export function resolveAppAsset(rendererRoot: string, requestUrl: string): string {
  if (/%2e/i.test(requestUrl)) {
    throw new Error("Encoded dot segments are not allowed");
  }

  const url = new URL(requestUrl);
  if (url.protocol !== "mara:" || url.hostname !== "app") {
    throw new Error("Unexpected application URL");
  }

  const relativePath =
    url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname.slice(1));
  if (!relativePath || relativePath.includes("\0")) {
    throw new Error("Invalid application asset path");
  }

  const root = path.resolve(rendererRoot);
  const resolved = path.resolve(root, relativePath);
  const relative = path.relative(root, resolved);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error("Application asset path escapes the renderer root");
  }
  return resolved;
}

export function contentTypeFor(assetPath: string): string {
  return CONTENT_TYPES[path.extname(assetPath).toLowerCase()] ?? "application/octet-stream";
}
