import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "../styles/globals.css";
import { siteConfig } from "@/lib/site-config";

const geistSans = Geist({
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: siteConfig.browserTitle,
  description: "An AI-powered web application for generating and managing content.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={geistSans.className}>
      <body>{children}</body>
    </html>
  );
}
