import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const body = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "智库云 - 收藏夹知识库",
  description: "将你的 B站收藏夹变成可对话的知识库",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`${body.variable} antialiased`}>{children}</body>
    </html>
  );
}
