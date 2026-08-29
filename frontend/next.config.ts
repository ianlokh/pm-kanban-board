import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: process.env.NODE_ENV === "development" ? undefined : "export",
  ...(process.env.NODE_ENV === "development"
    ? {
        async rewrites() {
          return [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }];
        },
      }
    : {}),
};

export default nextConfig;
