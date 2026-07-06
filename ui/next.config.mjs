import { fileURLToPath } from "url";
import { dirname } from "path";

/** @type {import('next').NextConfig} */
// Static export: `make ui-build` produces `ui/out`, which `make serve`
// mounts at `/ui` via FastAPI's StaticFiles (Decisions: one process for
// the demo). `next dev` on :3000 talks to the API on :8000 directly
// (CORS added in api.py's Phase 1 commit) and does not use this export.
const nextConfig = {
  output: "export",
  basePath: "/ui",
  trailingSlash: true,
  images: { unoptimized: true },
  // Pins Turbopack's workspace-root inference to this directory -- an
  // unrelated lockfile elsewhere on this machine (outside this repo) was
  // making Next.js 16 guess the wrong root.
  turbopack: { root: dirname(fileURLToPath(import.meta.url)) },
};

export default nextConfig;
