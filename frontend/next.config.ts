import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  output: "export",
  trailingSlash: true,
  // 强制 webpack：Turbopack 对含中文的路径存在 UTF-8 字节边界 bug
  // package.json 中已加 --webpack 标志，此处 webpack 函数确保 Next.js 识别 webpack 配置
  webpack: (config) => config,
  // 允许加载外部图片
  images: {
    unoptimized: true,
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
};

export default nextConfig;
