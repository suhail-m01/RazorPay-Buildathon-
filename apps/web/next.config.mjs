/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Same-origin API: the browser only ever talks to this Next app, which proxies
    // to the FastAPI service (cookies stay first-party; preview iframes work).
    return [
      { source: "/api/v1/:path*", destination: "http://127.0.0.1:8000/api/v1/:path*" },
      { source: "/health", destination: "http://127.0.0.1:8000/health" },
      { source: "/webhook/:path*", destination: "http://127.0.0.1:8000/webhook/:path*" },
    ];
  },
};

export default nextConfig;
