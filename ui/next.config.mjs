/** @type {import('next').NextConfig} */
// Static export: `make ui-build` produces `ui/out`, which `make serve`
// mounts at `/ui` via FastAPI's StaticFiles (Decisions: one process for
// the demo). `next dev` on :3000 talks to the API on :8000 directly
// (CORS added in api.py's Phase 1 commit) and does not use this export.
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
