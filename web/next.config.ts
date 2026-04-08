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

  // For Render deployment compatibility
  serverRuntimeConfig: {
    apiUrl: process.env.BACKEND_URL || 'http://localhost:8000',
  },
  publicRuntimeConfig: {
    apiUrl: process.env.NEXT_PUBLIC_API_URL,
  },
};

export default nextConfig;
