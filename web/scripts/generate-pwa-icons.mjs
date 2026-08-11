// Rasterizes the PWA icon set from the Argus mark in components/ArgusLogo.tsx.
// Dev-time only. Re-run after changing the mark:
//   bun run scripts/generate-pwa-icons.mjs
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const outputDir = join(webRoot, "public", "icons");

const BACKGROUND = "#191c1f";
const MARK = "#ffffff";
const VIEW_BOX = "0 0 473 447";

// "any" icons keep a normal icon margin. The maskable variant stays inside the
// 80 percent safe circle so Android never crops the mark.
const targets = [
  { file: "argus-192.png", size: 192, markWidthRatio: 0.62, radiusRatio: 0 },
  { file: "argus-512.png", size: 512, markWidthRatio: 0.62, radiusRatio: 0 },
  { file: "argus-maskable-512.png", size: 512, markWidthRatio: 0.54, radiusRatio: 0 },
  { file: "apple-touch-icon-180.png", size: 180, markWidthRatio: 0.62, radiusRatio: 0 },
];

async function readMarkGroup() {
  const source = await readFile(join(webRoot, "components", "ArgusLogo.tsx"), "utf-8");
  const start = source.indexOf("<g data-logo=");
  const end = source.indexOf("</g>", start);
  if (start === -1 || end === -1) {
    throw new Error("Could not find the Argus mark group in ArgusLogo.tsx");
  }
  return source.slice(start, end + "</g>".length);
}

function iconMarkup({ markGroup, size, markWidthRatio }) {
  const markWidth = Math.round(size * markWidthRatio);
  return `<!doctype html><html><head><style>
    html, body { margin: 0; padding: 0; }
    body {
      width: ${size}px; height: ${size}px;
      background: ${BACKGROUND};
      display: flex; align-items: center; justify-content: center;
    }
    svg { width: ${markWidth}px; height: auto; color: ${MARK}; display: block; }
  </style></head><body>
    <svg viewBox="${VIEW_BOX}" fill="currentColor" xmlns="http://www.w3.org/2000/svg">${markGroup}</svg>
  </body></html>`;
}

const markGroup = await readMarkGroup();
await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch();
try {
  for (const target of targets) {
    const page = await browser.newPage({
      viewport: { width: target.size, height: target.size },
      deviceScaleFactor: 1,
    });
    await page.setContent(iconMarkup({ markGroup, ...target }));
    const png = await page.screenshot({ type: "png" });
    await writeFile(join(outputDir, target.file), png);
    await page.close();
    console.log(`wrote public/icons/${target.file} (${target.size}x${target.size})`);
  }
} finally {
  await browser.close();
}
