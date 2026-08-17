import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { PwaRegister } from "@/components/pwa-register";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "zChit — Chit fund operations, unified",
    template: "%s | zChit",
  },
  description: "Enterprise chit fund management for members, collections, field teams, payments, and compliance.",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = { themeColor: "#059669" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body suppressHydrationWarning className="flex min-h-full flex-col">
        <PwaRegister />
        {children}
      </body>
    </html>
  );
}
