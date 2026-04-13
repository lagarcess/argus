/**
 * Secure Asset Fetcher for Stitch
 *
 * Enforces a domain allowlist to prevent SSRF and other retrieval-based attacks.
 * Usage: node secure-fetch.mjs <url> <output_path>
 */

import fs from 'node:fs';
import path from 'node:path';
import { URL } from 'node:url';

const ALLOWED_DOMAINS = [
  'storage.googleapis.com',
  'googleusercontent.com',
];

const ALLOWED_EXTENSIONS = ['.html', '.png', '.jpg', '.jpeg', '.json'];

async function secureFetch() {
  const urlArg = process.argv[2];
  const outputPath = process.argv[3];

  if (!urlArg || !outputPath) {
    console.error('Usage: node secure-fetch.mjs <url> <output_path>');
    process.exit(1);
  }

  try {
    const parsedUrl = new URL(urlArg);
    const hostname = parsedUrl.hostname;

    // Domain Validation
    const isAllowed = ALLOWED_DOMAINS.some(domain =>
      hostname === domain || hostname.endsWith('.' + domain)
    );

    if (!isAllowed) {
      console.error(`❌ Security Alert: Blocked unauthorized domain: ${hostname}`);
      process.exit(1);
    }

    // Path Validation
    const ext = path.extname(outputPath).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
       // Note: GCS URLs might have query params that obscure the extension,
       // so we primarily trust the output path extension provided by the agent.
       console.warn(`⚠️ Warning: Fetching to an unusual extension: ${ext}`);
    }

    console.log(`🔍 Initiating secure fetch for: ${hostname}...`);

    const response = await fetch(urlArg, {
      signal: AbortSignal.timeout(15000), // 15s timeout
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const buffer = await response.arrayBuffer();
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, Buffer.from(buffer));

    console.log(`✅ Successfully retrieved asset to: ${outputPath}`);
    process.exit(0);

  } catch (err) {
    console.error(`❌ Fetch Failed: ${err.message}`);
    process.exit(1);
  }
}

secureFetch();
