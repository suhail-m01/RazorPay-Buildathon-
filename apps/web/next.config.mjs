/** @type {import('next').NextConfig} */

const backendUrl =
  process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
      {
        source: "/webhook/:path*",
        destination: `${backendUrl}/webhook/:path*`,
      },
    ];
  },
};

export default nextConfig;