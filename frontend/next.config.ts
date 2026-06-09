import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 强制 webpack：Turbopack 对含中文的路径存在 UTF-8 字节边界 bug
  // package.json 中已加 --webpack 标志，此处 webpack 函数确保 Next.js 识别 webpack 配置
  webpack: (config) => config,
  // 允许加载外部图片
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**.hdslb.com",
      },
      {
        protocol: "https",
        hostname: "**.bilivideo.com",
      },
      {
        protocol: "http",
        hostname: "localhost",
      },
    ],
  },
  // 环境变量
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

export default nextConfig;
