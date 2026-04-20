import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Server-side rendering enabled (required for Node.js Render deployment)
  // Do NOT use output: 'export' (that's for static sites)

  // Image optimization works with Next.js server
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
    ],
  },

  // Fix Next.js 16 HMR cross-origin warnings
  allowedDevOrigins: ['192.168.1.76', 'localhost:3000'],
};

export default nextConfig;
