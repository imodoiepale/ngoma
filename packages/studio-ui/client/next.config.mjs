import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // The workspace root is packages/studio-ui (one lockfile). Without this, Next picks up a
  // stray lockfile higher up the disk and warns on every build.
  turbopack: { root: path.join(here, "..") },
  // No rewrites: every /api route is served by this app. The old proxy to a FastAPI server on
  // :8000 pointed at a backend that no longer exists.
};

export default nextConfig;
