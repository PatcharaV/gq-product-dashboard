const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");

const root = __dirname;
const port = Number(process.env.PORT || 4173);

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

function send(res, status, body, type = "text/plain; charset=utf-8") {
  res.writeHead(status, {
    "Content-Type": type,
    "Cache-Control": "no-store",
  });
  res.end(body);
}

function resolveSafePath(urlPath) {
  const cleanPath = decodeURIComponent(urlPath.split("?")[0]);
  const target = cleanPath === "/" ? "/index.html" : cleanPath;
  const fullPath = path.resolve(root, `.${target}`);
  if (!fullPath.startsWith(root)) {
    return null;
  }
  return fullPath;
}

function serveFile(req, res) {
  const filePath = resolveSafePath(req.url);
  if (!filePath) {
    send(res, 403, "Forbidden");
    return;
  }

  fs.stat(filePath, (statErr, stat) => {
    if (statErr || !stat.isFile()) {
      send(res, 404, "Not found");
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {
      "Content-Type": mimeTypes[ext] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    fs.createReadStream(filePath).pipe(res);
  });
}

function runScraper(res) {
  const python = process.env.PYTHON_BIN || (process.platform === "win32" ? "python" : "python3");
  const child = spawn(python, ["scripts/scrape_gqsize.py"], {
    cwd: root,
    shell: false,
  });
  let output = "";
  child.stdout.on("data", (chunk) => {
    output += chunk.toString();
  });
  child.stderr.on("data", (chunk) => {
    output += chunk.toString();
  });
  child.on("close", (code) => {
    send(
      res,
      code === 0 ? 200 : 500,
      JSON.stringify({ ok: code === 0, code, output }, null, 2),
      "application/json; charset=utf-8"
    );
  });
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === "GET" && url.pathname === "/health") {
    send(
      res,
      200,
      JSON.stringify({ ok: true, service: "gq-product-dashboard" }),
      "application/json; charset=utf-8"
    );
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/products") {
    const dataPath = path.join(root, "data", "gq_products.json");
    fs.readFile(dataPath, "utf8", (err, text) => {
      if (err) {
        send(res, 500, JSON.stringify({ error: "Cannot read product data" }), "application/json");
        return;
      }
      send(res, 200, text, "application/json; charset=utf-8");
    });
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/refresh") {
    runScraper(res);
    return;
  }

  if (req.method !== "GET" && req.method !== "HEAD") {
    send(res, 405, "Method not allowed");
    return;
  }

  serveFile(req, res);
});

server.listen(port, () => {
  console.log(`GQSize dashboard running at http://localhost:${port}`);
});
