import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_BUILD_DIR || ".next",
  ...(process.env.NEXT_PUBLIC_CLOUD_DEMO === "true"
    ? { output: "export" as const, trailingSlash: true }
    : {}),
};

export default nextConfig;
