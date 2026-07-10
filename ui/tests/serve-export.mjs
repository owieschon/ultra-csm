import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, resolve, sep } from "node:path";

const root = resolve("out");
const host = "127.0.0.1";
const port = 4173;

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".woff2", "font/woff2"],
]);

async function resolveExportPath(rawUrl) {
  const url = new URL(rawUrl ?? "/", `http://${host}:${port}`);
  let pathname = decodeURIComponent(url.pathname);
  if (pathname === "/" || pathname === "/ui" || pathname === "/ui/") {
    pathname = "/index.html";
  } else if (pathname.startsWith("/ui/")) {
    pathname = pathname.slice(3);
  }
  if (pathname.endsWith("/")) pathname += "index.html";

  const direct = resolve(root, `.${pathname}`);
  if (direct !== root && !direct.startsWith(`${root}${sep}`)) return null;
  try {
    if ((await stat(direct)).isFile()) return direct;
  } catch {
    // Try Next's trailing-slash export shape below.
  }
  const nested = resolve(root, `.${pathname}/index.html`);
  if (nested !== root && !nested.startsWith(`${root}${sep}`)) return null;
  try {
    return (await stat(nested)).isFile() ? nested : null;
  } catch {
    return null;
  }
}

const server = createServer(async (request, response) => {
  const file = await resolveExportPath(request.url);
  if (!file) {
    response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
    response.end("Not found");
    return;
  }
  const body = await readFile(file);
  response.writeHead(200, {
    "Cache-Control": "no-store",
    "Content-Type": contentTypes.get(extname(file)) ?? "application/octet-stream",
  });
  response.end(body);
});

server.listen(port, host, () => {
  process.stdout.write(`serving ${root} at http://${host}:${port}\n`);
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
