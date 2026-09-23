import type { NextConfig } from "next";

function proxyTarget(): string | undefined {
  const fromEnv = process.env.API_PROXY_TARGET?.trim();
  if (fromEnv) {
    return fromEnv.replace(/\/+$/, "");
  }
  if (process.env.NODE_ENV !== "production") {
    return "http://localhost:8000";
  }
  return undefined;
}

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    const target = proxyTarget();
    if (!target) {
      return [];
    }
    return [
      {
        source: "/api/v1/:path*",
        destination: `${target}/api/v1/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
};

export default nextConfig;
