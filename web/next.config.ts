import type { NextConfig } from "next";

// Device QA runs the dev server over a LAN address, which the cross-origin dev
// guard blocks by default: the JS chunks never load and the phone shows a blank
// page with nothing in the console to explain it. Named hosts only, set locally
// for the session; nothing here reaches a deployed build.
const devOrigins = (process.env.NEXT_DEV_ALLOWED_ORIGINS ?? "")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  allowedDevOrigins: ["127.0.0.1", "localhost", ...devOrigins],
};

export default nextConfig;
